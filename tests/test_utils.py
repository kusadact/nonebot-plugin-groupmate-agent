import asyncio
import base64
import hashlib
import io
import sys
from datetime import datetime, timedelta
from types import ModuleType, SimpleNamespace

from PIL import Image

from tests.helpers import install_package_stub, load_module


class FakeColumn:
    def __eq__(self, other):
        return ("eq", other)

    def is_(self, other):
        return ("is", other)


class FakeChatHistory:
    session_id = FakeColumn()
    vectorized = FakeColumn()
    created_at = FakeColumn()
    msg_id = FakeColumn()


class FakeChatHistorySchema:
    @classmethod
    def model_validate(cls, value):
        return value


class FakeDB:
    async def batch_insert(self, contexts, session_id):
        return None


model_module = ModuleType("groupmate_agent_utils_pkg.model")
model_module.ChatHistory = FakeChatHistory
model_module.ChatHistorySchema = FakeChatHistorySchema
memory_module = ModuleType("groupmate_agent_utils_pkg.memory")
memory_module.DB = FakeDB()
orm_module = ModuleType("nonebot_plugin_orm")
orm_module.AsyncSession = object
install_package_stub("groupmate_agent_utils_pkg")
sys.modules["groupmate_agent_utils_pkg.model"] = model_module
sys.modules["groupmate_agent_utils_pkg.memory"] = memory_module
sys.modules["nonebot_plugin_orm"] = orm_module
utils = load_module("groupmate_agent_utils_pkg.utils", "utils.py")


def test_generate_file_hash_matches_sha256():
    data = b"groupmate-agent"
    assert utils.generate_file_hash(data) == hashlib.sha256(data).hexdigest()


def test_bytes_to_base64_returns_utf8_string():
    data = "群友".encode()
    assert utils.bytes_to_base64(data) == base64.b64encode(data).decode("utf-8")


def test_estimate_token_count_falls_back_to_character_count(monkeypatch):
    def raise_encoder():
        raise RuntimeError("encoder unavailable")

    monkeypatch.setattr(utils, "get_encoder", raise_encoder)
    assert utils.estimate_token_count("abc中文") == 5


def test_check_and_compress_image_bytes_returns_small_images_unchanged():
    raw = make_image_bytes(16, "PNG")
    assert utils.check_and_compress_image_bytes(raw, max_size_mb=2) == raw


def test_check_and_compress_image_bytes_compresses_large_images():
    raw = make_image_bytes(512, "PNG")

    compressed = utils.check_and_compress_image_bytes(
        raw,
        max_size_mb=0.005,
        quality_start=80,
        image_format="JPG",
    )

    assert len(compressed) < len(raw)
    with Image.open(io.BytesIO(compressed)) as image:
        assert image.format == "JPEG"


def test_check_and_compress_image_bytes_returns_original_on_invalid_image():
    raw = b"not an image but large enough"
    assert utils.check_and_compress_image_bytes(raw, max_size_mb=0) == raw


def test_combine_messages_into_context_formats_messages_and_ids():
    created_at = datetime(2026, 1, 1, 12, 30, 5)
    messages = [
        SimpleNamespace(msg_id=1, user_name="alice", content="hello", created_at=created_at),
        SimpleNamespace(msg_id=2, user_name="bob", content="world", created_at=created_at + timedelta(seconds=1)),
    ]

    context, msg_ids = utils.combine_messages_into_context(messages)

    assert msg_ids == [1, 2]
    assert "[2026-01-01 12:30:05] alice: hello" in context
    assert "[2026-01-01 12:30:06] bob: world" in context


def test_split_chat_into_context_groups_splits_by_time_gap_and_message_limit(monkeypatch):
    base = datetime(2026, 1, 1, 12, 0, 0)
    messages = [
        SimpleNamespace(msg_id=1, content="a", created_at=base),
        SimpleNamespace(msg_id=2, content="b", created_at=base + timedelta(minutes=1)),
        SimpleNamespace(msg_id=3, content="c", created_at=base + timedelta(hours=3)),
        SimpleNamespace(msg_id=4, content="d", created_at=base + timedelta(hours=3, minutes=1)),
        SimpleNamespace(msg_id=5, content="e", created_at=base + timedelta(hours=3, minutes=2)),
    ]

    monkeypatch.setattr(utils, "Select", lambda model: FakeQuery())
    monkeypatch.setattr(utils, "estimate_token_count", lambda text: 1)

    groups = asyncio.run(
        utils.split_chat_into_context_groups(
            FakeSession(messages),
            "session-1",
            max_time_gap=timedelta(hours=1),
            max_token_count=10,
            max_messages=2,
        )
    )

    assert [[message.msg_id for message in group] for group in groups] == [[1, 2], [3, 4], [5]]


def test_split_chat_into_context_groups_splits_by_token_count(monkeypatch):
    base = datetime(2026, 1, 1, 12, 0, 0)
    messages = [
        SimpleNamespace(msg_id=1, content="aa", created_at=base),
        SimpleNamespace(msg_id=2, content="bbb", created_at=base + timedelta(minutes=1)),
    ]

    monkeypatch.setattr(utils, "Select", lambda model: FakeQuery())
    monkeypatch.setattr(utils, "estimate_token_count", len)

    groups = asyncio.run(
        utils.split_chat_into_context_groups(
            FakeSession(messages),
            "session-1",
            max_time_gap=timedelta(hours=1),
            max_token_count=4,
            max_messages=10,
        )
    )

    assert [[message.msg_id for message in group] for group in groups] == [[1], [2]]


def test_insert_vectors_with_retry_retries_then_succeeds(monkeypatch):
    calls = []
    sleeps = []

    class FlakyDB:
        async def batch_insert(self, contexts, session_id):
            calls.append((contexts, session_id))
            if len(calls) < 2:
                raise RuntimeError("temporary failure")

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(utils, "DB", FlakyDB())
    monkeypatch.setattr(utils.asyncio, "sleep", fake_sleep)

    asyncio.run(utils.insert_vectors_with_retry(["context"], "session-1", max_retries=3))

    assert calls == [(["context"], "session-1"), (["context"], "session-1")]
    assert sleeps == [1]


def make_image_bytes(size: int, image_format: str) -> bytes:
    image = Image.new("RGB", (size, size))
    pixels = image.load()
    for x in range(size):
        for y in range(size):
            pixels[x, y] = ((x * 17 + y * 3) % 256, (x * 5 + y * 11) % 256, (x * 13 + y * 7) % 256)

    output = io.BytesIO()
    image.save(output, format=image_format)
    return output.getvalue()


class FakeQuery:
    def where(self, *_args):
        return self

    def order_by(self, *_args):
        return self


class FakeScalars:
    def __init__(self, messages):
        self.messages = messages

    def all(self):
        return self.messages


class FakeResult:
    def __init__(self, messages):
        self.messages = messages

    def scalars(self):
        return FakeScalars(self.messages)


class FakeSession:
    def __init__(self, messages):
        self.messages = messages

    async def execute(self, _query):
        return FakeResult(self.messages)
