from __future__ import annotations

from typing import Any

from langchain.tools import tool
from nonebot.log import logger
from nonebot_plugin_alconna import Target, UniMessage
from nonebot_plugin_uninfo import SceneType
from sqlalchemy import Select

from ...model import ChatHistory
from ...reply_guard import can_request_continue
from .types import OptionalToolBundle, OptionalToolContext, ToolLimitSpec


def _config_enabled(ctx: OptionalToolContext) -> bool:
    return bool(getattr(getattr(ctx, "config", None), "proactive_private_message", False))


async def _can_continue(ctx: OptionalToolContext) -> bool:
    if ctx.can_continue is not None:
        return await ctx.can_continue()
    if ctx.request_id is None:
        return True
    return await can_request_continue(ctx.session_id, ctx.request_id)


def _message_id_from_result(result: Any) -> str:
    msg_ids = getattr(result, "msg_ids", None) or []
    if not msg_ids:
        return "unknown"
    last_msg = msg_ids[-1]
    if isinstance(last_msg, dict):
        return str(last_msg.get("message_id") or last_msg.get("msg_id") or "unknown")
    return str(last_msg)


def _member_aliases(member: Any) -> set[str]:
    aliases = {
        getattr(member, "name", None),
        getattr(member, "nick", None),
        getattr(getattr(member, "user", None), "name", None),
        getattr(getattr(member, "user", None), "nick", None),
    }
    return {str(alias).strip() for alias in aliases if str(alias or "").strip()}


def create_private_message_tool(ctx: OptionalToolContext):
    async def _resolve_group_member(
        target_user_id: str | None,
        target_name: str | None,
    ) -> tuple[str | None, str | None]:
        if ctx.interface is None:
            return None, "缺少群成员接口，无法确认私聊目标。"

        target_user_id = str(target_user_id or "").strip()
        target_name = str(target_name or "").strip()
        if not target_user_id and not target_name:
            return None, "缺少私聊目标，请提供 target_user_id 或 target_name。"

        try:
            members = await ctx.interface.get_members(SceneType.GROUP, ctx.session_id)
        except Exception as e:
            logger.warning(f"获取群成员失败，无法主动私聊: {e}")
            return None, "获取群成员失败，无法确认私聊目标。"

        member_ids: set[str] = set()
        name_to_id: dict[str, str] = {}
        for member in members:
            member_id = str(getattr(member, "id", "") or "").strip()
            if not member_id:
                continue
            member_ids.add(member_id)
            for alias in _member_aliases(member):
                name_to_id[alias] = member_id

        if target_user_id:
            if target_user_id not in member_ids:
                return None, "目标用户不在当前群内，已拒绝主动私聊。"
            if ctx.bot_id is not None and target_user_id == str(ctx.bot_id):
                return None, "不能给自己发送私聊。"
            return target_user_id, None

        resolved_id = name_to_id.get(target_name)
        if not resolved_id:
            return None, f"找不到群成员 {target_name!r}。"
        if ctx.bot_id is not None and resolved_id == str(ctx.bot_id):
            return None, "不能给自己发送私聊。"
        return resolved_id, None

    async def _latest_private_bot_message(target_id: str) -> ChatHistory | None:
        if ctx.db_session is None:
            return None
        return (
            (
                await ctx.db_session.execute(
                    Select(ChatHistory)
                    .where(
                        ChatHistory.session_id == target_id,
                        ChatHistory.content_type == "bot",
                    )
                    .order_by(ChatHistory.msg_id.desc())
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )

    @tool("send_private_message")
    async def send_private_message(
        content: str,
        target_user_id: str | None = None,
        target_name: str | None = None,
        reason: str | None = None,
    ) -> str:
        """
        主动给当前群内某个成员发送私聊消息。

        只在确实不适合群内公开回复时使用，例如提醒隐私信息、避免当众尴尬、继续一段只和对方相关的话题。
        不要群发，不要骚扰，不要绕过用户明确拒绝。

        Args:
            content: 要私聊发送的文本。
            target_user_id: 目标用户 ID，必须是当前群成员。
            target_name: 目标用户昵称/名称；不知道 ID 时使用。
            reason: 简短说明为什么需要私聊，用于日志和历史记录。
        """
        if not await _can_continue(ctx):
            return "请求已过期，已取消主动私聊。"

        content = str(content or "").strip()
        if not content:
            return "主动私聊内容为空，未发送。"

        target_id, error = await _resolve_group_member(target_user_id, target_name)
        if error or not target_id:
            return f"主动私聊失败: {error}"

        latest_private_msg = await _latest_private_bot_message(target_id)
        if latest_private_msg and latest_private_msg.content.endswith(content):
            return "检测到重复私聊内容，已跳过发送。"

        try:
            if not await _can_continue(ctx):
                return "请求已过期，已取消主动私聊。"

            target = Target(id=target_id, private=True, self_id=ctx.bot_id)
            result = await UniMessage.text(content).send(target=target)
            if ctx.mark_sent is not None:
                ctx.mark_sent()
            msg_id = _message_id_from_result(result)

            if ctx.db_session is not None:
                bot_name = str(getattr(ctx.config, "bot_name", None) or ctx.bot_id or "bot")
                ctx.db_session.add(
                    ChatHistory(
                        session_id=target_id,
                        user_id=bot_name,
                        content_type="bot",
                        content=f"id: {msg_id}\n{content}",
                        user_name=bot_name,
                    )
                )
                ctx.db_session.add(
                    ChatHistory(
                        session_id=ctx.session_id,
                        user_id=bot_name,
                        content_type="bot",
                        content="id: system\n" f"已主动私聊用户 {target_id}: {reason or '未填写原因'}",
                        user_name=bot_name,
                    )
                )

            logger.info(f"已主动私聊用户 {target_id}，reason={reason or '未填写原因'}")
            return f"已主动私聊用户 {target_id}。"
        except Exception as e:
            logger.error(f"主动私聊发送失败: {e}")
            return f"主动私聊发送失败: {type(e).__name__}: {e}"

    return send_private_message


async def healthcheck(ctx: OptionalToolContext) -> tuple[bool, str]:
    if not _config_enabled(ctx):
        return False, "proactive_private_message disabled"
    if ctx.is_private:
        return False, "private chat context"
    if ctx.is_cross_user_direct_reply:
        return False, "cross-user direct reply context"
    if ctx.interface is None:
        return False, "missing group member interface"
    return True, "ok"


async def build(ctx: OptionalToolContext) -> OptionalToolBundle:
    ok, _ = await healthcheck(ctx)
    if not ok:
        return OptionalToolBundle(name="private_message")

    prompt = """- 主动私聊：可使用 `send_private_message`
  - 只在不适合群内公开说、涉及隐私、避免让对方尴尬、或用户明确希望私下继续时使用
  - 不要群发，不要骚扰，不要用私聊绕过对方拒绝，也不要发送营销/诱导内容
  - 能在群内自然说清的内容优先用 `reply_user`
  - `target_user_id` 必须是当前群成员；不知道 ID 时可用 `target_name`
  - `reason` 简短填写为什么需要私聊
"""
    return OptionalToolBundle(
        name="private_message",
        tools=[create_private_message_tool(ctx)],
        prompt=prompt,
        tool_limits=[ToolLimitSpec(tool_name="send_private_message", run_limit=1)],
    )
