import datetime
import re
from collections.abc import Iterator
from typing import Any

RECENT_FORWARD_MESSAGE_MAX_COUNT = 20
RECENT_FORWARD_MESSAGE_TTL = datetime.timedelta(hours=1)


def iter_message_segments(message_obj: Any) -> Iterator[Any]:
    if message_obj is None:
        return

    if isinstance(message_obj, dict):
        seg_type = message_obj.get("type")
        if seg_type:
            yield message_obj
        return

    if isinstance(message_obj, (bytes, bytearray)):
        message_obj = message_obj.decode("utf-8", errors="ignore")

    if isinstance(message_obj, str):
        for match in re.finditer(r"\[CQ:(\w+),([^\]]*)\]", message_obj):
            seg_data: dict[str, str] = {}
            raw_data = match.group(2)
            if raw_data:
                for item in raw_data.split(","):
                    if "=" not in item:
                        continue
                    key, value = item.split("=", 1)
                    seg_data[key] = value
            yield {"type": match.group(1), "data": seg_data}
        return

    try:
        iterator = iter(message_obj)
    except TypeError:
        return

    yield from iterator


def segment_type_and_data(seg: Any) -> tuple[str | None, dict[str, Any]]:
    if isinstance(seg, dict):
        seg_type = seg.get("type")
        seg_data = seg.get("data") or {}
        return seg_type, seg_data if isinstance(seg_data, dict) else {}

    seg_type = getattr(seg, "type", None)
    seg_data = getattr(seg, "data", None) or {}
    return seg_type, seg_data if isinstance(seg_data, dict) else {}


def extract_forward_ids_from_message_obj(message_obj: Any) -> list[str]:
    forward_ids: list[str] = []
    seen: set[str] = set()
    for seg in iter_message_segments(message_obj):
        seg_type, seg_data = segment_type_and_data(seg)
        if seg_type != "forward":
            continue

        # Some adapters put forward ids on the segment itself instead of data.
        if isinstance(seg, dict):
            raw_id = seg_data.get("id") or seg.get("id") or seg.get("forward_id")
        else:
            raw_id = seg_data.get("id") or getattr(seg, "id", None) or getattr(seg, "forward_id", None)
        forward_id = str(raw_id or "").strip()
        if not forward_id or forward_id in seen:
            continue
        seen.add(forward_id)
        forward_ids.append(forward_id)
    return forward_ids


def event_message_candidates(event: Any, *extra_candidates: Any) -> list[Any]:
    candidates: list[Any] = []
    seen_ids: set[int] = set()

    def add(value: Any) -> None:
        if value is None:
            return
        marker = id(value)
        if marker in seen_ids:
            return
        seen_ids.add(marker)
        candidates.append(value)

    for value in extra_candidates:
        add(value)

    for attr in ("message", "original_message"):
        add(getattr(event, attr, None))

    get_message = getattr(event, "get_message", None)
    if callable(get_message):
        try:
            add(get_message())
        except Exception:
            pass
    return candidates


def extract_text_from_message_obj(message_obj: Any) -> str:
    parts: list[str] = []
    for seg in iter_message_segments(message_obj):
        seg_type, seg_data = segment_type_and_data(seg)
        if seg_type != "text":
            continue
        text = str(seg_data.get("text") or "").strip()
        if text:
            parts.append(text)

    if parts:
        return " ".join(parts)

    if isinstance(message_obj, str):
        text = re.sub(r"\[CQ:[^\]]+\]", "", message_obj)
        return re.sub(r"\s+", " ", text).strip()

    return ""


class RecentForwardMessageStore:
    def __init__(
        self,
        *,
        max_count: int = RECENT_FORWARD_MESSAGE_MAX_COUNT,
        ttl: datetime.timedelta = RECENT_FORWARD_MESSAGE_TTL,
    ) -> None:
        self.max_count = max_count
        self.ttl = ttl
        self._messages_by_session: dict[str, list[dict[str, Any]]] = {}

    def prune(self, session_id: str, now: datetime.datetime | None = None) -> None:
        bucket = self._messages_by_session.get(session_id)
        if not bucket:
            return

        current = now or datetime.datetime.now()
        cutoff = current - self.ttl
        kept: list[dict[str, Any]] = []
        for item in bucket:
            created_at = item.get("created_at")
            if not isinstance(created_at, datetime.datetime):
                continue
            if created_at < cutoff:
                continue
            kept.append(item)

        if len(kept) > self.max_count:
            kept = kept[-self.max_count :]
        if kept:
            bucket[:] = kept
        else:
            self._messages_by_session.pop(session_id, None)

    def remember(
        self,
        session_id: str,
        message_id: str,
        user_id: str,
        user_name: str,
        *message_candidates: Any,
        now: datetime.datetime | None = None,
    ) -> None:
        forward_ids: list[str] = []
        seen_forward_ids: set[str] = set()
        for candidate in message_candidates:
            for forward_id in extract_forward_ids_from_message_obj(candidate):
                if forward_id in seen_forward_ids:
                    continue
                seen_forward_ids.add(forward_id)
                forward_ids.append(forward_id)
        if not forward_ids:
            return

        created_at = now or datetime.datetime.now()
        replacement_keys = {(message_id, forward_id) for forward_id in forward_ids}
        bucket = self._messages_by_session.setdefault(session_id, [])
        bucket[:] = [
            item
            for item in bucket
            if (item.get("message_id"), item.get("forward_id")) not in replacement_keys
        ]
        for forward_id in forward_ids:
            bucket.append(
                {
                    "message_id": message_id,
                    "forward_id": forward_id,
                    "user_id": user_id,
                    "user_name": user_name,
                    "created_at": created_at,
                }
            )
        self.prune(session_id, created_at)

    def get_newest_first(
        self,
        session_id: str,
        now: datetime.datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Return recent forward refs newest-first for prompt/tool context."""
        self.prune(session_id, now)
        bucket = self._messages_by_session.get(session_id) or []
        return [dict(item) for item in reversed(bucket)]
