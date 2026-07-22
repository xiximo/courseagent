from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import Settings
from app.sync.http_ssl import SslVerifySetting, build_sprs_ssl_context
from app.sync.errors import (
    SprsApiError,
    SprsGatewayBlockedError,
    SprsTimeoutError,
)

logger = logging.getLogger(__name__)

LIST_PATH = (
    "/api/sprsSarLawsPublicInfo/sar-laws-public-info/getLawsPublicInfoPage"
)
DOWNLOAD_PATH = (
    "/api/sprsSarLawsPublicInfo/sar-laws-public-info/downloadFile"
)


class SprsClient:
    def __init__(
        self,
        settings: Settings,
        *,
        base_url: str | None = None,
        timeout_seconds: int | None = None,
        tls_verify: bool | None = None,
        tls_legacy_ciphers: bool | None = None,
    ) -> None:
        self.settings = settings
        self.base_url = (base_url or settings.sprs_base_url).rstrip("/")
        self.timeout = timeout_seconds or settings.sprs_timeout_seconds
        verify = settings.sprs_tls_verify if tls_verify is None else tls_verify
        legacy = (
            settings.sprs_tls_legacy_ciphers
            if tls_legacy_ciphers is None
            else tls_legacy_ciphers
        )
        self._ssl_verify: SslVerifySetting = build_sprs_ssl_context(
            verify=verify,
            legacy_ciphers=legacy,
        )

    def _http_client(self) -> httpx.Client:
        return httpx.Client(
            timeout=self.timeout,
            follow_redirects=True,
            verify=self._ssl_verify,
        )

    def _detect_gateway_block(self, response: httpx.Response) -> None:
        content_type = (response.headers.get("content-type") or "").lower()
        if "text/html" in content_type:
            body_preview = response.text[:500].lower()
            if "atrust" in body_preview or "<html" in body_preview:
                raise SprsGatewayBlockedError()

    def fetch_laws_page(
        self,
        stand_type: str,
        current: int,
        limit: int,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{LIST_PATH}"
        params = {"standType": stand_type, "current": current, "limit": limit}
        try:
            with self._http_client() as client:
                response = client.get(url, params=params)
        except httpx.TimeoutException as exc:
            raise SprsTimeoutError() from exc
        except httpx.HTTPError as exc:
            raise SprsApiError("SPRS_HTTP_ERROR", f"SPRS 请求失败: {exc}") from exc

        self._detect_gateway_block(response)

        try:
            payload = response.json()
        except ValueError as exc:
            self._detect_gateway_block(response)
            raise SprsApiError(
                "SPRS_INVALID_JSON",
                "SPRS 返回非 JSON 响应",
            ) from exc

        if payload.get("ok") is False or str(payload.get("respCode")) not in {"0", "200"}:
            message = payload.get("message") or "SPRS 列表查询失败"
            raise SprsApiError("SPRS_LIST_ERROR", message)

        data = payload.get("data")
        if not isinstance(data, dict):
            raise SprsApiError("SPRS_EMPTY", "未查询到符合条件的标准")

        return data

    def download_files(self, file_ids: list[str]) -> tuple[bytes, str]:
        if not file_ids:
            raise SprsApiError("SPRS_NO_FILE", "附件 ID 为空")

        url = f"{self.base_url}{DOWNLOAD_PATH}"
        params = {"fileIds": ",".join(file_ids)}
        try:
            with self._http_client() as client:
                response = client.get(url, params=params)
        except httpx.TimeoutException as exc:
            raise SprsTimeoutError() from exc
        except httpx.HTTPError as exc:
            raise SprsApiError(
                "ATTACHMENT_FAILED",
                f"附件下载失败: {exc}",
            ) from exc

        self._detect_gateway_block(response)

        if response.status_code >= 400:
            raise SprsApiError(
                "ATTACHMENT_FAILED",
                f"附件下载失败，HTTP {response.status_code}",
            )

        content_type = response.headers.get("content-type") or "application/octet-stream"
        if "text/html" in content_type.lower():
            raise SprsGatewayBlockedError()

        content = response.content
        if "application/json" in content_type.lower() or content.lstrip()[:1] in (b"{", b"["):
            self._raise_if_json_error(content)

        return content, content_type

    @staticmethod
    def _raise_if_json_error(content: bytes) -> None:
        stripped = content.lstrip()
        if not stripped.startswith((b"{", b"[")):
            return
        try:
            payload = json.loads(stripped.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return
        if not isinstance(payload, dict):
            return
        if payload.get("ok") is False or str(payload.get("respCode")) not in {"0", "200"}:
            message = payload.get("message") or payload.get("msg") or "SPRS 附件下载失败"
            raise SprsApiError("ATTACHMENT_FAILED", message)
