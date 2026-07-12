from typing import Any

from langchain.tools import ToolRuntime, tool
from langchain_tavily import TavilySearch
from nonebot.log import logger

from ...reply_guard import can_request_continue
from .types import AgentSkill, OptionalToolBundle, OptionalToolContext

PROMPT = "- 外部知识、缩写、术语：优先 `search_web`"


async def healthcheck(ctx: OptionalToolContext) -> tuple[bool, str]:
    if not (ctx.config.tavily_api_key or "").strip():
        return False, "missing tavily_api_key"
    return True, "ok"


async def build(ctx: OptionalToolContext) -> OptionalToolBundle:
    tavily_search = TavilySearch(max_results=3, tavily_api_key=ctx.config.tavily_api_key)

    @tool("search_web")
    async def search_web(query: str, runtime: ToolRuntime[Any]) -> str:
        """
        用于搜索最新的实时信息。当你需要最新的事实信息、天气或新闻时使用。
        输入：需要搜索的内容。
        """
        runtime_context = runtime.context
        if runtime_context.request_id is not None and not await can_request_continue(
            runtime_context.session_id, runtime_context.request_id
        ):
            return "请求已过期，已取消搜索。"
        if not tavily_search:
            logger.error("没有配置 tavily_api_key, 无法进行搜索")
            return "没有配置 tavily_api_key, 无法进行搜索"
        results = await tavily_search.ainvoke(query)
        return results

    return OptionalToolBundle(
        name="web_search",
        tools=[search_web],
        skills=[
            AgentSkill(
                name="web_search",
                description="查询外部知识、天气、新闻和其他实时网络信息。",
                prompt=PROMPT,
                tool_names=("search_web",),
            )
        ],
    )
