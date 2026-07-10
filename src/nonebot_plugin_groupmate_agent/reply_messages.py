import difflib
import re
from collections.abc import Sequence

import jieba
from pydantic import BaseModel, Field, field_validator

MAX_REPLY_MESSAGES = 3


class ReplyItem(BaseModel):
    content: str = Field(
        min_length=1,
        description="一条实际发送消息的正文；正文内部可以包含普通换行。",
    )
    target_ref: int | None = Field(
        default=None,
        ge=1,
        description="多目标逐条回复时对应本轮提示中的目标编号；普通回复省略。",
    )

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            raise ValueError("消息正文不能为空")
        return normalized


class TargetedReplyItem(ReplyItem):
    target_ref: int = Field(
        ge=1,
        description="对应本轮提示中的目标编号；每个编号必须恰好出现一次。",
    )


class ReplyArgs(BaseModel):
    messages: list[ReplyItem] = Field(
        min_length=1,
        max_length=MAX_REPLY_MESSAGES,
        description="要顺序发送的消息数组；每个元素是一条独立消息。",
    )


class TargetedReplyArgs(BaseModel):
    messages: list[TargetedReplyItem] = Field(
        min_length=1,
        max_length=MAX_REPLY_MESSAGES,
        description="按 target_ref 对应本轮各编号目标的回复数组。",
    )


def normalize_reply_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def semantic_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    seq_ratio = difflib.SequenceMatcher(None, a, b).ratio()
    a_tokens = {token for token in jieba.lcut(a) if token.strip()}
    b_tokens = {token for token in jieba.lcut(b) if token.strip()}
    if not a_tokens or not b_tokens:
        return seq_ratio

    intersection = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    jaccard = intersection / union if union else 0.0
    return max(seq_ratio, jaccard)


def dedupe_reply_items(
    messages: Sequence[ReplyItem],
    *,
    allow_reply_duplicates: bool = False,
) -> list[ReplyItem]:
    prepared: list[ReplyItem] = []
    for message in messages:
        if prepared and not allow_reply_duplicates:
            previous = normalize_reply_text(prepared[-1].content)
            current = normalize_reply_text(message.content)
            if semantic_similarity(previous, current) >= 0.9:
                continue
        prepared.append(message)
    return prepared


def resolve_reply_targets(
    messages: Sequence[ReplyItem],
    *,
    direct_target_count: int,
) -> list[ReplyItem]:
    resolved = list(messages)
    if direct_target_count <= 0:
        return resolved

    if direct_target_count == 1:
        invalid_refs = [message.target_ref for message in resolved if message.target_ref not in {None, 1}]
        if invalid_refs:
            raise ValueError("单目标回复的 target_ref 只能是 1")
        return resolved

    if len(resolved) != direct_target_count:
        raise ValueError(f"本轮有 {direct_target_count} 个目标，messages 必须恰好包含 {direct_target_count} 条回复")

    refs = [message.target_ref for message in resolved]
    if any(ref is None for ref in refs):
        raise ValueError("多目标回复的每条消息都必须提供 target_ref")

    expected_refs = set(range(1, direct_target_count + 1))
    actual_refs = {int(ref) for ref in refs if ref is not None}
    if len(actual_refs) != len(refs) or actual_refs != expected_refs:
        expected = ", ".join(str(ref) for ref in sorted(expected_refs))
        raise ValueError(f"target_ref 必须不重复并完整覆盖编号 {expected}")

    return sorted(resolved, key=lambda message: int(message.target_ref or 0))
