from __future__ import annotations

import ssl
from typing import Union

SslVerifySetting = Union[bool, str, ssl.SSLContext]


def build_sprs_ssl_context(
    *,
    verify: bool | str = True,
    legacy_ciphers: bool = True,
) -> SslVerifySetting:
    """构建 SPRS HTTPS 客户端 SSL 上下文。

    部分企业内网网关仍使用 AES256-SHA 等旧套件，Python 3.13 默认 SECLEVEL=2
    会握手失败，而浏览器/curl 通常仍可访问。
    """
    if verify is False:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    elif isinstance(verify, ssl.SSLContext):
        ctx = verify
    elif isinstance(verify, str):
        ctx = ssl.create_default_context(cafile=verify)
    else:
        ctx = ssl.create_default_context()

    if legacy_ciphers:
        try:
            ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        except ssl.SSLError:
            ctx.set_ciphers("DEFAULT")

    return ctx
