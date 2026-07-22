"""火山方舟（豆包）Chat Completions 客户端。"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DoubaoChatMessage:
    role: str
    content: str


class DoubaoClientError(RuntimeError):
    pass


def chat_completion(
    *,
    api_key: str,
    endpoint_id: str,
    messages: list[DoubaoChatMessage],
    base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
    timeout_seconds: int = 120,
    temperature: float = 0.3,
    stream: bool = False,
) -> str:
    if stream:
        text = "".join(
            iter_chat_completion(
                api_key=api_key,
                endpoint_id=endpoint_id,
                messages=messages,
                base_url=base_url,
                timeout_seconds=timeout_seconds,
                temperature=temperature,
            )
        ).strip()
        if not text:
            raise DoubaoClientError("豆包流式响应为空")
        return text

    if not api_key.strip():
        raise DoubaoClientError("豆包 API Key 未配置")
    if not endpoint_id.strip():
        raise DoubaoClientError("豆包 Endpoint 未配置")

    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": endpoint_id.strip(),
        "messages": [{"role": item.role, "content": item.content} for item in messages],
        "temperature": temperature,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=timeout_seconds, trust_env=False) as client:
            response = client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        raise DoubaoClientError("豆包 API 请求超时") from exc
    except httpx.HTTPError as exc:
        raise DoubaoClientError(f"豆包 API 网络错误: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text[:500]
        logger.warning("Doubao API error %s: %s", response.status_code, detail)
        raise DoubaoClientError(f"豆包 API 错误 ({response.status_code}): {detail}")

    try:
        body = response.json()
        return str(body["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise DoubaoClientError("豆包 API 响应格式异常") from exc


def iter_chat_completion(
    *,
    api_key: str,
    endpoint_id: str,
    messages: list[DoubaoChatMessage],
    base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
    timeout_seconds: int = 120,
    temperature: float = 0.3,
) -> Iterator[str]:
    """按 token/片段产出助手回复增量。"""
    if not api_key.strip():
        raise DoubaoClientError("豆包 API Key 未配置")
    if not endpoint_id.strip():
        raise DoubaoClientError("豆包 Endpoint 未配置")

    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": endpoint_id.strip(),
        "messages": [{"role": item.role, "content": item.content} for item in messages],
        "temperature": temperature,
        "stream": True,
    }
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=timeout_seconds, trust_env=False) as client:
            with client.stream("POST", url, json=payload, headers=headers) as response:
                if response.status_code >= 400:
                    detail = response.read().decode("utf-8", errors="replace")[:500]
                    logger.warning(
                        "Doubao stream API error %s: %s", response.status_code, detail
                    )
                    raise DoubaoClientError(
                        f"豆包 API 错误 ({response.status_code}): {detail}"
                    )
                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        body = json.loads(data)
                        delta = body["choices"][0]["delta"].get("content") or ""
                        if delta:
                            yield str(delta)
                    except (KeyError, IndexError, TypeError, ValueError):
                        continue
    except DoubaoClientError:
        raise
    except httpx.TimeoutException as exc:
        raise DoubaoClientError("豆包 API 请求超时") from exc
    except httpx.HTTPError as exc:
        raise DoubaoClientError(f"豆包 API 网络错误: {exc}") from exc
