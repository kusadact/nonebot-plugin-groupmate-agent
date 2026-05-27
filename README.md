<div align="center">
  <a href="https://v2.nonebot.dev/store">
    <img src="https://raw.githubusercontent.com/fllesser/nonebot-plugin-template/refs/heads/resource/.docs/NoneBotPlugin.svg" width="310" alt="logo">
  </a>

## ✨ nonebot-plugin-ai-groupmate ✨

</div>

## 📖 介绍
这是一个基于 NoneBot2 的 AI 群友插件，使用 LangChain Agent 驱动群聊交互。

核心能力包括：

- 记忆能力：聊天历史检索、群体认知档案、关系维护
- 聊天能力：群聊自动回复、主动发言、年度报告、禁言辅助
- 学习表情包能力：表情包识别、检索、发送、相似图搜索、自动拉黑

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
| `ai_groupmate__tavily_api_key` | 空 | Tavily 搜索 API Key |
| `ai_groupmate__qwen_token` | 空 | DashScope 通用 API Key，`summary` / `multimodal` 可回退使用 |
| `ai_groupmate__summary_base_url` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 总结模型 base URL |
| `ai_groupmate__summary_model` | `qwen-flash` | 群体认知档案总结模型 |
| `ai_groupmate__summary_api_key` | 空 | 总结模型 API Key |
| `ai_groupmate__openai_base_url` | 空 | 主对话模型 base URL |
| `ai_groupmate__openai_model` | 空 | 主对话模型名，需支持 Tool Calling |
| `ai_groupmate__openai_token` | 空 | 主对话模型 API Key |
| `ai_groupmate__multimodal_base_url` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 多模态模型 base URL |
| `ai_groupmate__multimodal_model` | `qwen-vl-max` | 图片理解模型 |
| `ai_groupmate__multimodal_api_key` | 空 | 多模态模型 API Key |
| `ai_groupmate__remote_embedding_base_url` | 空 | 文本 embedding 地址 |
| `ai_groupmate__remote_embedding_model` | 空 | 文本 embedding 模型名 |
| `ai_groupmate__remote_embedding_api_key` | 空 | 文本 embedding API Key |
| `ai_groupmate__remote_media_embedding_provider` | `aliyun_dashscope` | 图片 embedding 提供方：`openai` / `aliyun_dashscope` |
| `ai_groupmate__remote_media_embedding_base_url` | 空 | 图片 embedding 地址 |
| `ai_groupmate__remote_media_embedding_model` | 空 | 图片 embedding 模型名 |
| `ai_groupmate__remote_media_embedding_api_key` | 空 | 图片 embedding API Key |
| `ai_groupmate__remote_rerank_base_url` | 空 | 文本 rerank 地址 |
| `ai_groupmate__remote_rerank_model` | 空 | 文本 rerank 模型名 |
| `ai_groupmate__remote_rerank_api_key` | 空 | 文本 rerank API Key |
| `ai_groupmate__qdrant_uri` | 空 | Qdrant 地址；不填则禁用 RAG / 表情包向量功能 |
| `ai_groupmate__qdrant_api_key` | 空 | Qdrant API Key |
| `ai_groupmate__voice_enabled` | `false` | 是否启用语音工具 |
| `ai_groupmate__voice_base_url` | 空 | GPT-SoVITS 服务地址 |

<details>
<summary>高级配置</summary>

| 配置项 | 默认值 | 说明 |
|:--|:--|:--|
| `ai_groupmate__chat_vector_dim` | `1024` | 聊天文本向量维度 |
| `ai_groupmate__media_vector_dim` | `2560` | 图片向量维度 |
| `ai_groupmate__remote_embedding_dimensions` | `1024` | 文本 embedding 维度 |
| `ai_groupmate__remote_media_embedding_dimensions` | `2560` | 图片 embedding 维度 |
| `ai_groupmate__media_search_recall_limit` | `6` | 表情包检索召回候选数 |
| `ai_groupmate__media_search_return_limit` | `5` | 表情包检索最终返回数 |
| `ai_groupmate__voice_text_lang` | `zh` | 目标文本语言 |
| `ai_groupmate__voice_speed_factor` | `1.0` | 语速 |
| `ai_groupmate__voice_top_k` | `15` | GPT-SoVITS top_k |
| `ai_groupmate__voice_top_p` | `1.0` | GPT-SoVITS top_p |
| `ai_groupmate__voice_temperature` | `1.0` | GPT-SoVITS temperature |

</details>

## ✨ 当前分支能力

- **群聊 Agent**
  - 基于 LangChain Agent + Tool Calling 驱动群聊回复，主对话模型使用 OpenAI 兼容接口
  - 支持联网搜索、历史聊天检索、表情包搜索/发送、消息评论表情、语音发送、年度报告、关系更新和禁言管理；语音工具支持 GPT-SoVITS 接口，健康检查通过时才会注入 Agent，插件直接发送 API 返回的音频
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
| `/词频 <统计天数>` | 生成个人词频词云 |
| `/群词频 <统计天数>` | 生成群词频词云 |

### 表情包拉黑

当前分支支持“回复式拉黑”：

1. bot 先发出一张表情包
2. superuser 回复这条消息
3. 回复内容包含 `不可以 / 不行 / 不能 / 别发 / 别再发 / 不要这张` 等否定反馈
4. 该表情包会被标记为黑名单，并从后续检索中排除

## 📌 与原项目差异

### 记忆与向量层

- 当前 fork 将主对话、总结、图片理解、文本 embedding 的接入拆成独立配置，按用途分别接不同 `base_url`、`model` 和 API Key。
- 表情包数据新增 `blocked` 标记，检索和清理都会过滤黑名单。
- 表情包检索支持文字找图和按历史消息图找相似图，并保留可调的召回 / 返回数量。

### 好感度与关系层

- 关系表改成 `favorability_raw` + `favorability` 双分值，状态机、每日上限、bank、bypass、道歉衰减和惩罚冷却都按原始分计算。
- `get_status_desc()` 也改为基于原始分映射，不再沿用旧版单分值阈值。

### 交互工具层

- 当前 fork 新增 **消息评论表情工具**；Agent 可按上下文给合适消息添加 NapCat 评论表情。
- 当前 fork 新增 **语音工具**；健康检查通过时才会注入 Agent，直接发送 GPT-SoVITS 返回的音频。

### 群聊请求处理

- 直接 @ / 回复 的聚合逻辑做了额外修正，尽量避免跨用户串单和旧请求互相干扰。
- `reply_guard` 增加了已发送状态跟踪，配合请求失效保护，减少重复发送和清理遗漏。
- 多模态永久失败图片会跳过，媒体清理会同步删除 Qdrant 向量，避免脏数据继续参与检索。

## 🙏 致谢

- 原项目：[`yaowan233/nonebot-plugin-ai-groupmate`](https://github.com/yaowan233/nonebot-plugin-ai-groupmate)
- NoneBot2 社区及相关插件作者
