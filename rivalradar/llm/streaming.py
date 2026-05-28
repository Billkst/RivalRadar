"""LLM streaming wrapper for chunk-event forwarding(plan v3.2 §5 — Epic 2.7)。

设计要点:
- stream=True wrapper of OpenAI-compatible client.chat.completions.create
- 每个 stream chunk 提取 delta.content,emit("chunk", {...}) forward 给 SSE
- 累积完整 text return for caller(后续可能用于 trace / persist / structured extract)

混合 LLM 调用模式(plan §5):
- Reasoning step / Narrative writing  → stream_chat()(typing 效果,本文件)
- 结构化 extraction(features / pricing / SWOT) → structured_call()(tools FC,structured.py)

未接 stream 的 caller path(现状,后续 polish):
- agents/analyst.py 仍用 structured_call() — 现状不动
- agents/writer.py  仍用 structured_call() — 现状不动
- Day-3 spike 后可优化:agent 先 stream_chat() reasoning step("灵犀正在分析..."
  typing)→ 然后 structured_call() extract;让用户看到 LLM 实时输出 + 最终结构化
"""
from __future__ import annotations

from typing import Any, Callable, Iterable


def stream_chat(
    messages: list[dict],
    *,
    client: Any,
    model: str,
    emit: Callable[[str, dict[str, Any]], None] | None = None,
    agent_id: str = "",
    step: str = "reasoning",
    **chat_kwargs: Any,
) -> str:
    """Stream chat completion + forward delta tokens as chunk events,return full text.

    Args:
        messages: OpenAI-format messages list (system / user / assistant)
        client: OpenAI-compatible client(Doubao Ark)
        model: endpoint id from rivalradar.config.doubao_model()
        emit: optional emit callback(sse.py 注入)。Signature: emit(ev_type, data)。
              None = 不 emit chunk events,退化成普通 stream(测试 / CLI 调用)。
        agent_id: chunk event payload 'agent_id' field("collector"/"analyst"/...)
        step: chunk event payload 'step' field("reasoning"/"drafting"/"thinking")
        **chat_kwargs: additional kwargs forwarded to client.chat.completions.create
                       (e.g. temperature, max_tokens)

    Returns:
        Full text accumulated from all delta chunks(empty string if stream had nothing)。

    Raises:
        任何 client.chat.completions.create 异常往上抛 — caller 包 try/except,
        sse.py 的 except Exception 路径会 mark_run_failed + yield error event。

    Note:
        - Sync function — graph nodes 是 sync,直接调用 OK
        - delta.content 在某些 chunks 是 None / empty(如 role chunk / 最末 chunk);
          skip 这些 chunks 不 emit empty delta(typingStore 不必处理空字符)
        - Frontend typingStore D7 throttle window 50 + 16ms batch,backend forward
          不限速(~30-50 chunk/s 是典型 LLM 输出节奏,完全在 throttle 上限内)
    """
    stream: Iterable[Any] = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        **chat_kwargs,
    )

    full_text: list[str] = []  # list append + final join 比 string += 快
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta is None:
            continue
        content = getattr(delta, "content", None)
        if not content:
            # None 或 empty string — role chunk / final chunk / tool chunk;skip 不 emit
            continue
        full_text.append(content)
        if emit is not None:
            emit("chunk", {
                "agent_id": agent_id,
                "step": step,
                "delta": content,
            })

    return "".join(full_text)
