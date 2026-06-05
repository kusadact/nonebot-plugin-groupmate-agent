from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolLimitSpec:
    tool_name: str | None
    run_limit: int


@dataclass
class OptionalToolBundle:
    name: str
    tools: list[Any] = field(default_factory=list)
    prompt: str = ""
    tool_limits: list[ToolLimitSpec] = field(default_factory=list)


@dataclass
class OptionalToolContext:
    session_id: str
    request_id: str | None
    user_id: str | None
    user_name: str | None
    interface: Any
    bot_id: str | None
    history: list[Any]
    direct_targets: list[dict[str, Any]]
    emoji_like_candidate_ids: set[str]
    has_direct_targets: bool
    is_multi_direct_reply: bool
    is_cross_user_direct_reply: bool
    has_admin_permission: bool
    config: Any
    model: Any
    stop_words: list[str]
    detach_request: Callable[[str], None] | None = None
    can_continue: Callable[[], Awaitable[bool]] | None = None
    mark_sent: Callable[[], None] | None = None
    clear_detached: Callable[[], None] | None = None
    create_detached_task: Callable[[Coroutine[Any, Any, Any], str], Any] | None = None
    bot: Any | None = None
    event: Any | None = None
