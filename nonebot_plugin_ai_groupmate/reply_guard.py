import asyncio


_lock = asyncio.Lock()
_latest_request_ids: dict[str, str] = {}
_sent_request_ids: set[tuple[str, str]] = set()


async def set_latest_request_id(session_id: str, request_id: str) -> None:
    async with _lock:
        _latest_request_ids[session_id] = request_id


async def is_request_active(session_id: str, request_id: str) -> bool:
    async with _lock:
        return _latest_request_ids.get(session_id) == request_id


async def mark_request_sent(session_id: str, request_id: str) -> None:
    async with _lock:
        _sent_request_ids.add((session_id, request_id))


async def has_request_sent(session_id: str, request_id: str) -> bool:
    async with _lock:
        return (session_id, request_id) in _sent_request_ids


async def clear_request_sent(session_id: str, request_id: str) -> None:
    async with _lock:
        _sent_request_ids.discard((session_id, request_id))
