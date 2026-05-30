from ..emoji_like import EMOJI_LIKE_CATEGORY_PROMPT, create_emoji_like_tool
from .types import OptionalToolBundle, OptionalToolContext, ToolLimitSpec

PROMPT_TEMPLATE = """- 评论表情：可选使用 `add_message_emoji_like`
  - 当你觉得某条消息适合轻量回应时，可以给它添加一个评论表情
  - 这是附加反应，不是必须；没有特别合适的消息就不要调用
  - 优先给【当前触发消息】或【本轮回复引用的消息】添加
  - `target_msg_id` 必须来自本轮 prompt 中出现的消息 id，不要猜
  - 不要为了完成任务硬贴表情，不要连续乱贴；每轮最多调用一次
  - `emoji_name` 可以传具体表情名、表情 id、语义词或分类词
  - 可用分类：{categories}
  - 选择表情时按语义匹配，例如：赞同用“赞同鼓励”，好笑用“好笑玩梗”，疑惑用“疑惑思考”，安慰用“安慰难过”
  - 喜欢亲近用“喜欢贴贴”，祝贺用“庆祝好运”，生气或拒绝用“生气拒绝”，惊讶或尴尬用“惊讶尴尬”
  - 如果 `add_message_emoji_like` 返回失败，不要假装成功；通常也不用专门解释
"""


async def build(ctx: OptionalToolContext) -> OptionalToolBundle:
    emoji_like_tool = create_emoji_like_tool(
        ctx.session_id,
        ctx.request_id,
        ctx.bot_id,
        ctx.emoji_like_candidate_ids,
    )
    return OptionalToolBundle(
        name="emoji_like",
        tools=[emoji_like_tool],
        prompt=PROMPT_TEMPLATE.format(categories=EMOJI_LIKE_CATEGORY_PROMPT),
        tool_limits=[ToolLimitSpec(tool_name="add_message_emoji_like", run_limit=1)],
    )
