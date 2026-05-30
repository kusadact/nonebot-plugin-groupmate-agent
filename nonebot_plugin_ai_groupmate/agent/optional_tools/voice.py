from ..voice_tool import (
    create_voice_tool,
    get_voice_health_detail,
    get_voice_supported_text_langs,
    is_voice_service_healthy,
)
from .types import OptionalToolBundle, OptionalToolContext, ToolLimitSpec


async def healthcheck(ctx: OptionalToolContext) -> tuple[bool, str]:
    if not ctx.config.voice_enabled:
        return False, "voice disabled"
    if not (ctx.config.voice_base_url or "").strip():
        return False, "missing voice_base_url"
    ok = await is_voice_service_healthy(ctx.config)
    return ok, get_voice_health_detail()


async def build(ctx: OptionalToolContext) -> OptionalToolBundle:
    voice_supported_text_langs = get_voice_supported_text_langs(ctx.config)
    voice_default_values_instruction = (
        "  - 当前默认值："
        f"`text_lang={ctx.config.voice_text_lang}`，"
        f"`speed_factor={ctx.config.voice_speed_factor}`，"
        f"`top_k={ctx.config.voice_top_k}`，"
        f"`top_p={ctx.config.voice_top_p}`，"
        f"`temperature={ctx.config.voice_temperature}`\n"
    )
    if voice_supported_text_langs:
        voice_text_lang_options = " / ".join(voice_supported_text_langs)
        voice_text_lang_instruction = f"  - `text_lang` 当前只能从这些值里选：{voice_text_lang_options}\n"
    else:
        voice_text_lang_instruction = "  - 健康检查当前没有返回可选 `text_lang` 列表时，不要自己猜新的值\n"

    prompt = f"""- 语音：可使用 `send_voice` 合成并发送语音
  - 只有用户明确要求“发语音 / 用语音说 / 念出来 / 读出来”时才使用
  - 语音内容必须短，优先一句话，避免长段落
  - `content` 里只放最终要念出来的文本，不要把参数说明、括号解释、舞台指令写进去
  - 可按需传 `text_lang`、`speed_factor`、`top_k`、`top_p`、`temperature`
  - 参数含义：
    - `text_lang`：目标文本语言
    - `speed_factor`：语速，越大越快
    - `top_k`：候选采样范围，越大越放飞
    - `top_p`：候选累计概率范围，越大越发散
    - `temperature`：整体随机度，越大越有情绪起伏
{voice_default_values_instruction}{voice_text_lang_instruction}  - 日常普通对话优先直接用默认值，不要为了小变化乱调参数
  - 只有在用户情绪、语气、演绎需求很明显时，再小幅微调这些参数
  - 如果 `send_voice` 返回失败，不要假装已发送；可以改用 `reply_user` 简短说明
"""
    return OptionalToolBundle(
        name="voice",
        tools=[create_voice_tool(ctx.session_id, ctx.request_id, ctx.config, ctx.config.bot_name)],
        prompt=prompt,
        tool_limits=[ToolLimitSpec(tool_name="send_voice", run_limit=1)],
    )
