import asyncio
import sys
from types import ModuleType, SimpleNamespace

from tests.helpers import install_package_stub, load_module


class FakeTarget:
    def __init__(self, id, private=False, self_id=None):
        self.id = id
        self.private = private
        self.self_id = self_id


class FakeUniMessage:
    sent: list[tuple[str, FakeTarget | None]] = []

    def __init__(self, content: str):
        self.content = content

    @classmethod
    def text(cls, content: str):
        return cls(content)

    async def send(self, target=None):
        self.sent.append((self.content, target))
        return SimpleNamespace(msg_ids=[{"message_id": "pm-1"}])


class FakeInterface:
    async def get_members(self, scene_type, session_id):
        assert scene_type == "group"
        assert session_id == "group-1"
        return [
            SimpleNamespace(id="user-1", name="Alice", nick="Ali", user=SimpleNamespace(name="AliceU", nick="AU")),
            SimpleNamespace(id="bot-1", name="Bot", nick="", user=SimpleNamespace(name="Bot", nick="")),
        ]


class FakeChatHistory:
    session_id = object()
    content_type = object()
    msg_id = SimpleNamespace(desc=lambda: "desc")

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


install_package_stub("private_tool_pkg")
install_package_stub("private_tool_pkg.agent")
install_package_stub("private_tool_pkg.agent.optional_tools")

alconna_module = ModuleType("nonebot_plugin_alconna")
alconna_module.Target = FakeTarget
alconna_module.UniMessage = FakeUniMessage
sys.modules["nonebot_plugin_alconna"] = alconna_module

uninfo_module = ModuleType("nonebot_plugin_uninfo")
uninfo_module.SceneType = SimpleNamespace(GROUP="group")
sys.modules["nonebot_plugin_uninfo"] = uninfo_module

nonebot_log_module = ModuleType("nonebot.log")
nonebot_log_module.logger = SimpleNamespace(
    warning=lambda *a, **k: None,
    error=lambda *a, **k: None,
    info=lambda *a, **k: None,
)
sys.modules["nonebot.log"] = nonebot_log_module

model_module = ModuleType("private_tool_pkg.model")
model_module.ChatHistory = FakeChatHistory
sys.modules["private_tool_pkg.model"] = model_module

reply_guard_module = ModuleType("private_tool_pkg.reply_guard")


async def _can_request_continue(session_id, request_id):
    return True


reply_guard_module.can_request_continue = _can_request_continue
sys.modules["private_tool_pkg.reply_guard"] = reply_guard_module

types = load_module("private_tool_pkg.agent.optional_tools.types", "agent/optional_tools/types.py")
private_message = load_module(
    "private_tool_pkg.agent.optional_tools.private_message",
    "agent/optional_tools/private_message.py",
)


def make_ctx(enabled=True):
    return types.OptionalToolContext(
        db_session=None,
        session_id="group-1",
        request_id=None,
        user_id="user-1",
        user_name="Alice",
        interface=FakeInterface(),
        bot_id="bot-1",
        history=[],
        direct_targets=[],
        emoji_like_candidate_ids=set(),
        has_direct_targets=False,
        is_multi_direct_reply=False,
        is_cross_user_direct_reply=False,
        has_admin_permission=False,
        config=SimpleNamespace(proactive_private_message=enabled, bot_name="bot"),
        model=None,
        stop_words=[],
        send_target=SimpleNamespace(id="group-1"),
        is_private=False,
    )


def test_private_message_healthcheck_respects_disabled_config():
    ok, reason = asyncio.run(private_message.healthcheck(make_ctx(enabled=False)))

    assert ok is False
    assert reason == "proactive_private_message disabled"


def test_private_message_builds_bundle_when_enabled():
    bundle = asyncio.run(private_message.build(make_ctx(enabled=True)))

    assert bundle.name == "private_message"
    assert bundle.tools[0].name == "send_private_message"
    assert bundle.tool_limits == [types.ToolLimitSpec(tool_name="send_private_message", run_limit=1)]
    assert "主动私聊" in bundle.prompt


def test_private_message_tool_resolves_target_name_and_sends():
    FakeUniMessage.sent.clear()
    marked = []
    ctx = make_ctx(enabled=True)
    ctx.mark_sent = lambda: marked.append(True)
    tool = private_message.create_private_message_tool(ctx)

    result = asyncio.run(
        tool.ainvoke(
            {
                "content": "hello",
                "target_name": "Alice",
                "reason": "test",
            }
        )
    )

    assert result == "已主动私聊用户 user-1。"
    assert marked == [True]
    assert FakeUniMessage.sent[0][0] == "hello"
    assert FakeUniMessage.sent[0][1].id == "user-1"
    assert FakeUniMessage.sent[0][1].private is True
