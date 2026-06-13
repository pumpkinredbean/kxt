"""Async transport helpers for Toss Invest Open API."""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import httpx

from .exceptions import (
    TossInvestAPIError,
    TossInvestAuthenticationError,
    TossInvestConnectionError,
    TossInvestTimeoutError,
    TossInvestTransportError,
)

DEFAULT_TIMEOUT = 10.0
REST_BASE_URL = "https://openapi.tossinvest.com"
TOKEN_CACHE_SKEW = timedelta(minutes=1)


@dataclass(slots=True)
class TossInvestToken:
    """Cached Toss Invest access token metadata."""

    access_token: str
    expires_at: datetime

    def is_valid(self) -> bool:
        return datetime.now(UTC) + TOKEN_CACHE_SKEW < self.expires_at

    def as_cache_payload(self) -> dict[str, str]:
        return {
            "access_token": self.access_token,
            "expires_at": self.expires_at.astimezone(UTC).isoformat(),
        }

    @classmethod
    def from_cache_payload(cls, payload: dict[str, Any]) -> "TossInvestToken":
        access_token = str(payload.get("access_token") or "").strip()
        expires_text = str(payload.get("expires_at") or "").strip()
        if not access_token or not expires_text:
            raise ValueError("missing token cache metadata")
        expires_at = datetime.fromisoformat(expires_text)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        else:
            expires_at = expires_at.astimezone(UTC)
        return cls(access_token=access_token, expires_at=expires_at)


class TossInvestTransport:
    """Shared async transport state for Toss Invest REST calls."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        timeout: float = DEFAULT_TIMEOUT,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout = timeout
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None
        self._token: TossInvestToken | None = None
        self._token_lock = asyncio.Lock()
        self._token_cache_path = _token_cache_path(client_id)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_access_token(self) -> str:
        async with self._token_lock:
            if self._token is not None and self._token.is_valid():
                return self._token.access_token

            cached_token = self._load_cached_token()
            if cached_token is not None:
                self._token = cached_token
                return cached_token.access_token

            return await self._request_access_token_locked()

    async def refresh_access_token(self) -> str:
        async with self._token_lock:
            self._token = None
            self._clear_cached_token()
            return await self._request_access_token_locked()

    async def _request_access_token_locked(self) -> str:
        response = await self._request(
            self._client.post,
            "/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        data = self._decode_oauth_json(response)
        access_token = str(data.get("access_token") or "").strip()
        expires_in = data.get("expires_in")
        try:
            expires_delta = timedelta(seconds=int(expires_in))
        except (TypeError, ValueError) as exc:
            raise TossInvestAuthenticationError(
                "Toss Invest token response did not include expires_in"
            ) from exc
        if not access_token:
            raise TossInvestAuthenticationError(
                "Toss Invest token response did not include access_token"
            )
        self._token = TossInvestToken(
            access_token=access_token,
            expires_at=datetime.now(UTC) + expires_delta,
        )
        self._store_cached_token(self._token)
        return access_token

    async def get_result(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        account_seq: str | int | None = None,
    ) -> Any:
        return await self._request_result(
            self._client.get,
            path,
            params=params or {},
            account_seq=account_seq,
        )

    async def post_result(
        self,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        account_seq: str | int | None = None,
    ) -> Any:
        return await self._request_result(
            self._client.post,
            path,
            json=body or {},
            account_seq=account_seq,
        )

    async def _request_result(
        self,
        request,
        path: str,
        *,
        account_seq: str | int | None,
        **kwargs: Any,
    ) -> Any:
        for attempt in range(2):
            token = await self.get_access_token()
            headers = {
                "authorization": f"Bearer {token}",
                "accept": "application/json",
            }
            if "json" in kwargs:
                headers["content-type"] = "application/json"
            if account_seq is not None:
                headers["X-Tossinvest-Account"] = str(account_seq)
            response = await self._request(request, path, headers=headers, **kwargs)
            try:
                return self._decode_api_result(response)
            except TossInvestAPIError as exc:
                if attempt == 0 and _is_expired_access_token_error(exc):
                    await self.refresh_access_token()
                    continue
                raise
        raise TossInvestAuthenticationError("Toss Invest token refresh retry was exhausted")

    async def _request(self, request, path: str, **kwargs: Any) -> httpx.Response:
        try:
            return await request(f"{REST_BASE_URL}{path}", **kwargs)
        except httpx.HTTPError as exc:
            raise map_httpx_exception(exc, action=f"requesting {path}") from exc

    def _decode_oauth_json(self, response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise TossInvestAuthenticationError(
                f"Toss Invest returned non-JSON OAuth response: HTTP {response.status_code}"
            ) from exc

        if response.is_error:
            message = str(
                data.get("error_description")
                or data.get("message")
                or response.text
                or f"HTTP {response.status_code}"
            )
            raise TossInvestAuthenticationError(message)
        return data

    def _decode_api_result(self, response: httpx.Response) -> Any:
        try:
            data = response.json()
        except ValueError as exc:
            raise TossInvestAPIError(
                f"Toss Invest returned non-JSON response: HTTP {response.status_code}",
                provider="tossinvest",
                code=str(response.status_code),
            ) from exc

        error = data.get("error") if isinstance(data, dict) else None
        if response.is_error or error:
            code = None
            message = response.text or f"HTTP {response.status_code}"
            if isinstance(error, dict):
                code = str(error.get("code") or response.status_code)
                message = str(error.get("message") or message)
            elif isinstance(data, dict):
                code = str(data.get("code") or data.get("error") or response.status_code)
                message = str(data.get("error_description") or data.get("message") or message)
            raise TossInvestAPIError(message, provider="tossinvest", code=code)

        if isinstance(data, dict) and "result" in data:
            return data["result"]
        return data

    def _load_cached_token(self) -> TossInvestToken | None:
        try:
            payload = json.loads(self._token_cache_path.read_text(encoding="utf-8"))
            token = TossInvestToken.from_cache_payload(payload)
        except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
            self._clear_cached_token()
            return None

        if not token.is_valid():
            self._clear_cached_token()
            return None
        return token

    def _store_cached_token(self, token: TossInvestToken) -> None:
        temp_path: Path | None = None
        try:
            self._token_cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._token_cache_path.parent.chmod(0o700)
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._token_cache_path.parent,
                prefix=f"{self._token_cache_path.name}.",
                delete=False,
            ) as handle:
                json.dump(token.as_cache_payload(), handle)
                handle.flush()
                os.fchmod(handle.fileno(), 0o600)
                temp_path = Path(handle.name)
            temp_path.replace(self._token_cache_path)
            self._token_cache_path.chmod(0o600)
        except OSError:
            if temp_path is not None:
                with suppress(OSError):
                    temp_path.unlink(missing_ok=True)

    def _clear_cached_token(self) -> None:
        with suppress(FileNotFoundError, OSError):
            self._token_cache_path.unlink()


def _token_cache_path(client_id: str) -> Path:
    cache_key = sha256(f"{REST_BASE_URL}:{client_id}".encode("utf-8")).hexdigest()[:32]
    return _user_cache_dir() / "kxt" / "tossinvest" / f"token-{cache_key}.json"


def _is_expired_access_token_error(exc: TossInvestAPIError) -> bool:
    text = f"{getattr(exc, 'code', '')} {exc}".lower()
    english_token_error = "token" in text and (
        "expired" in text or "expire" in text or "invalid" in text
    )
    korean_token_error = "토큰" in text and ("만료" in text or "유효하지 않은" in text)
    return english_token_error or korean_token_error


def _user_cache_dir() -> Path:
    xdg_cache_home = os.getenv("XDG_CACHE_HOME", "").strip()
    if xdg_cache_home:
        return Path(xdg_cache_home).expanduser()

    home = Path.home()
    if os.name == "nt":
        local_app_data = os.getenv("LOCALAPPDATA", "").strip()
        if local_app_data:
            return Path(local_app_data).expanduser()
        return home / "AppData" / "Local"

    if os.sys.platform == "darwin":
        return home / "Library" / "Caches"

    return home / ".cache"


def map_httpx_exception(exc: httpx.HTTPError, *, action: str) -> TossInvestTransportError:
    detail = _provider_error_detail(exc)
    if isinstance(
        exc,
        (
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.PoolTimeout,
            httpx.TimeoutException,
        ),
    ):
        return TossInvestTimeoutError(f"Toss Invest request timed out while {action}{detail}")
    if isinstance(exc, (httpx.ConnectError, httpx.ProxyError)):
        return TossInvestConnectionError(f"Toss Invest connection failed while {action}{detail}")
    return TossInvestTransportError(f"Toss Invest transport failed while {action}{detail}")


def _provider_error_detail(exc: BaseException) -> str:
    detail = str(exc).strip()
    return f": {detail}" if detail else ""


__all__ = [
    "REST_BASE_URL",
    "TossInvestToken",
    "TossInvestTransport",
    "map_httpx_exception",
]
