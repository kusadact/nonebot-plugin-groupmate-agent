<div align="center">
  <a href="https://v2.nonebot.dev/store">
    <img src="https://raw.githubusercontent.com/fllesser/nonebot-plugin-template/refs/heads/resource/.docs/NoneBotPlugin.svg" width="310" alt="logo">
  </a>

## ✨ nonebot-plugin-groupmate-agent ✨

  <a href="https://codecov.io/gh/kusadact/nonebot-plugin-groupmate-agent/tree/dev">
    <img src="https://codecov.io/gh/kusadact/nonebot-plugin-groupmate-agent/branch/dev/graph/badge.svg" alt="codecov">
  </a>

</div>

## 📖 介绍
这是一个基于 NoneBot2 的群友 Agent 插件，使用 LangGraph 状态图执行群聊 Agent，并保留 LangChain Tool Calling / 工具生态。

`nonebot-plugin-groupmate-agent` 是从 `nonebot-plugin-ai-groupmate` 分离出来的独立插件线。当前版本不保留旧包名、旧配置前缀或旧数据目录入口；请使用新的模块名 `nonebot_plugin_groupmate_agent`、配置前缀 `groupmate_agent__` 和数据目录 `data/nonebot_plugin_groupmate_agent`。

从 `3.0.0` 起，主 Agent 执行器已从 LangChain `create_agent` 迁移到 LangGraph `StateGraph`：
模型仍使用 `ChatOpenAI` 及兼容的 Tool Calling，现有 `@tool` 工具、内置可选工具和用户自定义工具接口保持兼容。

从 `2.3.0` 起，插件默认使用阿里云 DashScope / 通义千问 API：
主对话默认 `qwen3.5-plus`，群体记忆总结默认 `qwen-flash`，图片理解默认 `qwen-vl-max`，图片向量默认 `qwen3-vl-embedding`。
显式配置 `base_url`、`model`、`summary_*`、`multimodal_*` 或 `remote_media_embedding_*` 时会覆盖默认值。

核心能力包括：

- 记忆能力：聊天历史检索、群体认知档案、关系维护
- 聊天能力：群聊自动回复、主动发言、禁言辅助
- 学习表情包能力：表情包识别、检索、发送、相似图搜索、自动拉黑
- 扩展能力：用户可自行编写tools给agent使用

`3.1.0` 主要变化：

- 新增内置 QQ 头像工具：Agent 可按 QQ 号、群名片、昵称、`我/自己`、`你/bot/机器人/bot 名` 匹配目标头像
- 用户只是要求“发头像 / 看原头像 / 把头像发群里”时，会直接调用 `send_qq_avatar_image` 发送原始 QQ 头像，避免误触发生图工具
- 用户要求“用头像做图 / 头像二创 / 拿头像当参考图”时，会调用 `fetch_qq_avatar_references` 下载头像并返回本地 `path`，供图片工具继续处理
- 新增内置 `describe_qq_avatar_image`：用户询问“头像长什么样 / 头像里是什么”时，可先获取头像 `path`，再交给多模态模型描述头像内容
- QQ 头像下载/发送和头像多模态描述拆成两个内置可选工具模块，核心能力默认启用，不需要额外暴露头像尺寸、缓存等调参项

`3.0.0` 主要变化：

- 主 Agent 从 LangChain `create_agent` 迁移为 LangGraph `StateGraph`，执行链路更明确，方便继续扩展分支、状态和工具策略
- 工具执行不再依赖旧的 LangChain `ToolNode` 默认行为，改为项目内 `graph.py` 显式处理工具调用、`ToolRuntime` 注入、请求过期保护和工具次数限制
- 工具调用上限迁入图执行器：全局每轮最多 20 次，`reply_user` 每轮 1 次，`send_meme_image` 每轮 1 次；可选工具声明的额外限制仍会合并生效
- `finish` 只标记本轮结束，不会提前跳过同一个 assistant message 中后续排队的 `reply_user`、`send_meme_image` 等工具调用，避免平行 tool calls 下漏发回复
- 直接请求、detached 长任务、多模态历史、RAG、表情包检索、关系维护、禁言和用户自定义工具能力保持在新图执行器上运行

`2.3.0` 主要变化：

- 默认接入阿里云 DashScope / 通义千问，新增 `qwen_key` 作为通用 Key，收紧基础配置项
- Agent 可选工具拆分为独立模块，并支持从插件数据目录加载用户自定义工具；联网搜索会在健康检查通过后才注入 Agent prompt

## 💿 安装

直接用 `uv` 安装这个插件：

```bash
uv add git+https://github.com/kusadact/nonebot-plugin-groupmate-agent@dev
```

然后打开你的 NoneBot2 项目根目录下的 `pyproject.toml` 文件，在 `[tool.nonebot]` 部分追加写入：

```toml
plugins = ["nonebot_plugin_groupmate_agent"]
```

## ⚙️ 配置

### 基础配置

| 配置项 | 默认值 | 说明 |
|:--|:--|:--|
| `groupmate_agent__bot_name` | `bot` | bot 名称 |
| `groupmate_agent__reply_probability` | `0.01` | 群内主动发言概率 |
| `groupmate_agent__personality_setting` | 空 | 自定义人设补充 |
| `groupmate_agent__qwen_key` | 空 | 阿里云 DashScope API Key，默认供主对话、总结、多模态和图片 embedding 使用 |
| `groupmate_agent__remote_embedding_base_url` | 空 | 文本 embedding 地址 |
| `groupmate_agent__remote_embedding_model` | 空 | 文本 embedding 模型名 |
| `groupmate_agent__remote_embedding_api_key` | 空 | 文本 embedding API Key |
| `groupmate_agent__remote_rerank_base_url` | 空 | 文本 rerank 地址 |
| `groupmate_agent__remote_rerank_model` | 空 | 文本 rerank 模型名 |
| `groupmate_agent__remote_rerank_api_key` | 空 | 文本 rerank API Key |
| `groupmate_agent__qdrant_uri` | 空 | Qdrant 地址；不填则禁用 RAG / 表情包向量功能 |
| `groupmate_agent__qdrant_api_key` | 空 | Qdrant API Key |
| `groupmate_agent__tavily_api_key` | 空 | Tavily 搜索 API Key |

如果需要自定义各模型的 API 参数，可使用下面高级配置里的配置项。

用户自定义工具应放在 bot 数据目录下的 `data/nonebot_plugin_groupmate_agent/tools`。
可参考工具仓库 [`kusadact/groupmate-agent-tools`](https://github.com/kusadact/groupmate-agent-tools)，其中存放了适用于本插件的用户自定义 Agent 工具实例。

<details>
<summary>高级配置</summary>

| 配置项 | 默认值 | 说明 |
|:--|:--|:--|
| `groupmate_agent__base_url` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 主对话模型 base URL |
| `groupmate_agent__model` | `qwen3.5-plus` | 主对话模型名，需支持 Tool Calling |
| `groupmate_agent__openai_base_url` | 空 | 主对话模型 base URL，配置后优先于 `base_url` |
| `groupmate_agent__openai_model` | 空 | 主对话模型名，配置后优先于 `model` |
| `groupmate_agent__openai_token` | 空 | 主对话模型 API Key；配置后优先于 `qwen_key` |
| `groupmate_agent__summary_base_url` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 总结模型 base URL |
| `groupmate_agent__summary_model` | `qwen-flash` | 群体认知档案总结模型 |
| `groupmate_agent__summary_api_key` | 空 | 总结模型 API Key |
| `groupmate_agent__multimodal_base_url` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 多模态模型 base URL |
| `groupmate_agent__multimodal_model` | `qwen-vl-max` | 图片理解模型 |
| `groupmate_agent__multimodal_api_key` | 空 | 多模态模型 API Key |
| `groupmate_agent__remote_media_embedding_provider` | `dashscope` | 图片 embedding 提供方：可选 `openai` / `dashscope` |
| `groupmate_agent__remote_media_embedding_base_url` | `https://dashscope.aliyuncs.com/api/v1/services/embeddings/multimodal-embedding/multimodal-embedding` | 图片 embedding 地址 |
| `groupmate_agent__remote_media_embedding_model` | `qwen3-vl-embedding` | 图片 embedding 模型名 |
| `groupmate_agent__remote_media_embedding_api_key` | 空 | 图片 embedding API Key |
| `groupmate_agent__chat_vector_dim` | `1024` | 聊天文本向量维度 |
| `groupmate_agent__media_vector_dim` | `2560` | 图片向量维度 |
| `groupmate_agent__remote_embedding_dimensions` | `1024` | 文本 embedding 维度 |
| `groupmate_agent__remote_media_embedding_dimensions` | `2560` | 图片 embedding 维度 |
| `groupmate_agent__media_search_recall_limit` | `6` | 表情包检索召回候选数 |
| `groupmate_agent__media_search_return_limit` | `5` | 表情包检索最终返回数 |

</details>

<details>
<summary>自定义 Agent 工具</summary>

支持两种文件形式：

- `data/nonebot_plugin_groupmate_agent/tools/my_tool.py`
- `data/nonebot_plugin_groupmate_agent/tools/my_tool/__init__.py`

工具模块需要提供 `build(ctx)`，可选提供 `healthcheck(ctx)`；两者都可以是同步或异步函数。健康检查返回不通过时，该工具和它的 prompt 都不会注入 Agent。

```python
from typing import Any

from langchain.tools import ToolRuntime, tool
from nonebot_plugin_groupmate_agent.agent.optional_tools import OptionalToolBundle, OptionalToolContext, ToolLimitSpec


async def healthcheck(ctx: OptionalToolContext) -> tuple[bool, str]:
    return True, "ok"


async def build(ctx: OptionalToolContext) -> OptionalToolBundle:
    @tool
    async def my_tool(text: str, runtime: ToolRuntime[Any]) -> str:
        """工具说明会提供给模型。"""
        # runtime 由 Agent 图执行器注入，不会暴露给模型填写。
        return f"{runtime.context.session_id}: {text}"

    return OptionalToolBundle(
        name="my_tool",
        tools=[my_tool],
        prompt="- 需要调用 my_tool 时，优先给出明确的 text 参数",
        tool_limits=[ToolLimitSpec(tool_name="my_tool", run_limit=1)],
    )
```

如果工具函数声明了 `runtime: ToolRuntime[Any]` 参数，图执行器会自动注入运行时上下文；可以从 `runtime.context.session_id`、`runtime.context.request_id` 读取当前会话和请求信息。`tool_limits` 可限制本轮工具调用次数，`tool_name=None` 表示调整全局工具调用上限。

也支持从其他 NoneBot 插件中注册工具。只要注册代码所在模块被 NoneBot 加载，工具就会在每次创建 Agent 时按当前上下文动态加入：

```python
from langchain.tools import tool
from nonebot import require

require("nonebot_plugin_groupmate_agent")

from nonebot_plugin_groupmate_agent.agent import (
    AgentToolBundle,
    AgentToolContext,
    register_agent_tool,
)
from nonebot_plugin_groupmate_agent.agent.optional_tools import ToolLimitSpec


@register_agent_tool
def build_my_plugin_tools(ctx: AgentToolContext) -> AgentToolBundle:
    @tool("get_current_session_id")
    async def get_current_session_id() -> str:
        """获取当前会话 ID。"""
        return ctx.session_id

    return AgentToolBundle(
        name="my_plugin_tools",
        tools=[get_current_session_id],
        instructions=["- 需要知道当前群/会话 ID 时，调用 `get_current_session_id`"],
        tool_limits=[ToolLimitSpec(tool_name="get_current_session_id", run_limit=1)],
    )
```

在其他插件模块顶层导入本插件的注册 API 前，必须先调用 `require("nonebot_plugin_groupmate_agent")`，确保本插件在 NoneBot 插件加载上下文中初始化完成。

注册式 factory 可以返回单个 LangChain tool、tool 列表、`AgentToolBundle`、`OptionalToolBundle` 或 `None`。`AgentToolContext` 会提供当前 `session_id`、`request_id`、触发用户、群成员接口、历史消息、direct reply 状态、权限、配置、模型、`send_target`、`bot/event` 和 detached 生命周期方法。需要按上下文禁用工具时，可以返回 `None` 或空 bundle；`/ai tools` 会显示注册式工具的启用状态。

长耗时工具可以在确认任务已经开始后使用 detached 生命周期，让后台任务脱离当前 Agent 等待，当前请求结束后仍可发送结果：

```python
async def build(ctx: OptionalToolContext) -> OptionalToolBundle:
    async def run_long_job(prompt: str) -> None:
        # 执行耗时任务，例如生成图片。
        result = await generate_image(prompt)
        if ctx.can_continue and not await ctx.can_continue():
            return
        await send_result(result)
        if ctx.mark_sent:
            ctx.mark_sent()

    @tool
    async def generate_image_tool(prompt: str) -> str:
        """提交图片生成任务。"""
        if ctx.create_detached_task:
            ctx.create_detached_task(run_long_job(prompt), "image generation")
            return "图片生成任务已开始，完成后会发送结果。"
        return "当前请求不支持后台长任务。"

    return OptionalToolBundle(
        name="image_tool",
        tools=[generate_image_tool],
        tool_limits=[ToolLimitSpec(tool_name="generate_image_tool", run_limit=1)],
    )
```

`ctx.create_detached_task(...)` 会负责注册 detached 状态、记录异常并在后台任务结束后清理状态。
不要只调用 `ctx.detach_request(...)` 后继续在当前工具协程里 `await` 长任务；这会继续占用当前 Agent worker，并且仍会受 Agent 超时影响。
</details>

## ✨ 当前分支能力

- **群聊 Agent**
  - 基于 LangGraph 状态图 + LangChain Tool Calling 驱动群聊回复，主对话模型使用 OpenAI 兼容接口
  - 默认使用阿里云 DashScope / 通义千问；主对话、总结、多模态和图片 embedding 已内置默认模型和地址，填写 `qwen_key` 即可使用
  - 联网搜索、消息评论表情、禁言、QQ 头像参考图、QQ 头像内容描述和计算器已拆为内置 Agent 可选工具模块；用户自定义工具从 `data/nonebot_plugin_groupmate_agent/tools` 加载；联网搜索不健康时不会注入工具和 prompt
  - 支持联网搜索、历史聊天检索、表情包搜索/发送、消息评论表情、QQ 头像参考图、QQ 头像内容描述、关系更新和禁言管理；放入对应用户工具后可扩展更多能力
  - 直接 @/回复 请求会各自启动独立 Agent task，不会因同群新消息过期，也不会被前一个直达请求阻塞
  - 普通概率回复按群内小队列限流；有直达请求运行时会跳过普通概率回复，避免群聊刷屏堆积
  - 直接 @/回复 场景会按本轮消息回复；旧直达消息只作为背景，不会被后续直达请求再次执行
  - 工具调用带 `request_id` 活跃状态保护；请求结束或 detached 清理后不会继续搜索、发消息或更新关系
  - 当前触发消息会作为本轮重点注入 prompt，降低顺着其他人支线接话的概率
  - 多段回复使用一次 `reply_user` 调用，按换行由程序串行拆成多条消息
  - `reply_user` 会把实际发送段落返回给 Agent，方便本轮后续工具知道刚刚说过什么
  - Agent 可选调用 `add_message_emoji_like` 给合适的最近消息添加 NapCat 评论表情，每轮最多一次
  - bot 有群管理权限时会注入 `mute_user` 工具，禁言 / 解除禁言成功后会写入 `ChatHistory`
- **群体认知档案**
  - 每 6 小时自动汇总群内常见话题、成员特征、内部梗和群氛围
- **聊天 RAG**
  - 聊天历史写入 Qdrant，检索结果会再走 rerank
  - Qdrant 不可用时自动降级，不会直接把 bot 拉死
- **表情包学习与检索**
  - 群图片先用多模态模型判定是否为表情包，再进入媒体向量库
  - 支持文字找图，也支持按历史消息 ID 找相似图
  - 图片处理已改为后台异步，不阻塞主回复链路
- **表情包拉黑**
  - superuser 回复 bot 发出的表情包消息，并带有“不能 / 不行 / 不可以 / 别发”等否定反馈时，会自动拉黑
  - 被拉黑表情包会同时从 SQL 标记并在 Qdrant 检索侧过滤
- **好感度**
  - 使用 `favorability_raw` + `favorability` 双分值
  - 带状态机、每日上限、bank、bypass、道歉衰减、惩罚冷却
- **运维**
  - `/ai on|off|status` 可直接控制插件状态
  - Agent 工具内部数据库写入使用独立 session，降低异步工具并发导致的事务状态冲突
  - 过期媒体和磁盘孤儿文件会定期清理
  - 多模态永久失败图片会自动跳过，避免无限重试

## 🧭 使用

### 触发方式

- `@bot`、回复 bot、直接点名 bot，都会触发回复判断
- 也会按 `reply_probability` 概率主动发言
- 图片会后台异步入库，不再阻塞主回复

### 管理指令

| 指令 | 说明 |
|:--|:--|
| `/ai on` | 打开插件，仅 superuser 可用 |
| `/ai off` | 关闭插件，仅 superuser 可用 |
| `/ai status` | 查看插件状态与 Qdrant 连通性 |
| `/ai tools` | 查看当前会注入 Agent 的可选工具，以及被跳过的工具原因 |
| `/词频 <统计天数>` | 生成个人词频词云 |
| `/群词频 <统计天数>` | 生成群词频词云 |

### 表情包拉黑

当前分支支持“回复式拉黑”：

1. bot 先发出一张表情包
2. superuser 回复这条消息
3. 回复内容包含 `不可以 / 不行 / 不能 / 别发 / 别再发 / 不要这张` 等否定反馈
4. 该表情包会被标记为黑名单，并从后续检索中排除

## ✅ 代办清单

- [ ] 将主 Agent 的图片安全错误识别抽象成 provider-neutral 逻辑，避免偏向单一模型供应商的错误码。

## 🙏 致谢

- 原项目：[`yaowan233/nonebot-plugin-ai-groupmate`](https://github.com/yaowan233/nonebot-plugin-ai-groupmate)
- NoneBot2 社区及相关插件作者
