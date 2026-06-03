"""LangGraph-based agent executor for the groupmate chat tools."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from nonebot.log import logger

from ..reply_guard import can_request_continue

DEFAULT_MAX_TOOL_COUNT = 20


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    session_id: str
    request_id: str | None
    tool_count: int
    tool_run_counts: dict[str, int]
    called_finish: int


@dataclass(frozen=True)
class GraphToolLimit:
    tool_name: str | None
    run_limit: int


@dataclass
class _AgentContext:
    session_id: str
    request_id: str | None


def make_agent_state(
    messages: Sequence[BaseMessage],
    session_id: str,
    request_id: str | None,
) -> AgentState:
    return {
        "messages": list(messages),
        "session_id": session_id,
        "request_id": request_id,
        "tool_count": 0,
        "tool_run_counts": {},
        "called_finish": 0,
    }


def _normalize_limits(
    tool_limits: Sequence[GraphToolLimit] | None,
) -> tuple[int, dict[str, int]]:
    global_limit = DEFAULT_MAX_TOOL_COUNT
    named_limits: dict[str, int] = {}

    for spec in tool_limits or ():
        run_limit = max(0, int(spec.run_limit))
        if spec.tool_name is None:
            global_limit = min(global_limit, run_limit)
            continue

        current = named_limits.get(spec.tool_name)
        named_limits[spec.tool_name] = run_limit if current is None else min(current, run_limit)

    return global_limit, named_limits


def _build_tool_runtime(ctx: _AgentContext, tool_call_id: str, args: dict[str, Any]) -> ToolRuntime[Any, Any]:
    return ToolRuntime(
        state={"session_id": ctx.session_id, "request_id": ctx.request_id},
        context=ctx,
        config=RunnableConfig(),
        stream_writer=lambda _: None,
        tool_call_id=tool_call_id,
        store=None,
    )


def _tool_accepts_runtime(tool_item: BaseTool) -> bool:
    args = getattr(tool_item, "args", None)
    if isinstance(args, dict) and "runtime" in args:
        return True

    try:
        schema = tool_item.get_input_schema()
    except Exception:
        return False

    fields = getattr(schema, "model_fields", None)
    return isinstance(fields, dict) and "runtime" in fields


def _make_agent_node(model: Any, tools: list[BaseTool], system_prompt: str) -> Any:
    bound_model = model.bind_tools(tools)

    async def agent_node(state: AgentState) -> dict[str, Any]:
        response: AIMessage = await bound_model.ainvoke([*state["messages"]])
        if not isinstance(response, AIMessage):
            response = AIMessage(content=str(getattr(response, "content", response)))
        return {"messages": [response], "called_finish": 0}

    async def prompted_agent_node(state: AgentState) -> dict[str, Any]:
        response: AIMessage = await bound_model.ainvoke(
            [SystemMessage(content=system_prompt), *state["messages"]],
        )
        if not isinstance(response, AIMessage):
            response = AIMessage(content=str(getattr(response, "content", response)))
        return {"messages": [response], "called_finish": 0}

    return prompted_agent_node if system_prompt.strip() else agent_node


def _make_tool_node(
    tools_by_name: dict[str, BaseTool],
    *,
    global_tool_limit: int,
    named_tool_limits: dict[str, int],
) -> Any:
    async def tool_node(state: AgentState) -> dict[str, Any]:
        messages = state["messages"]
        last_message = messages[-1]
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return {}

        results: list[ToolMessage] = []
        tool_count = state.get("tool_count", 0)
        tool_run_counts = dict(state.get("tool_run_counts", {}))
        called_finish = 0
        session_id = state["session_id"]
        request_id = state["request_id"]
        agent_ctx = _AgentContext(session_id=session_id, request_id=request_id)

        for index, tool_call in enumerate(last_message.tool_calls, 1):
            name = str(tool_call.get("name") or "")
            tool_call_id = str(tool_call.get("id") or f"{name}-{index}")

            if name == "finish":
                called_finish = 1
                results.append(ToolMessage(content="", tool_call_id=tool_call_id))
                continue

            if tool_count >= global_tool_limit:
                results.append(ToolMessage(content="本轮工具调用次数已达上限，停止执行。", tool_call_id=tool_call_id))
                break

            tool_count += 1

            if request_id and not await can_request_continue(session_id, request_id):
                results.append(ToolMessage(content="请求已过期，已取消执行。", tool_call_id=tool_call_id))
                continue

            named_limit = named_tool_limits.get(name)
            current_tool_count = tool_run_counts.get(name, 0)
            if named_limit is not None and current_tool_count >= named_limit:
                results.append(
                    ToolMessage(
                        content=f"工具 `{name}` 本轮调用次数已达上限，已跳过。",
                        tool_call_id=tool_call_id,
                    )
                )
                continue

            tool = tools_by_name.get(name)
            if tool is None:
                results.append(ToolMessage(content=f"未知工具: {name}", tool_call_id=tool_call_id))
                continue

            tool_run_counts[name] = current_tool_count + 1

            raw_args = tool_call.get("args", {})
            args = raw_args if isinstance(raw_args, dict) else {}
            runtime = _build_tool_runtime(agent_ctx, tool_call_id, args)
            tool_input: Any = args
            if _tool_accepts_runtime(tool):
                tool_input = {**args, "runtime": runtime}
            elif not isinstance(raw_args, dict):
                tool_input = raw_args

            try:
                result = await tool.ainvoke(tool_input, runtime=runtime)
            except Exception as e:
                logger.exception(f"[Agent] 工具执行失败 {name}")
                result = f"工具执行出错: {e}"

            results.append(ToolMessage(content=str(result), tool_call_id=tool_call_id))

        return {
            "messages": results,
            "tool_count": tool_count,
            "tool_run_counts": tool_run_counts,
            "called_finish": called_finish,
        }

    return tool_node


def _should_call_tools(state: AgentState) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "end"


def _make_should_continue(global_tool_limit: int) -> Any:
    def should_continue(state: AgentState) -> str:
        if state.get("called_finish", 0) > 0:
            return "end"
        if state.get("tool_count", 0) >= global_tool_limit:
            logger.info("[Agent] 已达最大工具调用次数，结束本轮对话")
            return "end"
        return "agent"

    return should_continue


def build_chat_graph(
    model: Any,
    tools: list[BaseTool],
    system_prompt: str,
    *,
    tool_limits: Sequence[GraphToolLimit] | None = None,
) -> Any:
    global_tool_limit, named_tool_limits = _normalize_limits(tool_limits)
    tools_by_name: dict[str, BaseTool] = {}
    for tool in tools:
        if tool.name in tools_by_name:
            logger.warning(f"[Agent] 工具名重复，后加载的工具会覆盖前者: {tool.name}")
        tools_by_name[tool.name] = tool

    builder = StateGraph(AgentState)
    builder.add_node("agent", _make_agent_node(model, tools, system_prompt))
    builder.add_node(
        "tools",
        _make_tool_node(
            tools_by_name,
            global_tool_limit=global_tool_limit,
            named_tool_limits=named_tool_limits,
        ),
    )
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", _should_call_tools, {"tools": "tools", "end": END})
    builder.add_conditional_edges("tools", _make_should_continue(global_tool_limit), {"agent": "agent", "end": END})
    return builder.compile()
