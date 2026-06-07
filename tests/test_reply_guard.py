import asyncio
from uuid import uuid4

from tests.helpers import load_module

reply_guard = load_module("groupmate_agent_reply_guard_under_test", "reply_guard.py")


def run(coro):
    return asyncio.run(coro)


def new_ids() -> tuple[str, str]:
    return f"session-{uuid4()}", f"request-{uuid4()}"


def test_active_request_lifecycle_controls_continuation():
    session_id, request_id = new_ids()

    assert run(reply_guard.is_request_active(session_id, request_id)) is False
    assert run(reply_guard.can_request_continue(session_id, request_id)) is False

    run(reply_guard.mark_request_active(session_id, request_id))
    assert run(reply_guard.is_request_active(session_id, request_id)) is True
    assert run(reply_guard.can_request_continue(session_id, request_id)) is True

    run(reply_guard.clear_request_active(session_id, request_id))
    assert run(reply_guard.is_request_active(session_id, request_id)) is False
    assert run(reply_guard.can_request_continue(session_id, request_id)) is False


def test_detached_request_lifecycle_keeps_continuation_alive():
    session_id, request_id = new_ids()

    reply_guard.mark_request_detached(session_id, request_id)
    assert reply_guard.is_request_detached(session_id, request_id) is True
    assert run(reply_guard.can_request_continue(session_id, request_id)) is True

    reply_guard.clear_request_detached(session_id, request_id)
    assert reply_guard.is_request_detached(session_id, request_id) is False
    assert run(reply_guard.can_request_continue(session_id, request_id)) is False


def test_detached_task_counter_keeps_request_detached_until_all_tasks_finish():
    session_id, request_id = new_ids()

    reply_guard.register_detached_task(session_id, request_id)
    reply_guard.register_detached_task(session_id, request_id)
    assert reply_guard.is_request_detached(session_id, request_id) is True

    reply_guard.unregister_detached_task(session_id, request_id)
    assert reply_guard.is_request_detached(session_id, request_id) is True

    reply_guard.unregister_detached_task(session_id, request_id)
    assert reply_guard.is_request_detached(session_id, request_id) is False


def test_sent_request_marker_lifecycle():
    session_id, request_id = new_ids()

    assert reply_guard.has_request_sent(session_id, request_id) is False

    reply_guard.mark_request_sent(session_id, request_id)
    assert reply_guard.has_request_sent(session_id, request_id) is True

    reply_guard.clear_request_sent(session_id, request_id)
    assert reply_guard.has_request_sent(session_id, request_id) is False
