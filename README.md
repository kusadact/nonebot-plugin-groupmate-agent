<div align="center">
  <a href="https://v2.nonebot.dev/store">
    <img src="https://raw.githubusercontent.com/fllesser/nonebot-plugin-template/refs/heads/resource/.docs/NoneBotPlugin.svg" width="310" alt="logo">
  </a>

## ✨ nonebot-plugin-ai-groupmate ✨

</div>

## 📖 介绍
这是一个基于 NoneBot2 的 AI 群友插件，使用 LangChain Agent 驱动群聊交互。

从 `2.3.0` 起，插件默认使用阿里云 DashScope / 通义千问 API：
主对话默认 `qwen3.5-plus`，群体记忆总结默认 `qwen-flash`，图片理解默认 `qwen-vl-max`，图片向量默认 `qwen3-vl-embedding`。
显式配置 `base_url`、`model`、`summary_*`、`multimodal_*` 或 `remote_media_embedding_*` 时会覆盖默认值。

核心能力包括：

- 记忆能力：聊天历史检索、群体认知档案、关系维护
- 聊天能力：群聊自动回复、主动发言、禁言辅助
- 学习表情包能力：表情包识别、检索、发送、相似图搜索、自动拉黑
- 扩展能力：用户可自行编写tools给agent使用

`2.3.0` 主要变化：

- 默认接入阿里云 DashScope / 通义千问，新增 `qwen_key` 作为通用 Key，收紧基础配置项
- Agent 可选工具拆分为独立模块，并支持从插件数据目录加载用户自定义工具；联网搜索会在健康检查通过后才注入 Agent prompt

## 💿 安装

直接用 `uv` 安装这个插件：

```bash
uv add git+https://github.com/kusadact/nonebot-plugin-ai-groupmate@dev
```

然后打开你的 NoneBot2 项目根目录下的 `pyproject.toml` 文件，在 `[tool.nonebot]` 部分追加写入：

```toml
plugins = ["nonebot_plugin_ai_groupmate"]
```

## ⚙️ 配置

### 基础配置

| 配置项 | 默认值 | 说明 |
|:--|:--|:--|
| `ai_groupmate__bot_name` | `bot` | bot 名称 |
| `ai_groupmate__reply_probability` | `0.01` | 群内主动发言概率 |
| `ai_groupmate__personality_setting` | 空 | 自定义人设补充 |
| `ai_groupmate__qwen_key` | 空 | 阿里云 DashScope API Key，默认供主对话、总结、多模态和图片 embedding 使用 |
| `ai_groupmate__remote_embedding_base_url` | 空 | 文本 embedding 地址 |
| `ai_groupmate__remote_embedding_model` | 空 | 文本 embedding 模型名 |
| `ai_groupmate__remote_embedding_api_key` | 空 | 文本 embedding API Key |
| `ai_groupmate__remote_rerank_base_url` | 空 | 文本 rerank 地址 |
| `ai_groupmate__remote_rerank_model` | 空 | 文本 rerank 模型名 |
| `ai_groupmate__remote_rerank_api_key` | 空 | 文本 rerank API Key |
| `ai_groupmate__qdrant_uri` | 空 | Qdrant 地址；不填则禁用 RAG / 表情包向量功能 |
| `ai_groupmate__qdrant_api_key` | 空 | Qdrant API Key |
| `ai_groupmate__tavily_api_key` | 空 | Tavily 搜索 API Key |

如果需要自定义各模型的 API 参数，可使用下面高级配置里的配置项。

<details>
<summary>高级配置</summary>

| 配置项 | 默认值 | 说明 |
|:--|:--|:--|
| `ai_groupmate__base_url` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 主对话模型 base URL |
| `ai_groupmate__model` | `qwen3.5-plus` | 主对话模型名，需支持 Tool Calling |
| `ai_groupmate__openai_base_url` | 空 | 主对话模型 base URL，配置后优先于 `base_url` |
| `ai_groupmate__openai_model` | 空 | 主对话模型名，配置后优先于 `model` |
| `ai_groupmate__openai_token` | 空 | 主对话模型 API Key；配置后优先于 `qwen_key` |
| `ai_groupmate__summary_base_url` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 总结模型 base URL |
| `ai_groupmate__summary_model` | `qwen-flash` | 群体认知档案总结模型 |
| `ai_groupmate__summary_api_key` | 空 | 总结模型 API Key |
| `ai_groupmate__multimodal_base_url` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 多模态模型 base URL |
| `ai_groupmate__multimodal_model` | `qwen-vl-max` | 图片理解模型 |
| `ai_groupmate__multimodal_api_key` | 空 | 多模态模型 API Key |
| `ai_groupmate__remote_media_embedding_provider` | `dashscope` | 图片 embedding 提供方：可选 `openai` / `dashscope` |
| `ai_groupmate__remote_media_embedding_base_url` | `https://dashscope.aliyuncs.com/api/v1/services/embeddings/multimodal-embedding/multimodal-embedding` | 图片 embedding 地址 |
| `ai_groupmate__remote_media_embedding_model` | `qwen3-vl-embedding` | 图片 embedding 模型名 |
| `ai_groupmate__remote_media_embedding_api_key` | 空 | 图片 embedding API Key |
| `ai_groupmate__chat_vector_dim` | `1024` | 聊天文本向量维度 |
| `ai_groupmate__media_vector_dim` | `2560` | 图片向量维度 |
| `ai_groupmate__remote_embedding_dimensions` | `1024` | 文本 embedding 维度 |
| `ai_groupmate__remote_media_embedding_dimensions` | `2560` | 图片 embedding 维度 |
| `ai_groupmate__media_search_recall_limit` | `6` | 表情包检索召回候选数 |
| `ai_groupmate__media_search_return_limit` | `5` | 表情包检索最终返回数 |
| `ai_groupmate__voice_enabled` | `false` | 是否启用语音用户工具 |
| `ai_groupmate__voice_base_url` | 空 | GPT-SoVITS 服务地址，供语音用户工具使用 |
| `ai_groupmate__voice_text_lang` | `zh` | 语音用户工具目标文本语言 |
| `ai_groupmate__voice_speed_factor` | `1.0` | 语音用户工具语速 |
| `ai_groupmate__voice_top_k` | `15` | 语音用户工具 GPT-SoVITS top_k |
| `ai_groupmate__voice_top_p` | `1.0` | 语音用户工具 GPT-SoVITS top_p |
| `ai_groupmate__voice_temperature` | `1.0` | 语音用户工具 GPT-SoVITS temperature |

</details>

<details>
<summary>自定义 Agent 工具</summary>

用户自定义工具应放在 bot 数据目录下的 `data/nonebot_plugin_ai_groupmate/tools`。

支持两种文件形式：

- `data/nonebot_plugin_ai_groupmate/tools/my_tool.py`
- `data/nonebot_plugin_ai_groupmate/tools/my_tool/__init__.py`

工具模块需要提供 `build(ctx)`，可选提供 `healthcheck(ctx)`；健康检查返回不通过时，该工具和它的 prompt 都不会注入 Agent。

```python
from langchain.tools import tool
from nonebot_plugin_ai_groupmate.agent.optional_tools import OptionalToolBundle, OptionalToolContext


async def healthcheck(ctx: OptionalToolContext) -> tuple[bool, str]:
    return True, "ok"


async def build(ctx: OptionalToolContext) -> OptionalToolBundle:
    @tool
    async def my_tool(text: str) -> str:
        """工具说明会提供给模型。"""
        return text

    return OptionalToolBundle(
        name="my_tool",
        tools=[my_tool],
        prompt="- 需要调用 my_tool 时，优先给出明确的 text 参数",
    )
```

长耗时工具可以在确认任务已经开始后使用 detached 生命周期，避免同一群的新请求取消后台任务：

```python
LONG_RUNNING_TRIGGERS = ["生成图片", "画图", "做图"]


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

    return OptionalToolBundle(name="image_tool", tools=[generate_image_tool])
```

`LONG_RUNNING_TRIGGERS` 是可选的模块级声明。用户直接 @bot 发起并命中这些关键词时，主 Agent 会在决策和 RAG 阶段保护该请求，不会被普通同群新消息取消；新的直达长任务请求仍可替换旧请求。
`ctx.create_detached_task(...)` 会负责注册 detached 状态、记录异常并在后台任务结束后清理状态。
不要只调用 `ctx.detach_request(...)` 后继续在当前工具协程里 `await` 长任务；当前 Agent worker 仍可能被取消。
</details>

## ✨ 当前分支能力

- **群聊 Agent**
  - 基于 LangChain Agent + Tool Calling 驱动群聊回复，主对话模型使用 OpenAI 兼容接口
  - 默认使用阿里云 DashScope / 通义千问；主对话、总结、多模态和图片 embedding 已内置默认模型和地址，填写 `qwen_key` 即可使用
  - 联网搜索、消息评论表情、禁言和计算器已拆为内置 Agent 可选工具模块；用户自定义工具从 `data/nonebot_plugin_ai_groupmate/tools` 加载；联网搜索不健康时不会注入工具和 prompt
  - 支持联网搜索、历史聊天检索、表情包搜索/发送、消息评论表情、关系更新和禁言管理；放入对应用户工具后可扩展更多能力
  - 每个群只保留最新待处理回复请求，旧请求会被取消
  - 直接 @/回复 场景会按编号聚合处理，逐条回复，不会互相抢上下文
  - 工具调用带 `request_id` 过期保护，旧请求不会继续搜索、发消息或更新关系
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
