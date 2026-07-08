import datetime
from types import SimpleNamespace

from tests.helpers import load_module

recent_forward = load_module("groupmate_agent_recent_forward_under_test", "recent_forward.py")


def test_extract_forward_ids_from_dict_object_and_cq_segments():
    object_segment = SimpleNamespace(type="forward", data={"id": " obj-fwd "})
    fallback_segment = SimpleNamespace(type="forward", data={}, forward_id="fallback-fwd")
    message = [
        {"type": "forward", "data": {"id": "dict-fwd"}},
        {"type": "forward", "forward_id": "direct-dict-fwd"},
        {"type": "forward", "data": {"id": ""}},
        {"type": "text", "data": {"text": "not a forward"}},
        {"type": "forward", "data": {"id": "dict-fwd"}},
        object_segment,
        fallback_segment,
    ]

    assert recent_forward.extract_forward_ids_from_message_obj(message) == [
        "dict-fwd",
        "direct-dict-fwd",
        "obj-fwd",
        "fallback-fwd",
    ]
    assert recent_forward.extract_forward_ids_from_message_obj("[CQ:forward,id=cq-fwd]") == ["cq-fwd"]


def test_event_message_candidates_deduplicates_same_message_object():
    message = [{"type": "forward", "data": {"id": "fwd-1"}}]
    event = SimpleNamespace(
        message=message,
        original_message=message,
        get_message=lambda: message,
    )

    assert recent_forward.event_message_candidates(event, message) == [message]


def test_recent_forward_store_deduplicates_message_forward_pairs():
    now = datetime.datetime(2026, 1, 1, 12, 0, 0)
    store = recent_forward.RecentForwardMessageStore()

    store.remember(
        "group-1",
        "101",
        "user-1",
        "Alice",
        [{"type": "forward", "data": {"id": "fwd-1"}}, {"type": "forward", "data": {"id": "fwd-2"}}],
        now=now,
    )
    store.remember(
        "group-1",
        "101",
        "user-1",
        "Alice v2",
        [{"type": "forward", "data": {"id": "fwd-1"}}],
        now=now + datetime.timedelta(minutes=1),
    )

    refs = store.get_newest_first("group-1", now=now + datetime.timedelta(minutes=1))

    assert [(item["message_id"], item["forward_id"], item["user_name"]) for item in refs] == [
        ("101", "fwd-1", "Alice v2"),
        ("101", "fwd-2", "Alice"),
    ]


def test_recent_forward_store_prunes_expired_malformed_and_count_overflow():
    now = datetime.datetime(2026, 1, 1, 12, 0, 0)
    store = recent_forward.RecentForwardMessageStore(
        max_count=2,
        ttl=datetime.timedelta(minutes=10),
    )
    store._messages_by_session["group-1"] = [
        {"message_id": "old", "forward_id": "old", "created_at": now - datetime.timedelta(minutes=11)},
        {"message_id": "bad", "forward_id": "bad", "created_at": "not-a-datetime"},
        {"message_id": "keep-1", "forward_id": "fwd-1", "created_at": now - datetime.timedelta(minutes=3)},
        {"message_id": "keep-2", "forward_id": "fwd-2", "created_at": now - datetime.timedelta(minutes=2)},
        {"message_id": "keep-3", "forward_id": "fwd-3", "created_at": now - datetime.timedelta(minutes=1)},
    ]

    store.prune("group-1", now)

    assert [item["message_id"] for item in store.get_newest_first("group-1", now)] == [
        "keep-3",
        "keep-2",
    ]


def test_recent_forward_store_returns_empty_for_missing_session():
    store = recent_forward.RecentForwardMessageStore()

    assert store.get_newest_first("missing") == []
