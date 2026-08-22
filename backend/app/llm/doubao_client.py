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


@dataclass
class DoubaoToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class DoubaoCompletion:
    content: str
    tool_calls: list[DoubaoToolCall]
    finish_reason: str
    assistant_message: dict
    reasoning: str = ""


def chat_completion_turn(
    *,
    api_key: str,
    endpoint_id: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
    timeout_seconds: int = 120,
    temperature: float = 0.3,
) -> DoubaoCompletion:
    """单轮 Chat Completions，支持 OpenAI 兼容 tools / tool_calls。"""
    if not api_key.strip():
        raise DoubaoClientError("豆包 API Key 未配置")
    if not endpoint_id.strip():
        raise DoubaoClientError("豆包 Endpoint 未配置")

    url = f"{base_url.rstrip('/')}/chat/completions"
    payload: dict = {
        "model": endpoint_id.strip(),
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
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
        message = body["choices"][0]["message"]
        finish_reason = str(body["choices"][0].get("finish_reason") or "")
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise DoubaoClientError("豆包 API 响应格式异常") from exc

    raw_calls = message.get("tool_calls") or []
    tool_calls: list[DoubaoToolCall] = []
    for item in raw_calls:
        if not isinstance(item, dict):
            continue
        fn = item.get("function") if isinstance(item.get("function"), dict) else {}
        tool_calls.append(
            DoubaoToolCall(
                id=str(item.get("id") or f"call_{len(tool_calls)}"),
                name=str(fn.get("name") or "").strip(),
                arguments=str(fn.get("arguments") or ""),
            )
        )

    content = str(message.get("content") or "").strip()
    reasoning = str(
        message.get("reasoning_content") or message.get("reasoning") or ""
    ).strip()
    assistant_message = {
        "role": "assistant",
        "content": message.get("content"),
    }
    if raw_calls:
        assistant_message["tool_calls"] = raw_calls
    return DoubaoCompletion(
        content=content,
        tool_calls=tool_calls,
        finish_reason=finish_reason,
        assistant_message=assistant_message,
        reasoning=reasoning,
    )


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
