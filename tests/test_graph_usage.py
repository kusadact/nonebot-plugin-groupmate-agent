import asyncio
import sys
from types import ModuleType

from langchain.tools import tool
from langchain_core.messages import AIMessage

from tests.helpers import install_package_stub, load_module

install_package_stub("graph_pkg")
install_package_stub("graph_pkg.agent")

reply_guard_module = ModuleType("graph_pkg.reply_guard")


async def _can_request_continue(session_id, request_id):
    return True


reply_guard_module.can_request_continue = _can_request_continue
sys.modules["graph_pkg.reply_guard"] = reply_guard_module

graph = load_module("graph_pkg.agent.graph", "agent/graph.py")


def test_llm_usage_parser_reads_usage_metadata_cache_details():
    message = AIMessage(
        content="ok",
        usage_metadata={
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
            "input_token_details": {"cache_read": 30, "cache_creation": 10},
        },
    )
    state = graph.make_agent_state([], "group-1", "req-1")

    usage = graph._log_llm_token_usage(message, state)

    assert usage == {
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "cached_tokens": 30,
        "cache_creation_tokens": 10,
        "total_tokens": 120,
    }


def test_llm_usage_parser_reads_response_metadata_token_usage():
    message = AIMessage(
        content="ok",
        response_metadata={
            "token_usage": {
                "prompt_tokens": 40,
                "completion_tokens": 6,
                "total_tokens": 46,
                "prompt_tokens_details": {"cached_tokens": 12, "cache_creation_input_tokens": 4},
            }
        },
    )
    state = graph.make_agent_state([], "group-1", "req-1")

    usage = graph._log_llm_token_usage(message, state)

    assert usage == {
        "prompt_tokens": 40,
        "completion_tokens": 6,
        "cached_tokens": 12,
        "cache_creation_tokens": 4,
        "total_tokens": 46,
    }


def test_llm_usage_parser_reads_raw_usage_metadata():
    message = AIMessage(
        content="ok",
        response_metadata={
            "usage": {
                "prompt_tokens": 70,
                "completion_tokens": 8,
                "total_tokens": 78,
                "prompt_tokens_details": {"cache_read": 20},
            }
        },
    )
    state = graph.make_agent_state([], "group-1", "req-1")

    usage = graph._log_llm_token_usage(message, state)

    assert usage == {
        "prompt_tokens": 70,
        "completion_tokens": 8,
        "cached_tokens": 20,
        "cache_creation_tokens": 0,
        "total_tokens": 78,
    }


def test_skill_tools_are_hidden_until_the_skill_is_active():
    @tool("load_agent_skill")
    async def load_agent_skill(skill_name: str) -> str:
        """加载技能。"""
        return f"loaded {skill_name}"

    @tool("weather_tool")
    async def weather_tool() -> str:
        """查询天气。"""
        return "sunny"

    node = graph._make_tool_node(
        {"load_agent_skill": load_agent_skill, "weather_tool": weather_tool},
        base_tools=[load_agent_skill],
        tools_by_skill={"weather": [weather_tool]},
        global_tool_limit=20,
        named_tool_limits={},
    )
    hidden_state = graph.make_agent_state(
        [AIMessage(content="", tool_calls=[{"name": "weather_tool", "args": {}, "id": "hidden"}])],
        "group-1",
        "req-1",
    )

    hidden_result = asyncio.run(node(hidden_state))

    assert "当前未启用" in hidden_result["messages"][0].content
    assert hidden_result["active_skills"] == []

    load_state = graph.make_agent_state(
        [
            AIMessage(
                content="",
                tool_calls=[{"name": "load_agent_skill", "args": {"skill_name": "weather"}, "id": "load"}],
            )
        ],
        "group-1",
        "req-1",
    )
    load_result = asyncio.run(node(load_state))

    assert load_result["active_skills"] == ["weather"]
    assert load_result["messages"][0].content == "loaded weather"

    active_state = graph.make_agent_state(
        [AIMessage(content="", tool_calls=[{"name": "weather_tool", "args": {}, "id": "active"}])],
        "group-1",
        "req-1",
    )
    active_state["active_skills"] = load_result["active_skills"]
    active_result = asyncio.run(node(active_state))

    assert active_result["messages"][0].content == "sunny"

    repeated_state = graph.make_agent_state(
        [
            AIMessage(
                content="",
                tool_calls=[{"name": "load_agent_skill", "args": {"skill_name": "weather"}, "id": "repeat"}],
            )
        ],
        "group-1",
        "req-1",
    )
    repeated_state["active_skills"] = ["weather"]
    repeated_result = asyncio.run(node(repeated_state))

    assert repeated_result["active_skills"] == ["weather"]
    assert "无需重复读取" in repeated_result["messages"][0].content


def test_agent_node_binds_only_tools_for_active_skills():
    @tool("base_tool")
    async def base_tool() -> str:
        """基础工具。"""
        return "base"

    @tool("lazy_tool")
    async def lazy_tool() -> str:
        """按需工具。"""
        return "lazy"

    class BoundModel:
        async def ainvoke(self, messages):
            return AIMessage(content="done")

    class RecordingModel:
        def __init__(self):
            self.bound_tool_names = []

        def bind_tools(self, tools):
            self.bound_tool_names.append([tool_item.name for tool_item in tools])
            return BoundModel()

    model = RecordingModel()
    node = graph._make_agent_node(
        model,
        [base_tool],
        [],
        {"lazy": [lazy_tool]},
    )

    initial_state = graph.make_agent_state([], "group-1", "req-1")
    asyncio.run(node(initial_state))
    active_state = graph.make_agent_state([], "group-1", "req-2")
    active_state["active_skills"] = ["lazy"]
    asyncio.run(node(active_state))

    assert model.bound_tool_names == [["base_tool"], ["base_tool", "lazy_tool"]]


def test_failed_skill_loader_does_not_activate_tools():
    @tool("load_agent_skill")
    async def load_agent_skill(skill_name: str) -> str:
        """加载技能。"""
        raise RuntimeError("broken prompt")

    @tool("lazy_tool")
    async def lazy_tool() -> str:
        """按需工具。"""
        return "lazy"

    node = graph._make_tool_node(
        {"load_agent_skill": load_agent_skill, "lazy_tool": lazy_tool},
        base_tools=[load_agent_skill],
        tools_by_skill={"lazy": [lazy_tool]},
        global_tool_limit=20,
        named_tool_limits={},
    )
    state = graph.make_agent_state(
        [
            AIMessage(
                content="",
                tool_calls=[{"name": "load_agent_skill", "args": {"skill_name": "lazy"}, "id": "load"}],
            )
        ],
        "group-1",
        "req-1",
    )

    result = asyncio.run(node(state))

    assert result["active_skills"] == []
    assert "工具执行出错" in result["messages"][0].content
