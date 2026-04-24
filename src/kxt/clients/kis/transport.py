"""Async transport helpers for KIS REST and websocket access."""

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
import websockets
from websockets import exceptions as ws_exceptions

from .exceptions import KISAPIError, KISApprovalError, KISAuthenticationError, KISConnectionError, KISTimeoutError, KISTransportError

DEFAULT_TIMEOUT = 10.0
REAL_REST_BASE_URL = "https://openapi.koreainvestment.com:9443"
REAL_WS_BASE_URL = "ws://ops.koreainvestment.com:21000"
KIS_WS_PROXY_ENV = "KXT_KIS_WS_PROXY"
KIS_TOKEN_CACHE_SKEW = timedelta(minutes=1)


@dataclass(slots=True)
class KISToken:
    """Cached KIS access token metadata."""

    access_token: str
    expires_at: datetime

    def is_valid(self) -> bool:
        return datetime.now(UTC) + KIS_TOKEN_CACHE_SKEW < self.expires_at

    def as_cache_payload(self) -> dict[str, str]:
        return {
            "access_token": self.access_token,
            "expires_at": self.expires_at.astimezone(UTC).isoformat(),
        }

    @classmethod
    def from_cache_payload(cls, payload: dict[str, Any]) -> KISToken:
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


@dataclass(frozen=True, slots=True)
class KISJSONResponse:
    """Decoded KIS JSON response plus continuation metadata."""

    payload: dict[str, Any]
    tr_cont: str | None = None
    headers: dict[str, str] | None = None


class KISTransport:
    """Shared async transport state for KIS API calls."""

    def __init__(
        self,
        *,
        app_key: str,
        app_secret: str,
        timeout: float = DEFAULT_TIMEOUT,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._app_key = app_key
        self._app_secret = app_secret
        self._timeout = timeout
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None
        self._token: KISToken | None = None
        self._approval_key: str | None = None
        self._token_lock = asyncio.Lock()
        self._approval_lock = asyncio.Lock()
        self._token_cache_path = _kis_token_cache_path(app_key)

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

            response = await self._post_json(
                "/oauth2/tokenP",
                json={
                    "grant_type": "client_credentials",
                    "appkey": self._app_key,
                    "appsecret": self._app_secret,
                },
            )
            data = self._decode_json(response)
            access_token = str(data.get("access_token") or "").strip()
            expires_text = str(data.get("access_token_token_expired") or "").strip()
            if not access_token or not expires_text:
                raise KISAuthenticationError("KIS token response did not include token metadata")

            expires_at = datetime.strptime(expires_text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
            self._token = KISToken(access_token=access_token, expires_at=expires_at)
            self._store_cached_token(self._token)
            return access_token

    async def get_approval_key(self) -> str:
        async with self._approval_lock:
            if self._approval_key is not None:
                return self._approval_key
            approval_key = await self._request_approval_key_locked()
            self._approval_key = approval_key
            return approval_key

    async def refresh_approval_key(self) -> str:
        """Force-refresh the cached approval key (used after OAUTH/EGW errors)."""

        async with self._approval_lock:
            self._approval_key = None
            approval_key = await self._request_approval_key_locked()
            self._approval_key = approval_key
            return approval_key

    async def _request_approval_key_locked(self) -> str:
        response = await self._post_json(
            "/oauth2/Approval",
            json={
                "grant_type": "client_credentials",
                "appkey": self._app_key,
                "secretkey": self._app_secret,
            },
        )
        data = self._decode_json(response)
        approval_key = str(data.get("approval_key") or "").strip()
        if not approval_key:
            raise KISAuthenticationError("KIS approval response did not include approval_key")
        return approval_key

    async def get_json(self, path: str, *, tr_id: str, params: dict[str, Any]) -> dict[str, Any]:
        return (await self.get_json_response(path, tr_id=tr_id, params=params)).payload

    async def get_json_response(
        self, path: str, *, tr_id: str, params: dict[str, Any], tr_cont: str = ""
    ) -> KISJSONResponse:
        token = await self.get_access_token()
        headers = {
            "authorization": f"Bearer {token}",
            "appkey": self._app_key,
            "appsecret": self._app_secret,
            "tr_id": tr_id,
            "custtype": "P",
        }
        if tr_cont:
            headers["tr_cont"] = tr_cont
        response = await self._get(
            path,
            params=params,
            headers=headers,
        )
        return KISJSONResponse(
            payload=self._decode_json(response),
            tr_cont=response.headers.get("tr_cont"),
            headers=dict(response.headers),
        )

    async def post_json(
        self,
        path: str,
        *,
        tr_id: str,
        body: dict[str, Any],
        hashkey: str | None = None,
    ) -> dict[str, Any]:
        token = await self.get_access_token()
        headers: dict[str, str] = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": self._app_key,
            "appsecret": self._app_secret,
            "tr_id": tr_id,
            "custtype": "P",
        }
        if hashkey:
            headers["hashkey"] = hashkey
        response = await self._request(
            self._client.post,
            path,
            json=body,
            headers=headers,
        )
        return self._decode_json(response)

    async def connect_websocket(self):
        try:
            return await websockets.connect(
                f"{REAL_WS_BASE_URL}/tryitout",
                open_timeout=self._timeout,
                proxy=_resolve_kis_websocket_proxy(),
                ping_interval=None,
                ping_timeout=None,
                max_size=None,
                close_timeout=2.0,
            )
        except Exception as exc:
            mapped = map_websocket_exception(exc, action="opening websocket connection")
            if mapped is not None:
                raise mapped from exc
            raise

    async def _post_json(self, path: str, *, json: dict[str, Any]) -> httpx.Response:
        return await self._request(
            self._client.post,
            path,
            json=json,
            headers={"content-type": "application/json"},
        )

    async def _get(self, path: str, *, params: dict[str, Any], headers: dict[str, str]) -> httpx.Response:
        return await self._request(self._client.get, path, params=params, headers=headers)

    async def _request(self, request, path: str, **kwargs: Any) -> httpx.Response:
        try:
            return await request(f"{REAL_REST_BASE_URL}{path}", **kwargs)
        except httpx.HTTPError as exc:
            raise map_httpx_exception(exc, action=f"requesting {path}") from exc

    def _decode_json(self, response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise KISAPIError(f"KIS returned non-JSON response: HTTP {response.status_code}") from exc

        if response.is_error:
            raise KISAPIError(
                str(data.get("msg1") or response.text or f"HTTP {response.status_code}"),
                code=str(data.get("msg_cd") or response.status_code),
            )

        rt_cd = data.get("rt_cd")
        if rt_cd not in (None, "0"):
            msg_cd = str(data.get("msg_cd") or "")
            msg1 = str(data.get("msg1") or "KIS API request failed")
            if msg_cd and msg_cd.upper().startswith(("OAUTH", "EGW")):
                raise KISApprovalError(msg1 or msg_cd, code=msg_cd)
            raise KISAPIError(msg1, code=str(msg_cd or rt_cd))
        return data

    def _load_cached_token(self) -> KISToken | None:
        try:
            payload = json.loads(self._token_cache_path.read_text(encoding="utf-8"))
            token = KISToken.from_cache_payload(payload)
        except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
            self._clear_cached_token()
            return None

        if not token.is_valid():
            self._clear_cached_token()
            return None
        return token

    def _store_cached_token(self, token: KISToken) -> None:
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


def _resolve_kis_websocket_proxy() -> str | bool | None:
    """Return explicit websocket proxy behavior for KIS streaming.

    websockets>=15 inherits HTTP(S)_PROXY from the environment by default.
    That behavior can break KIS streaming in environments where a generic HTTP
    proxy doesn't support websocket upgrades correctly, so kxt defaults to a
    direct websocket connection unless explicitly configured otherwise.

    KXT_KIS_WS_PROXY values:
    - unset / empty / direct: connect directly and ignore env proxy discovery
    - auto: allow websockets to inherit proxy settings from the environment
    - any other non-empty value: treat as an explicit proxy URL
    """

    configured = os.getenv(KIS_WS_PROXY_ENV, "").strip()
    if not configured:
        return None

    if configured.lower() == "direct":
        return None
    if configured.lower() == "auto":
        return True
    return configured


def _kis_token_cache_path(app_key: str) -> Path:
    cache_key = sha256(f"{REAL_REST_BASE_URL}:{app_key}".encode("utf-8")).hexdigest()[:32]
    return _user_cache_dir() / "kxt" / "kis" / f"token-{cache_key}.json"


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


def map_httpx_exception(exc: httpx.HTTPError, *, action: str) -> KISTransportError:
    detail = _provider_error_detail(exc)

    if isinstance(exc, httpx.ProxyError):
        return KISConnectionError(f"KIS proxy connection failed while {action}{detail}")
    if isinstance(exc, (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout, httpx.TimeoutException)):
        return KISTimeoutError(f"KIS request timed out while {action}{detail}")
    if isinstance(exc, httpx.ConnectError):
        return KISConnectionError(f"KIS connection failed while {action}{detail}")
    return KISTransportError(f"KIS transport failed while {action}{detail}")


def map_websocket_exception(exc: BaseException, *, action: str) -> KISTransportError | None:
    detail = _provider_error_detail(exc)

    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return KISTimeoutError(f"KIS websocket timed out while {action}{detail}")
    if isinstance(exc, (ConnectionResetError, BrokenPipeError, EOFError)):
        return KISConnectionError(f"KIS websocket connection was lost while {action}{detail}")
    if isinstance(exc, ws_exceptions.ConnectionClosed):
        return KISConnectionError(f"KIS websocket connection closed unexpectedly while {action}{detail}")
    if isinstance(exc, (ws_exceptions.InvalidProxy, ws_exceptions.InvalidProxyMessage, ws_exceptions.ProxyError)):
        return KISConnectionError(f"KIS websocket proxy connection failed while {action}{detail}")
    if isinstance(exc, (ws_exceptions.InvalidHandshake, ws_exceptions.InvalidURI, OSError)):
        return KISConnectionError(f"KIS websocket connection failed while {action}{detail}")
    return None


def _provider_error_detail(exc: BaseException) -> str:
    message = str(exc).strip()
    if not message:
        return ""
    return f": {message}"
