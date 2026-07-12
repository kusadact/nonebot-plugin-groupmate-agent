import re
import traceback
from typing import Any

from langchain.tools import tool
from nonebot import get_bot
from nonebot.log import logger
from nonebot_plugin_orm import get_session
from nonebot_plugin_uninfo import SceneType

from ...model import ChatHistory
from ...reply_guard import can_request_continue
from .types import AgentSkill, OptionalToolBundle, OptionalToolContext

PERMISSION_STATUS = """
【你的权限】
你在这个群里是管理员或群主，必要时可以使用禁言工具维护秩序。
"""

PROMPT = """- 禁言管理：可使用 `mute_user` 禁言
  - 你有权限执行禁言操作
  - 【必须满足】用户请求禁言自己时，应该满足需求（例如“禁言我”“让我冷静一下”）
    - 时长可以根据用户要求或默认给 5-30 分钟
    - 这是帮助用户自我管理的合理需求
  - 【谨慎使用】禁言他人时才需要谨慎：
    - 严重违规、恶意刷屏时可以主动禁言
    - 轻微违规应先警告
    - 禁言时长应合理：轻微违规 60-300 秒，严重违规可更长
  - 不要禁言管理员或群主
  - 如果 `mute_user` 返回失败，只能如实说明失败原因，不能假装成功
"""


def create_mute_tool(ctx: OptionalToolContext):
    """创建禁言工具。仅在 bot 有管理权限时注入。"""

    def _extract_numeric_id(raw: str | None) -> int | None:
        text = str(raw or "").strip()
        match = re.search(r"(\d+)$", text)
        return int(match.group(1)) if match else None

    def _member_aliases(member: Any) -> set[str]:
        aliases = {
            str(getattr(member, "id", "") or "").strip(),
            str(getattr(member, "name", "") or "").strip(),
            str(getattr(member, "nick", "") or "").strip(),
            str(getattr(getattr(member, "user", None), "name", "") or "").strip(),
            str(getattr(getattr(member, "user", None), "nick", "") or "").strip(),
        }
        return {alias for alias in aliases if alias}

    def _member_display_name(member: Any, fallback: str) -> str:
        return (
            str(getattr(member, "nick", "") or "").strip()
            or str(getattr(member, "name", "") or "").strip()
            or str(getattr(getattr(member, "user", None), "nick", "") or "").strip()
            or str(getattr(getattr(member, "user", None), "name", "") or "").strip()
            or fallback
        )

    async def _record_mute_action(action: str, target_name: str, target_id: str, reason: str) -> None:
        try:
            async with get_session() as db_session:
                chat_history = ChatHistory(
                    session_id=ctx.session_id,
                    user_id=str(ctx.bot_id or ctx.config.bot_name),
                    content_type="bot",
                    content=(
                        "id: system\n"
                        f"系统记录：已执行群管理操作，{action}用户“{target_name}”"
                        f"（user_id: {target_id}）。原因：{reason}"
                    ),
                    user_name=ctx.config.bot_name,
                )
                db_session.add(chat_history)
                await db_session.commit()
        except Exception as e:
            logger.warning(f"记录禁言操作到聊天历史失败: {e}")

    @tool("mute_user")
    async def mute_user(target_user_name: str, duration_seconds: int, reason: str) -> str:
        """
        禁言指定用户。仅在 bot 是管理员或群主时可用。

        参数:
        - target_user_name: 要禁言的用户昵称；用户请求“禁言我”时可传“我”或“自己”
        - duration_seconds: 禁言时长（秒），0 表示解除禁言，最大 2592000
        - reason: 操作原因
        """
        if ctx.request_id is not None and not await can_request_continue(ctx.session_id, ctx.request_id):
            return "请求已过期，已取消操作。"
        if ctx.interface is None:
            return "无法获取群成员接口，禁言失败。"
        if not ctx.bot_id:
            return "无法获取 bot ID，禁言失败。"
        if not reason or not reason.strip():
            return "禁言原因不能为空。"
        if duration_seconds < 0 or duration_seconds > 2592000:
            return "禁言时长必须在 0 到 2592000 秒之间。"

        try:
            members = await ctx.interface.get_members(SceneType.GROUP, ctx.session_id)
            bot_member = None
            target_member = None
            normalized_target = str(target_user_name or "").strip().lstrip("@")

            for member in members:
                if str(member.id) == str(ctx.bot_id):
                    bot_member = member

                if normalized_target in {"我", "我自己", "自己", "me", "self"}:
                    if ctx.user_id and str(member.id) == str(ctx.user_id):
                        target_member = member
                else:
                    aliases = _member_aliases(member)
                    if normalized_target and normalized_target in aliases:
                        target_member = member

            if bot_member is None:
                return "无法获取 bot 的群成员信息。"

            bot_role = getattr(getattr(bot_member, "role", None), "name", None)
            if bot_role not in {"owner", "admin"}:
                return "bot 不是管理员或群主，无法执行禁言。"

            if target_member is None and ctx.user_name and normalized_target == ctx.user_name:
                for member in members:
                    if ctx.user_id and str(member.id) == str(ctx.user_id):
                        target_member = member
                        break

            if target_member is None:
                return f"未找到用户“{target_user_name}”，请确认昵称是否正确。"

            target_role = getattr(getattr(target_member, "role", None), "name", None)
            if target_role in {"owner", "admin"}:
                return f"无法禁言管理员或群主“{target_user_name}”。"

            group_num = _extract_numeric_id(ctx.session_id)
            user_num = _extract_numeric_id(str(target_member.id))
            if group_num is None or user_num is None:
                return "当前适配器会话 ID 格式不支持禁言。"

            bot = get_bot(ctx.bot_id)
            if hasattr(bot, "set_group_ban"):
                await bot.set_group_ban(
                    group_id=group_num,
                    user_id=user_num,
                    duration=duration_seconds,
                )
            elif hasattr(bot, "call_api"):
                await bot.call_api(
                    "set_group_ban",
                    group_id=group_num,
                    user_id=user_num,
                    duration=duration_seconds,
                )
            else:
                return "当前适配器不支持禁言功能。"

            action = "解除禁言" if duration_seconds == 0 else f"禁言 {duration_seconds} 秒"
            display_name = _member_display_name(
                target_member,
                ctx.user_name if normalized_target in {"我", "我自己", "自己", "me", "self"} else target_user_name,
            )
            logger.info(
                f"已{action}用户 name={display_name!r} user_id={target_member.id} "
                f"session_id={ctx.session_id} reason={reason}"
            )
            await _record_mute_action(action, display_name, str(target_member.id), reason)
            return f"已成功{action}用户“{display_name}”。原因：{reason}"
        except Exception as e:
            logger.error(f"禁言工具执行失败: {e}")
            print(traceback.format_exc())
            return f"禁言失败: {str(e)}"

    return mute_user


async def build(ctx: OptionalToolContext) -> OptionalToolBundle:
    if ctx.is_cross_user_direct_reply or not ctx.has_admin_permission:
        return OptionalToolBundle(name="moderation")
    return OptionalToolBundle(
        name="moderation",
        tools=[create_mute_tool(ctx)],
        skills=[
            AgentSkill(
                name="moderation",
                description="在 bot 有管理权限时执行群禁言或解除禁言。",
                prompt=PROMPT,
                tool_names=("mute_user",),
            )
        ],
    )
