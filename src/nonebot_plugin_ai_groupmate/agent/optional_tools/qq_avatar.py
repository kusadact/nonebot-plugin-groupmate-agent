import json
import re
import shutil
import time
from pathlib import Path
from typing import Any

import httpx
from langchain.tools import tool
from nonebot import require
from nonebot.log import logger
from nonebot_plugin_uninfo import SceneType
from pydantic import BaseModel, Field

from ...reply_guard import can_request_continue
from .types import OptionalToolBundle, OptionalToolContext, ToolLimitSpec

require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store

QQ_AVATAR_SIZE = 640
QQ_AVATAR_DOWNLOAD_TIMEOUT_SECONDS = 30.0
QQ_AVATAR_MAX_REFERENCE_AVATARS = 2
QQ_AVATAR_CACHE_SECONDS = 3600


class FetchQQAvatarArgs(BaseModel):
    target_user_names: list[str] | str = Field(
        description="要获取头像的当前群成员昵称、群名片或 QQ 号；“我/自己”表示当前发起用户。",
    )


class QQAvatarError(RuntimeError):
    pass


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _strip_at(value: str | None) -> str:
    return _normalize_text(value).lstrip("@＠").strip()


def _extract_numeric_id(raw: str | None) -> str | None:
    text = str(raw or "").strip()
    match = re.search(r"(\d+)$", text)
    return match.group(1) if match else None


def _extract_qq_id(raw: str | None) -> str | None:
    text = str(raw or "").strip()
    if not text:
        return None

    at_match = re.search(r"\[at:qq=(\d+)\]", text)
    if at_match:
        return at_match.group(1)

    if re.fullmatch(r"\d{5,12}", text):
        return text

    qq_match = re.search(r"(?:qq|QQ|user_id|uin)\s*[=:：]\s*(\d{5,12})", text)
    if qq_match:
        return qq_match.group(1)
    return None


def _normalize_target_names(names: list[str] | str | None) -> list[str]:
    if names is None:
        return []
    if isinstance(names, str):
        text = names.strip()
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = None
        if isinstance(parsed, list):
            candidates = [str(item) for item in parsed]
        elif isinstance(parsed, str):
            candidates = [parsed]
        else:
            candidates = re.split(r"[,，、\n]+", text)
    else:
        candidates = [str(name) for name in names]

    normalized: list[str] = []
    seen: set[str] = set()
    for name in (_strip_at(candidate) for candidate in candidates):
        if not name or name in seen:
            continue
        seen.add(name)
        normalized.append(name)
    return normalized


def _member_aliases(member: Any) -> set[str]:
    aliases = {
        str(getattr(member, "id", "") or "").strip(),
        str(getattr(member, "name", "") or "").strip(),
        str(getattr(member, "nick", "") or "").strip(),
        str(getattr(getattr(member, "user", None), "id", "") or "").strip(),
        str(getattr(getattr(member, "user", None), "name", "") or "").strip(),
        str(getattr(getattr(member, "user", None), "nick", "") or "").strip(),
    }
    return {alias for alias in aliases if alias}


def _member_user_id(member: Any) -> str | None:
    for raw in (
        getattr(member, "id", None),
        getattr(getattr(member, "user", None), "id", None),
    ):
        user_id = _extract_numeric_id(str(raw or ""))
        if user_id:
            return user_id
    return None


def _member_display_name(member: Any, fallback: str) -> str:
    return (
        str(getattr(member, "nick", "") or "").strip()
        or str(getattr(member, "name", "") or "").strip()
        or str(getattr(getattr(member, "user", None), "nick", "") or "").strip()
        or str(getattr(getattr(member, "user", None), "name", "") or "").strip()
        or fallback
    )


async def _resolve_members(ctx: OptionalToolContext) -> list[Any]:
    if ctx.interface is None:
        return []
    try:
        return list(await ctx.interface.get_members(SceneType.GROUP, ctx.session_id))
    except Exception as e:
        logger.warning(f"获取群成员列表失败: {type(e).__name__}: {e}")
        return []


def _find_member_by_name(members: list[Any], raw_name: str, ctx: OptionalToolContext) -> Any | None:
    target = _strip_at(raw_name)
    if not target:
        return None

    if target in {"我", "我自己", "自己", "me", "self"} and ctx.user_id:
        current_user_id = _extract_numeric_id(str(ctx.user_id))
        for member in members:
            if current_user_id and _member_user_id(member) == current_user_id:
                return member

    exact_matches: list[Any] = []
    contains_matches: list[Any] = []
    target_folded = target.casefold()

    for member in members:
        aliases = _member_aliases(member)
        if target in aliases:
            exact_matches.append(member)
            continue

        for alias in aliases:
            alias_folded = alias.casefold()
            if target_folded == alias_folded:
                exact_matches.append(member)
                break
            if target_folded and target_folded in alias_folded:
                contains_matches.append(member)
                break

    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        raise QQAvatarError(f"“{raw_name}”匹配到多个群成员，请让用户说得更具体")
    if len(contains_matches) == 1:
        return contains_matches[0]
    if len(contains_matches) > 1:
        raise QQAvatarError(f"“{raw_name}”匹配到多个群成员，请让用户说得更具体")
    return None


def _avatar_url(user_id: str, size: int) -> str:
    return f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s={size}"


def _detect_image_mime(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


def _mime_extension(mime_type: str) -> str:
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }.get(mime_type, ".png")


def _safe_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z._\-\u4e00-\u9fff]+", "_", value).strip("._-")
    return cleaned[:48] or "avatar"


def _avatar_cache_root() -> Path:
    return store.get_data_dir("nonebot_plugin_ai_groupmate") / "qq_avatar_references"


def _get_avatar_cache_dir(ctx: OptionalToolContext) -> Path:
    session_part = _safe_filename_part(ctx.session_id or "session")
    request_part = _safe_filename_part(ctx.request_id or str(int(time.time())))
    cache_dir = _avatar_cache_root() / session_part / request_part
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _cleanup_avatar_cache(cache_seconds: int) -> None:
    root = _avatar_cache_root()
    if not root.exists():
        return

    cutoff = time.time() - max(int(cache_seconds), 60)
    for request_dir in root.glob("*/*"):
        if not request_dir.is_dir():
            continue
        try:
            if request_dir.stat().st_mtime < cutoff:
                shutil.rmtree(request_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"清理 QQ 头像缓存失败: {request_dir}: {e}")

    for session_dir in root.iterdir():
        if session_dir.is_dir():
            try:
                next(session_dir.iterdir())
            except StopIteration:
                session_dir.rmdir()
            except Exception:
                pass


async def _download_avatar(user_id: str, display_name: str, ctx: OptionalToolContext) -> tuple[bytes, str, str]:
    url = _avatar_url(user_id, QQ_AVATAR_SIZE)
    timeout = httpx.Timeout(QQ_AVATAR_DOWNLOAD_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, trust_env=False) as client:
        response = await client.get(url)
    response.raise_for_status()
    if not response.content:
        raise QQAvatarError(f"用户“{display_name}”头像下载为空")

    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    detected = _detect_image_mime(response.content)
    if detected.startswith("image/"):
        content_type = detected
    if content_type and not content_type.startswith("image/"):
        raise QQAvatarError(f"用户“{display_name}”头像返回的不是图片: {content_type}")
    return bytes(response.content), content_type or "image/png", url


async def _resolve_avatar_targets(
    ctx: OptionalToolContext,
    names: list[str] | str | None,
) -> list[tuple[str, str]]:
    raw_names = _normalize_target_names(names)
    if not raw_names:
        return []

    if len(raw_names) > QQ_AVATAR_MAX_REFERENCE_AVATARS:
        raise QQAvatarError(f"最多只能获取 {QQ_AVATAR_MAX_REFERENCE_AVATARS} 个用户头像")

    members = await _resolve_members(ctx)
    targets: list[tuple[str, str]] = []
    seen_ids: set[str] = set()
    for raw_name in raw_names:
        member = None
        user_id = _extract_qq_id(raw_name)
        if user_id is None:
            if not members:
                raise QQAvatarError("无法获取当前群成员列表，不能按昵称获取头像；可直接提供 QQ 号")
            member = _find_member_by_name(members, raw_name, ctx)
            if member is None:
                raise QQAvatarError(f"未找到群成员“{raw_name}”，请确认昵称或直接使用 QQ 号")
            user_id = _member_user_id(member)
        if not user_id:
            raise QQAvatarError(f"无法解析群成员“{raw_name}”的 QQ 号")
        if user_id in seen_ids:
            continue
        display_name = _member_display_name(member, raw_name) if member is not None else raw_name
        targets.append((user_id, display_name))
        seen_ids.add(user_id)
    return targets


def create_qq_avatar_tool(ctx: OptionalToolContext):
    @tool("fetch_qq_avatar_references", args_schema=FetchQQAvatarArgs)
    async def fetch_qq_avatar_references(target_user_names: list[str] | str) -> str:
        """
        匹配当前群成员或 QQ 号，下载 QQ 头像并返回本地图片文件路径。

        当用户要求“用某人头像 / 给某人头像 / 拿某人头像做图”时调用。
        返回的 path 可作为其它图片编辑/生图工具的本地参考图路径。

        Args:
            target_user_names: 当前群成员昵称、群名片或 QQ 号；“我/自己”表示当前发起用户。
        """
        if ctx.request_id is not None and not await can_request_continue(ctx.session_id, ctx.request_id):
            return "请求已过期，已取消获取头像。"

        try:
            targets = await _resolve_avatar_targets(ctx, target_user_names)
            if not targets:
                return "未指定要获取头像的用户。"

            _cleanup_avatar_cache(QQ_AVATAR_CACHE_SECONDS)
            cache_dir = _get_avatar_cache_dir(ctx)

            items: list[str] = []
            for user_id, display_name in targets:
                content, mime_type, url = await _download_avatar(user_id, display_name, ctx)
                suffix = _mime_extension(mime_type)
                filename = f"qq_{user_id}_{_safe_filename_part(display_name)}{suffix}"
                path = cache_dir / filename
                path.write_bytes(content)
                items.append(f"path={path} name={display_name} qq={user_id} url={url}")

            return "已获取 QQ 头像参考图。把 path 作为后续图片工具的本地参考图路径：\n" + "\n".join(items)
        except QQAvatarError as e:
            logger.warning(f"获取 QQ 头像失败: {e}")
            return f"获取 QQ 头像失败: {e}"
        except httpx.HTTPError as e:
            logger.warning(f"获取 QQ 头像网络请求失败: {type(e).__name__}: {e}")
            return f"获取 QQ 头像失败: 网络请求失败 {type(e).__name__}: {e}"
        except Exception as e:
            logger.exception(f"获取 QQ 头像工具异常: {e}")
            return f"获取 QQ 头像失败: {type(e).__name__}: {e}"

    return fetch_qq_avatar_references


async def healthcheck(ctx: OptionalToolContext) -> tuple[bool, str]:
    return True, "ok"


async def build(ctx: OptionalToolContext) -> OptionalToolBundle:
    if ctx.is_cross_user_direct_reply:
        return OptionalToolBundle(name="qq_avatar")

    prompt = f"""- QQ 头像：可使用 `fetch_qq_avatar_references` 获取群成员或指定 QQ 号的头像参考图
  - 用户说“给某人头像...”或“用某人的头像...”时，先调用本工具，再调用后续图片工具
  - `target_user_names` 可填群名片、昵称、QQ号；“我/自己”表示当前发起用户
  - 工具会返回本地头像图片 `path`
  - 后续图片工具需要参考图时，把返回的 `path` 填入对应的参考图路径参数
  - 当前最多获取 {QQ_AVATAR_MAX_REFERENCE_AVATARS} 个用户头像
"""
    return OptionalToolBundle(
        name="qq_avatar",
        tools=[create_qq_avatar_tool(ctx)],
        prompt=prompt,
        tool_limits=[ToolLimitSpec(tool_name="fetch_qq_avatar_references", run_limit=1)],
    )
