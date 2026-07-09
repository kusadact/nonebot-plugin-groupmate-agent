from __future__ import annotations

import datetime
from collections.abc import Callable
from typing import Any

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import ScopedConfig
from .model import TokenUsage

MAX_USAGE_DAYS = 3650


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def estimate_cost(
    *,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int,
    callback_cost: float,
    input_cost_per_million: float,
    output_cost_per_million: float,
    cached_input_cost_per_million: float,
    long_context_threshold_tokens: int = 256000,
    long_input_cost_per_million: float | None = None,
    long_output_cost_per_million: float | None = None,
    long_cached_input_cost_per_million: float | None = None,
) -> float:
    if callback_cost > 0:
        return float(callback_cost)

    if prompt_tokens > long_context_threshold_tokens:
        input_cost_per_million = (
            long_input_cost_per_million
            if long_input_cost_per_million is not None
            else input_cost_per_million
        )
        output_cost_per_million = (
            long_output_cost_per_million
            if long_output_cost_per_million is not None
            else output_cost_per_million
        )
        cached_input_cost_per_million = (
            long_cached_input_cost_per_million
            if long_cached_input_cost_per_million is not None
            else cached_input_cost_per_million
        )

    billed_prompt_tokens = max(prompt_tokens - cached_tokens, 0)
    return (
        billed_prompt_tokens / 1_000_000 * input_cost_per_million
        + cached_tokens / 1_000_000 * cached_input_cost_per_million
        + completion_tokens / 1_000_000 * output_cost_per_million
    )


def estimate_cost_from_config(
    *,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int,
    callback_cost: float,
    config: ScopedConfig,
) -> float:
    return estimate_cost(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=cached_tokens,
        callback_cost=callback_cost,
        input_cost_per_million=config.chat_input_cost_per_million,
        output_cost_per_million=config.chat_output_cost_per_million,
        cached_input_cost_per_million=config.chat_cached_input_cost_per_million,
        long_context_threshold_tokens=config.chat_long_context_threshold_tokens,
        long_input_cost_per_million=config.chat_long_input_cost_per_million,
        long_output_cost_per_million=config.chat_long_output_cost_per_million,
        long_cached_input_cost_per_million=config.chat_long_cached_input_cost_per_million,
    )


async def record_token_usage(
    db_session: AsyncSession,
    *,
    session_id: str,
    session_type: str,
    user_id: str,
    user_name: str | None,
    model: str,
    request_id: str | None,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int,
    total_tokens: int,
    estimated_cost: float,
) -> None:
    if max(prompt_tokens, completion_tokens, cached_tokens, total_tokens) <= 0:
        return

    db_session.add(
        TokenUsage(
            session_id=session_id,
            session_type=session_type,
            user_id=user_id or "",
            user_name=user_name or "",
            model=model or "",
            request_id=request_id or "",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=cached_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
        )
    )


def since_from_days(days: int) -> datetime.datetime:
    days = max(1, min(days, MAX_USAGE_DAYS))
    return datetime.datetime.now() - datetime.timedelta(days=days)


def estimate_usage_row_cost(row: TokenUsage, config: ScopedConfig) -> float:
    if row.estimated_cost > 0:
        return row.estimated_cost
    return estimate_cost_from_config(
        prompt_tokens=row.prompt_tokens,
        completion_tokens=row.completion_tokens,
        cached_tokens=row.cached_tokens,
        callback_cost=0.0,
        config=config,
    )


def _empty_metrics(labels: dict[str, Any]) -> dict[str, Any]:
    return {
        **labels,
        "requests": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cached_tokens": 0,
        "total_tokens": 0,
        "estimated_cost": 0.0,
    }


def _aggregate_rows(
    rows: list[TokenUsage],
    *,
    key_fn: Callable[[TokenUsage], tuple[tuple[Any, ...], dict[str, Any]]],
    cost_fn: Callable[[TokenUsage], float],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key, labels = key_fn(row)
        item = grouped.setdefault(key, _empty_metrics(labels))
        item["requests"] += 1
        item["prompt_tokens"] += _as_int(row.prompt_tokens)
        item["completion_tokens"] += _as_int(row.completion_tokens)
        item["cached_tokens"] += _as_int(row.cached_tokens)
        item["total_tokens"] += _as_int(row.total_tokens)
        item["estimated_cost"] += cost_fn(row)
    return sorted(grouped.values(), key=lambda item: item["total_tokens"], reverse=True)


async def get_usage_dashboard_data(
    db_session: AsyncSession,
    *,
    config: ScopedConfig,
    days: int = 7,
    session_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    since = since_from_days(days)
    filters = [TokenUsage.created_at >= since]
    if session_id:
        filters.append(TokenUsage.session_id == session_id)
    if user_id:
        filters.append(TokenUsage.user_id == user_id)

    rows = (
        await db_session.execute(
            Select(TokenUsage)
            .where(*filters)
            .order_by(TokenUsage.created_at.desc())
        )
    ).scalars().all()
    def cost_fn(row: TokenUsage) -> float:
        return estimate_usage_row_cost(row, config)

    total = {
        "requests": len(rows),
        "prompt_tokens": sum(_as_int(row.prompt_tokens) for row in rows),
        "completion_tokens": sum(_as_int(row.completion_tokens) for row in rows),
        "cached_tokens": sum(_as_int(row.cached_tokens) for row in rows),
        "total_tokens": sum(_as_int(row.total_tokens) for row in rows),
        "estimated_cost": sum(cost_fn(row) for row in rows),
    }
    by_session_rows = _aggregate_rows(
        rows,
        key_fn=lambda row: (
            (row.session_id, row.session_type),
            {"session_id": row.session_id, "session_type": row.session_type},
        ),
        cost_fn=cost_fn,
    )[:50]
    by_user_rows = _aggregate_rows(
        rows,
        key_fn=lambda row: (
            (row.user_id,),
            {"user_id": row.user_id, "user_name": row.user_name},
        ),
        cost_fn=cost_fn,
    )[:50]
    by_model_rows = _aggregate_rows(
        rows,
        key_fn=lambda row: ((row.model,), {"model": row.model or "unknown"}),
        cost_fn=cost_fn,
    )[:30]
    recent_rows = rows[:100]

    return {
        "days": max(1, min(days, MAX_USAGE_DAYS)),
        "since": since.isoformat(),
        "filters": {"session_id": session_id or "", "user_id": user_id or ""},
        "total": total,
        "by_session": by_session_rows,
        "by_user": by_user_rows,
        "by_model": by_model_rows,
        "recent": [
            {
                "created_at": row.created_at.isoformat(),
                "session_id": row.session_id,
                "session_type": row.session_type,
                "user_id": row.user_id,
                "user_name": row.user_name,
                "model": row.model,
                "prompt_tokens": row.prompt_tokens,
                "completion_tokens": row.completion_tokens,
                "cached_tokens": row.cached_tokens,
                "total_tokens": row.total_tokens,
                "estimated_cost": cost_fn(row),
            }
            for row in recent_rows
        ],
    }
