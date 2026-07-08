import difflib
import re

import jieba

MULTI_REPLY_SEPARATOR = "/n"
_SEPARATOR_LINE_RE = re.compile(r"(?m)^[ \t]*/n[ \t]*$")


def normalize_reply_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def semantic_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    seq_ratio = difflib.SequenceMatcher(None, a, b).ratio()
    a_tokens = {t for t in jieba.lcut(a) if t.strip()}
    b_tokens = {t for t in jieba.lcut(b) if t.strip()}
    if not a_tokens or not b_tokens:
        return seq_ratio

    inter = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    jaccard = inter / union if union else 0.0
    return max(seq_ratio, jaccard)


def _split_by_separator_line(text: str) -> list[str]:
    parts: list[str] = []
    cursor = 0
    for match in _SEPARATOR_LINE_RE.finditer(text):
        parts.append(text[cursor : match.start()])
        cursor = match.end()
    parts.append(text[cursor:])
    return parts


def _dedupe_consecutive_lines(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return text
    deduped: list[str] = []
    for line in lines:
        if deduped and deduped[-1] == line:
            continue
        deduped.append(line)
    return "\n".join(deduped)


def split_reply_segments(
    text: str,
    *,
    allow_reply_duplicates: bool = False,
    split_on_newline: bool = False,
    max_segments: int = 3,
) -> list[str]:
    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized_text:
        return []

    if split_on_newline:
        split_text = normalized_text if allow_reply_duplicates else _dedupe_consecutive_lines(normalized_text)
        raw_segments = [line.strip() for line in split_text.split("\n") if line.strip()]
        overflow_joiner = " "
    else:
        raw_segments = [segment.strip() for segment in _split_by_separator_line(normalized_text) if segment.strip()]
        overflow_joiner = "\n"

    if not raw_segments:
        return []

    segments: list[str] = []
    for raw_segment in raw_segments:
        normalized_segment = normalize_reply_text(raw_segment)
        if not normalized_segment:
            continue

        if segments and not allow_reply_duplicates:
            previous_segment = normalize_reply_text(segments[-1])
            if semantic_similarity(previous_segment, normalized_segment) >= 0.9:
                continue

        if len(segments) < max_segments:
            segments.append(raw_segment)
        else:
            segments[-1] = f"{segments[-1]}{overflow_joiner}{raw_segment}".strip()

    return segments
