import asyncio
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

from langchain.tools import tool

from tests.helpers import install_package_stub, load_module

install_package_stub("groupmate_agent_tool_pkg")
install_package_stub("groupmate_agent_tool_pkg.agent")
install_package_stub("groupmate_agent_tool_pkg.agent.optional_tools")
types = load_module("groupmate_agent_tool_pkg.agent.optional_tools.types", "agent/optional_tools/types.py")
registry = load_module(
    "groupmate_agent_tool_pkg.agent.optional_tools.registry",
    "agent/optional_tools/registry.py",
)
skills = load_module("groupmate_agent_tool_pkg.agent.skills", "agent/skills.py")
STUB_TOOL_MODULE_NAMES = (
    "calculator",
    "emoji_like",
    "moderation",
    "private_message",
    "qq_avatar",
    "qq_avatar_describer",
    "scheduled_tasks",
    "web_search",
)
for name in STUB_TOOL_MODULE_NAMES:
    module = ModuleType(f"groupmate_agent_tool_pkg.agent.optional_tools.{name}")

    async def _empty_build(ctx, _name=name):
        return types.OptionalToolBundle(name=_name)

    module.build = _empty_build
    if name == "web_search":

        async def _disabled_healthcheck(ctx):
            return False, "disabled in test"

        module.healthcheck = _disabled_healthcheck

    sys.modules[module.__name__] = module
loader = load_module(
    "groupmate_agent_tool_pkg.agent.optional_tools.loader",
    "agent/optional_tools/loader.py",
)
calculator = load_module(
    "groupmate_agent_tool_pkg.agent.optional_tools.calculator",
    "agent/optional_tools/calculator.py",
)


def make_ctx():
    return types.OptionalToolContext(
        db_session=SimpleNamespace(name="db"),
        session_id="group-1",
        request_id="req-1",
        user_id="user-1",
        user_name="Alice",
        interface=SimpleNamespace(name="interface"),
        bot_id="bot-1",
        history=[],
        direct_targets=[],
        emoji_like_candidate_ids=set(),
        has_direct_targets=False,
        is_multi_direct_reply=False,
        is_cross_user_direct_reply=False,
        has_admin_permission=False,
        config=SimpleNamespace(),
        model=SimpleNamespace(name="model"),
        stop_words=[],
        send_target=SimpleNamespace(id="group-1"),
        is_private=False,
        bot=SimpleNamespace(name="bot"),
        event=SimpleNamespace(name="event"),
    )


def test_calculator_tool_returns_integer_float_and_error_results():
    bundle = asyncio.run(calculator.build(None))
    assert isinstance(bundle, types.OptionalToolBundle)
    assert bundle.name == "calculator"

    tool = bundle.tools[0]
    assert tool.name == "calculate_expression"
    assert tool.invoke({"expression": "2 + 3 * 4"}) == "14"
    assert tool.invoke({"expression": "1 / 4"}) == "计算结果是：0.2500000000"
    assert tool.invoke({"expression": "unknown_name + 1"}).startswith("计算失败。请检查表达式是否正确")


def test_registered_agent_tool_bundle_is_converted_to_optional_bundle():
    registry.clear_registered_agent_tools()

    @registry.register_agent_tool
    def build_registered_tools(ctx):
        @tool("get_registered_session_id")
        async def get_registered_session_id() -> str:
            """获取当前会话 ID。"""
            return ctx.session_id

        return registry.AgentToolBundle(
            name="registered_demo",
            tools=[get_registered_session_id],
            instructions=["- 需要会话 ID 时调用 `get_registered_session_id`"],
            tool_limits=[types.ToolLimitSpec(tool_name="get_registered_session_id", run_limit=1)],
        )

    bundles = asyncio.run(registry.build_registered_agent_tool_bundles(make_ctx()))

    assert len(bundles) == 1
    bundle = bundles[0]
    assert isinstance(bundle, types.OptionalToolBundle)
    assert bundle.name == "registered_demo"
    assert bundle.prompt == "- 需要会话 ID 时调用 `get_registered_session_id`"
    assert bundle.tool_limits == [types.ToolLimitSpec(tool_name="get_registered_session_id", run_limit=1)]
    assert bundle.tools[0].name == "get_registered_session_id"

    registry.clear_registered_agent_tools()


def test_registered_agent_tool_bundle_preserves_agent_skills():
    registry.clear_registered_agent_tools()

    @tool("skill_tool")
    async def skill_tool() -> str:
        """技能工具。"""
        return "ok"

    @registry.register_agent_tool
    def build_skill_tools(ctx):
        return registry.AgentToolBundle(
            name="registered_skill",
            tools=[skill_tool],
            skills=[
                types.AgentSkill(
                    name="registered_skill",
                    description="测试按需技能。",
                    prompt="完整技能规则",
                    tool_names=("skill_tool",),
                )
            ],
        )

    bundles = asyncio.run(registry.build_registered_agent_tool_bundles(make_ctx()))

    assert len(bundles) == 1
    assert bundles[0].skills == [
        types.AgentSkill(
            name="registered_skill",
            description="测试按需技能。",
            prompt="完整技能规则",
            tool_names=("skill_tool",),
        )
    ]

    registry.clear_registered_agent_tools()


def test_registered_agent_skill_prompt_receives_agent_tool_context():
    registry.clear_registered_agent_tools()

    @registry.register_agent_tool
    def build_skill(ctx):
        async def prompt(prompt_ctx):
            assert isinstance(prompt_ctx, registry.AgentToolContext)
            return f"registered session={prompt_ctx.session_id}"

        return registry.AgentToolBundle(
            name="registered_dynamic_skill",
            skills=[
                types.AgentSkill(
                    name="registered_dynamic_skill",
                    description="注册式动态技能。",
                    prompt=prompt,
                )
            ],
        )

    bundles = asyncio.run(registry.build_registered_agent_tool_bundles(make_ctx()))
    prompt = asyncio.run(skills.resolve_agent_skill_prompt(bundles[0].skills[0], make_ctx()))

    assert prompt == "registered session=group-1"

    registry.clear_registered_agent_tools()


def test_registered_agent_tool_accepts_single_tool_return():
    registry.clear_registered_agent_tools()

    @tool("echo_registered")
    async def echo_registered(text: str) -> str:
        """回显输入。"""
        return text

    @registry.register_agent_tool
    async def build_single_tool(ctx):
        return echo_registered

    bundles = asyncio.run(registry.build_registered_agent_tool_bundles(make_ctx()))

    assert len(bundles) == 1
    assert bundles[0].name == "build_single_tool"
    assert bundles[0].tools == [echo_registered]

    registry.clear_registered_agent_tools()


def test_registered_agent_tool_context_includes_recent_forward_messages():
    ctx = make_ctx()
    ctx.recent_forward_messages = [{"message_id": "101", "forward_id": "fwd-1"}]

    agent_ctx = registry._make_agent_tool_context(ctx)

    assert agent_ctx.recent_forward_messages == [{"message_id": "101", "forward_id": "fwd-1"}]


def test_loader_includes_registered_tools_in_statuses():
    registry.clear_registered_agent_tools()
    loader.get_user_tools_dir = lambda: Path("/__groupmate_agent_no_user_tools__")

    @registry.register_agent_tool
    def build_status_tool(ctx):
        @tool("status_tool")
        async def status_tool() -> str:
            """测试状态工具。"""
            return "ok"

        return registry.AgentToolBundle(
            name="status_bundle",
            tools=[status_tool],
            skills=[
                types.AgentSkill(
                    name="status_skill",
                    description="状态技能。",
                    prompt="状态技能规则",
                    tool_names=("status_tool",),
                )
            ],
        )

    statuses = asyncio.run(loader.list_optional_tool_statuses(make_ctx()))
    status = next(item for item in statuses if item.name == "status_bundle")

    assert status.enabled is True
    assert status.source.startswith("registered:")
    assert status.tool_names == ["status_tool"]
    assert status.skill_names == ["status_skill"]

    registry.clear_registered_agent_tools()


def test_user_tool_module_can_dynamically_register_a_lazy_skill(tmp_path, monkeypatch):
    registry.clear_registered_agent_tools()
    module_path = tmp_path / "lazy_user_tool.py"
    module_path.write_text(
        """
from langchain.tools import tool
from groupmate_agent_tool_pkg.agent.optional_tools.types import AgentSkill, OptionalToolBundle


async def build(ctx):
    @tool("lazy_user_tool")
    async def lazy_user_tool(text: str) -> str:
        \"\"\"测试动态目录工具。\"\"\"
        return text

    return OptionalToolBundle(
        name="lazy_user_bundle",
        tools=[lazy_user_tool],
        skills=[
            AgentSkill(
                name="lazy_user_skill",
                description="动态加载的用户技能。",
                prompt="完整用户技能规则",
                tool_names=("lazy_user_tool",),
            )
        ],
    )
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(loader, "get_user_tools_dir", lambda: tmp_path)

    bundles = asyncio.run(loader.load_optional_tool_bundles(make_ctx()))
    bundle = next(item for item in bundles if item.name == "lazy_user_bundle")

    assert [tool_item.name for tool_item in bundle.tools] == ["lazy_user_tool"]
    assert [skill.name for skill in bundle.skills] == ["lazy_user_skill"]


def test_agent_skill_index_only_contains_names_and_descriptions():
    skill = types.AgentSkill(
        name="weather",
        description="查询实时天气。",
        prompt="这是不应出现在索引里的完整天气规则",
        tool_names=("search_weather",),
    )

    index = skills.build_agent_skill_index([skill])

    assert "weather" in index
    assert "查询实时天气" in index
    assert "完整天气规则" not in index


def test_agent_skill_loader_resolves_async_dynamic_prompt():
    async def dynamic_prompt(ctx):
        return f"只允许查询会话 {ctx.session_id}"

    loader_tool = skills.create_agent_skill_loader_tool(
        [
            types.AgentSkill(
                name="dynamic",
                description="动态规则。",
                prompt=dynamic_prompt,
            )
        ],
        make_ctx(),
    )

    assert loader_tool is not None
    result = asyncio.run(loader_tool.ainvoke({"skill_name": "dynamic"}))
    assert result == "只允许查询会话 group-1"


def test_prepare_agent_skill_tools_keeps_legacy_tools_visible_and_gates_skill_tools():
    @tool("legacy_tool")
    async def legacy_tool() -> str:
        """旧工具。"""
        return "legacy"

    @tool("lazy_tool")
    async def lazy_tool() -> str:
        """按需工具。"""
        return "lazy"

    setup = skills.prepare_agent_skill_tools(
        [legacy_tool, lazy_tool],
        [
            types.AgentSkill(
                name="lazy_skill",
                description="按需技能。",
                prompt="完整规则",
                tool_names=("lazy_tool",),
            )
        ],
    )

    assert [tool_item.name for tool_item in setup.tools] == ["legacy_tool", "lazy_tool"]
    assert [tool_item.name for tool_item in setup.base_tools] == ["legacy_tool"]
    assert [tool_item.name for tool_item in setup.tools_by_skill["lazy_skill"]] == ["lazy_tool"]


def test_duplicate_skill_names_merge_tool_mappings_without_exposing_tools():
    @tool("first_tool")
    async def first_tool() -> str:
        """第一个工具。"""
        return "first"

    @tool("second_tool")
    async def second_tool() -> str:
        """第二个工具。"""
        return "second"

    setup = skills.prepare_agent_skill_tools(
        [first_tool, second_tool],
        [
            types.AgentSkill("shared", "首个描述。", "首个规则", ("first_tool",)),
            types.AgentSkill("shared", "第二个描述。", "第二个规则", ("second_tool",)),
        ],
    )

    assert setup.base_tools == []
    assert setup.skills == [types.AgentSkill("shared", "首个描述。", "首个规则", ("first_tool", "second_tool"))]
    assert [tool_item.name for tool_item in setup.tools_by_skill["shared"]] == ["first_tool", "second_tool"]
