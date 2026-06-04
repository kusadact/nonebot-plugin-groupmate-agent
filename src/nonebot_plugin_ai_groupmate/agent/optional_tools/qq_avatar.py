import json
import re
import shutil
import time
import asyncio
import base64
from pathlib import Path
from typing import Any

import httpx
from langchain.tools import tool
from langchain_core.messages import HumanMessage as LCHumanMessage
from langchain_core.messages import SystemMessage as LCSystemMessage
from langchain_openai import ChatOpenAI
from nonebot import require
from nonebot.log import logger
from nonebot_plugin_alconna import UniMessage
from nonebot_plugin_orm import get_session
from nonebot_plugin_uninfo import SceneType
from pydantic import BaseModel, Field, SecretStr

from ...model import ChatHistory
from ...reply_guard import can_request_continue, mark_request_sent as mark_guard_request_sent
from .types import OptionalToolBundle, OptionalToolContext, ToolLimitSpec

require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store

QQ_AVATAR_SIZE = 640
QQ_AVATAR_DOWNLOAD_TIMEOUT_SECONDS = 30.0
QQ_AVATAR_MAX_REFERENCE_AVATARS = 2
QQ_AVATAR_CACHE_SECONDS = 3600
QQ_AVATAR_MULTIMODAL_TIMEOUT_SECONDS = 90.0
QQ_AVATAR_DEFAULT_DESCRIPTION_QUESTION = (
    "请用中文描述这个 QQ 头像长什么样。重点说明画面主体、人物/角色特征、表情、颜色、文字、"
    "风格和可能传达的氛围。不要识别真实身份，不要编造看不见的细节。"
)


class FetchQQAvatarArgs(BaseModel):
    target_user_names: list[str] | str = Field(
        description="要获取头像的当前群成员昵称、群名片或 QQ 号；“我/自己”表示当前发起用户。",
    )


class DescribeQQAvatarArgs(BaseModel):
    reference_image_paths: list[str] | str = Field(
        description=(
            "fetch_qq_avatar_references 返回的本地头像图片路径；"
            "也可以直接传完整返回文本，工具会自动提取其中的 path=..."
        ),
    )
    question: str | None = Field(
        default=None,
        description="用户对头像的具体问题；为空时默认描述头像长什么样。",
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


def _image_to_data_uri(file_path: Path) -> str:
    content = file_path.read_bytes()
    payload = base64.b64encode(content).decode("utf-8")
    mime_type = _detect_image_mime(content)
    if not mime_type.startswith("image/"):
        mime_type = "image/png"
    return f"data:{mime_type};base64,{payload}"


def _safe_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z._\-\u4e00-\u9fff]+", "_", value).strip("._-")
    return cleaned[:48] or "avatar"


def _extract_path_values(text: str) -> list[str]:
    values: list[str] = []
    for line in text.splitlines():
        matches = re.findall(r"path=(.+?)(?=\s+(?:name|qq|url)=|$)", line)
        values.extend(match.strip() for match in matches if match.strip())
    return values


def _split_reference_path_candidates(text: str) -> list[str]:
    path_matches = _extract_path_values(text)
    if path_matches:
        return path_matches

    candidates: list[str] = []
    for line in text.splitlines():
        candidates.extend(part.strip() for part in re.split(r"[,，、]+", line) if part.strip())
    return candidates


def _normalize_reference_image_paths(paths: list[str] | str | None) -> list[str]:
    if paths is None:
        return []
    if isinstance(paths, str):
        text = paths.strip()
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = None
        if isinstance(parsed, list):
            candidates = [str(item) for item in parsed]
        elif isinstance(parsed, str):
            candidates = [parsed]
        else:
            candidates = _split_reference_path_candidates(text)
    else:
        candidates = [str(path) for path in paths]

    normalized: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        extracted_paths = _extract_path_values(str(candidate))
        reference_path = extracted_paths[0] if extracted_paths else _normalize_text(candidate)
        if not reference_path or reference_path in seen:
            continue
        seen.add(reference_path)
        normalized.append(reference_path)
    return normalized


def _avatar_cache_root() -> Path:
    return store.get_data_dir("nonebot_plugin_ai_groupmate") / "qq_avatar_references"


def _get_avatar_cache_dir(ctx: OptionalToolContext) -> Path:
    session_part = _safe_filename_part(ctx.session_id or "session")
    request_part = _safe_filename_part(ctx.request_id or str(int(time.time())))
    cache_dir = _avatar_cache_root() / session_part / request_part
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _create_multimodal_model(ctx: OptionalToolContext) -> ChatOpenAI | None:
    config = getattr(ctx, "config", None)
    model = _normalize_text(getattr(config, "multimodal_model_resolved", ""))
    api_key = _normalize_text(getattr(config, "multimodal_api_key_resolved", ""))
    base_url = _normalize_text(getattr(config, "multimodal_base_url_resolved", ""))
    if not model or not api_key:
        return None
    return ChatOpenAI(
        model=model,
        api_key=SecretStr(api_key),
        base_url=base_url or None,
        temperature=0.01,
    )


def _mark_request_sent(ctx: OptionalToolContext) -> None:
    mark_sent = getattr(ctx, "mark_sent", None)
    if mark_sent is not None:
        mark_sent()
        return
    if ctx.request_id is not None:
        mark_guard_request_sent(ctx.session_id, ctx.request_id)


async def _record_sent_avatar(
    ctx: OptionalToolContext,
    message_id: str,
    display_name: str,
    user_id: str,
) -> None:
    try:
        bot_name = str(getattr(ctx.config, "bot_name", None) or "bot")
        async with get_session() as db_session:
            chat_history = ChatHistory(
                session_id=ctx.session_id,
                user_id=str(ctx.bot_id or bot_name),
                content_type="bot",
                content=f"id: {message_id}\n发送了 QQ 头像，用户: {display_name}，QQ: {user_id}",
                user_name=bot_name,
            )
            db_session.add(chat_history)
            await db_session.commit()
    except Exception as e:
        logger.warning(f"记录 QQ 头像发送到聊天历史失败: {type(e).__name__}: {e}")


def _extract_model_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                if item.strip():
                    parts.append(item.strip())
                continue
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
        return "\n".join(parts).strip()
    return ""


def _strip_code_fence(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:text|markdown)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


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


def _resolve_reference_image_files(paths: list[str]) -> list[Path]:
    resolved: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = path.resolve()
        if not path.is_file():
            raise QQAvatarError(f"头像参考图不存在或不是文件: {raw_path}")
        content = path.read_bytes()
        if not content:
            raise QQAvatarError(f"头像参考图为空: {raw_path}")
        if not _detect_image_mime(content).startswith("image/"):
            raise QQAvatarError(f"头像参考图不是图片: {raw_path}")
        resolved.append(path)
    return resolved


def _build_multimodal_content(question: str, image_paths: list[Path]) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "text", "text": question}]
    for image_path in image_paths:
        content.append({"type": "image_url", "image_url": {"url": _image_to_data_uri(image_path)}})
    return content


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


async def _can_continue_request(ctx: OptionalToolContext) -> bool:
    can_continue = getattr(ctx, "can_continue", None)
    if can_continue is not None:
        return await can_continue()
    if ctx.request_id is None:
        return True
    return await can_request_continue(ctx.session_id, ctx.request_id)


def create_qq_avatar_tool(ctx: OptionalToolContext):
    @tool("fetch_qq_avatar_references", args_schema=FetchQQAvatarArgs)
    async def fetch_qq_avatar_references(target_user_names: list[str] | str) -> str:
        """
        匹配当前群成员或 QQ 号，下载 QQ 头像并返回本地图片文件路径。

        当用户要求“用某人头像做图 / 拿某人头像作为参考图 / 给某人头像二创”时调用。
        如果用户只是要求查看、发送某人的原始 QQ 头像，应该调用 send_qq_avatar_image。
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


def create_describe_qq_avatar_tool(ctx: OptionalToolContext):
    @tool("describe_qq_avatar_image", args_schema=DescribeQQAvatarArgs)
    async def describe_qq_avatar_image(
        reference_image_paths: list[str] | str,
        question: str | None = None,
    ) -> str:
        """
        调用多模态模型查看 QQ 头像参考图，并返回头像内容描述。

        当用户要求“看看头像长什么样 / 描述头像 / 分析头像内容 / 这个头像是什么”时调用。
        必须先调用 fetch_qq_avatar_references 获取头像本地 path，再把返回的 path
        或完整返回文本传给 reference_image_paths。本工具不会匹配 QQ 号，也不会下载头像。

        Args:
            reference_image_paths: fetch_qq_avatar_references 返回的本地头像图片路径。
            question: 用户对头像的具体问题；为空时默认描述头像长什么样。
        """
        if not await _can_continue_request(ctx):
            return "请求已过期，已取消查看头像。"

        raw_paths = _normalize_reference_image_paths(reference_image_paths)
        if not raw_paths:
            return "未提供头像参考图路径。请先调用 fetch_qq_avatar_references 获取 path。"
        if len(raw_paths) > QQ_AVATAR_MAX_REFERENCE_AVATARS:
            return f"一次最多只能查看 {QQ_AVATAR_MAX_REFERENCE_AVATARS} 张头像。"

        model = _create_multimodal_model(ctx)
        if model is None:
            return "未配置多模态模型，无法查看头像。请配置 multimodal_model 和 multimodal_api_key/qwen_key。"

        try:
            image_paths = _resolve_reference_image_files(raw_paths)
            prompt = _normalize_text(question) or QQ_AVATAR_DEFAULT_DESCRIPTION_QUESTION
            response = await asyncio.wait_for(
                model.ainvoke(
                    [
                        LCSystemMessage(
                            content=(
                                "你是一个谨慎的图片分析助手。只描述图片里能看到的内容；"
                                "不要识别真实人物身份，不要推断隐私属性。"
                            )
                        ),
                        LCHumanMessage(content=_build_multimodal_content(prompt, image_paths)),
                    ]
                ),
                timeout=QQ_AVATAR_MULTIMODAL_TIMEOUT_SECONDS,
            )
            text = _strip_code_fence(_extract_model_text(response.content))
            return text or "多模态模型没有返回可用描述。"
        except asyncio.TimeoutError:
            logger.warning(f"QQ 头像多模态描述超时: {raw_paths}")
            return "查看头像超时了。"
        except QQAvatarError as e:
            logger.warning(f"QQ 头像描述失败: {e}")
            return f"查看头像失败: {e}"
        except Exception as e:
            logger.exception(f"QQ 头像描述工具异常: {e}")
            return f"查看头像失败: {type(e).__name__}: {e}"

    return describe_qq_avatar_image


def create_send_qq_avatar_tool(ctx: OptionalToolContext):
    @tool("send_qq_avatar_image", args_schema=FetchQQAvatarArgs)
    async def send_qq_avatar_image(target_user_names: list[str] | str) -> str:
        """
        匹配当前群成员或 QQ 号，下载并直接发送原始 QQ 头像到当前群聊。

        当用户要求“发一下某人的头像 / 看看某人的 QQ 头像 / 把某人头像发群里”时调用。
        不会生成、编辑或改造图片。

        Args:
            target_user_names: 当前群成员昵称、群名片或 QQ 号；“我/自己”表示当前发起用户。
        """
        if ctx.request_id is not None and not await can_request_continue(ctx.session_id, ctx.request_id):
            return "请求已过期，已取消发送头像。"

        try:
            targets = await _resolve_avatar_targets(ctx, target_user_names)
            if not targets:
                return "未指定要发送头像的用户。"

            _cleanup_avatar_cache(QQ_AVATAR_CACHE_SECONDS)

            sent_items: list[str] = []
            for user_id, display_name in targets:
                content, _, _ = await _download_avatar(user_id, display_name, ctx)
                if ctx.request_id is not None and not await can_request_continue(ctx.session_id, ctx.request_id):
                    return "请求已过期，已取消发送头像。"

                send_result = await UniMessage.image(raw=content).send()
                _mark_request_sent(ctx)
                message_id = send_result.msg_ids[-1]["message_id"] if send_result.msg_ids else "unknown"
                await _record_sent_avatar(ctx, str(message_id), display_name, user_id)
                sent_items.append(f"{display_name}(qq={user_id})")

            return "已发送 QQ 头像：" + "、".join(sent_items)
        except QQAvatarError as e:
            logger.warning(f"发送 QQ 头像失败: {e}")
            return f"发送 QQ 头像失败: {e}"
        except httpx.HTTPError as e:
            logger.warning(f"发送 QQ 头像网络请求失败: {type(e).__name__}: {e}")
            return f"发送 QQ 头像失败: 网络请求失败 {type(e).__name__}: {e}"
        except Exception as e:
            logger.exception(f"发送 QQ 头像工具异常: {e}")
            return f"发送 QQ 头像失败: {type(e).__name__}: {e}"

    return send_qq_avatar_image


async def healthcheck(ctx: OptionalToolContext) -> tuple[bool, str]:
    return True, "ok"


async def build(ctx: OptionalToolContext) -> OptionalToolBundle:
    if ctx.is_cross_user_direct_reply:
        return OptionalToolBundle(name="qq_avatar")

    prompt = f"""- QQ 头像：
  - 用户只是要求“发 / 发送 / 看看 / 查看某人的 QQ 头像或原头像”时：
    调用 `send_qq_avatar_image`，直接把原头像发到群里；不要调用生图工具
  - 用户要求“头像长什么样 / 描述头像 / 分析头像内容 / 看看头像内容 / 这个头像是什么”时：
    先调用 `fetch_qq_avatar_references` 获取头像 path，再调用 `describe_qq_avatar_image`
  - 用户要求“用某人头像做图 / 给某人头像二创 / 把某人头像生成某种风格”时：
    调用 `fetch_qq_avatar_references` 获取参考图 path，再调用后续图片工具
  - `target_user_names` 可填群名片、昵称、QQ号；“我/自己”表示当前发起用户
  - `fetch_qq_avatar_references` 只返回本地头像图片 `path`，不会发送图片
  - `describe_qq_avatar_image.reference_image_paths` 可以直接填写 `fetch_qq_avatar_references` 的完整返回文本或其中的 path
  - 当前最多获取 {QQ_AVATAR_MAX_REFERENCE_AVATARS} 个用户头像
"""
    return OptionalToolBundle(
        name="qq_avatar",
        tools=[create_qq_avatar_tool(ctx), create_send_qq_avatar_tool(ctx), create_describe_qq_avatar_tool(ctx)],
        prompt=prompt,
        tool_limits=[
            ToolLimitSpec(tool_name="fetch_qq_avatar_references", run_limit=1),
            ToolLimitSpec(tool_name="send_qq_avatar_image", run_limit=1),
            ToolLimitSpec(tool_name="describe_qq_avatar_image", run_limit=1),
        ],
    )
