import asyncio


_lock = asyncio.Lock()
_active_request_ids: set[tuple[str, str]] = set()
_sent_request_ids: set[tuple[str, str]] = set()
_detached_request_ids: set[tuple[str, str]] = set()
_detached_task_counts: dict[tuple[str, str], int] = {}


def _is_detached(session_id: str, request_id: str) -> bool:
    key = (session_id, request_id)
    return key in _detached_request_ids or _detached_task_counts.get(key, 0) > 0


async def mark_request_active(session_id: str, request_id: str) -> None:
    async with _lock:
        _active_request_ids.add((session_id, request_id))


async def clear_request_active(session_id: str, request_id: str) -> None:
    async with _lock:
        _active_request_ids.discard((session_id, request_id))


async def is_request_active(session_id: str, request_id: str) -> bool:
    async with _lock:
        return (session_id, request_id) in _active_request_ids


async def can_request_continue(session_id: str, request_id: str) -> bool:
    async with _lock:
        key = (session_id, request_id)
        return key in _active_request_ids or _is_detached(session_id, request_id)


def mark_request_detached(session_id: str, request_id: str) -> None:
    _detached_request_ids.add((session_id, request_id))


def is_request_detached(session_id: str, request_id: str) -> bool:
    return _is_detached(session_id, request_id)


def clear_request_detached(session_id: str, request_id: str) -> None:
    _detached_request_ids.discard((session_id, request_id))


def register_detached_task(session_id: str, request_id: str) -> None:
    key = (session_id, request_id)
    _detached_task_counts[key] = _detached_task_counts.get(key, 0) + 1


def unregister_detached_task(session_id: str, request_id: str) -> None:
    key = (session_id, request_id)
    count = _detached_task_counts.get(key, 0)
    if count <= 1:
        _detached_task_counts.pop(key, None)
    else:
        _detached_task_counts[key] = count - 1


def mark_request_sent(session_id: str, request_id: str) -> None:
    _sent_request_ids.add((session_id, request_id))


def has_request_sent(session_id: str, request_id: str) -> bool:
    return (session_id, request_id) in _sent_request_ids


def clear_request_sent(session_id: str, request_id: str) -> None:
    _sent_request_ids.discard((session_id, request_id))
