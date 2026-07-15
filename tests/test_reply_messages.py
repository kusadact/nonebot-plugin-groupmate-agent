import asyncio

import pytest
from langchain.tools import tool
from pydantic import ValidationError

from tests.helpers import load_module

reply_messages = load_module("groupmate_agent_reply_messages_under_test", "reply_messages.py")
ReplyItem = reply_messages.ReplyItem


def test_single_message_preserves_plain_newlines():
    args = reply_messages.ReplyArgs.model_validate(
        {"messages": [{"content": "第一行\r\n第二行"}]},
    )

    assert [message.content for message in args.messages] == ["第一行\n第二行"]


def test_array_items_are_independent_messages():
    args = reply_messages.ReplyArgs.model_validate(
        {
            "messages": [
                {"content": "小川加油呀，你今天也很努力的"},
                {"content": "能撑到现在就已经很厉害了，摸摸头"},
            ]
        },
    )

    assert [message.content for message in args.messages] == [
        "小川加油呀，你今天也很努力的",
        "能撑到现在就已经很厉害了，摸摸头",
    ]


def test_langchain_tool_receives_validated_message_items():
    @tool("reply_probe", args_schema=reply_messages.ReplyArgs, description="测试结构化回复参数")
    async def reply_probe(messages: list[ReplyItem]) -> str:
        return "|".join(message.content for message in messages)

    result = asyncio.run(
        reply_probe.ainvoke(
            {
                "messages": [
                    {"content": "第一条"},
                    {"content": "第二条"},
                ]
            }
        )
    )

    assert result == "第一条|第二条"


def test_reply_args_reject_empty_or_too_many_messages():
    with pytest.raises(ValidationError):
        reply_messages.ReplyArgs.model_validate({"messages": []})

    with pytest.raises(ValidationError):
        reply_messages.ReplyArgs.model_validate(
            {"messages": [{"content": str(index)} for index in range(4)]},
        )

    with pytest.raises(ValidationError):
        reply_messages.ReplyArgs.model_validate({"messages": [{"content": " \r\n "}]})


def test_targeted_schema_requires_target_ref():
    with pytest.raises(ValidationError):
        reply_messages.TargetedReplyArgs.model_validate(
            {"messages": [{"content": "回复一号"}]},
        )


def test_single_target_ignores_extra_target_ref():
    args = reply_messages.ReplyArgs.model_validate(
        {"messages": [{"target_ref": 99, "content": "回复唯一目标"}]},
    )

    resolved = reply_messages.resolve_reply_targets(args.messages, direct_target_count=1)

    assert [message.content for message in resolved] == ["回复唯一目标"]


def test_targeted_messages_are_validated_and_sorted_by_ref():
    args = reply_messages.TargetedReplyArgs.model_validate(
        {
            "messages": [
                {"target_ref": 2, "content": "回复二号"},
                {"target_ref": 1, "content": "回复一号"},
            ]
        },
    )

    resolved = reply_messages.resolve_reply_targets(args.messages, direct_target_count=2)

    assert [(message.target_ref, message.content) for message in resolved] == [
        (1, "回复一号"),
        (2, "回复二号"),
    ]


@pytest.mark.parametrize(
    "raw_messages",
    [
        [
            {"target_ref": 1, "content": "回复一号"},
            {"target_ref": 1, "content": "又回复一号"},
        ],
        [
            {"target_ref": 1, "content": "回复一号"},
            {"target_ref": 3, "content": "错误编号"},
        ],
    ],
)
def test_targeted_messages_must_cover_each_ref_once(raw_messages):
    args = reply_messages.TargetedReplyArgs.model_validate({"messages": raw_messages})

    with pytest.raises(ValueError, match="完整覆盖编号"):
        reply_messages.resolve_reply_targets(args.messages, direct_target_count=2)


def test_targeted_messages_must_match_target_count():
    args = reply_messages.TargetedReplyArgs.model_validate(
        {"messages": [{"target_ref": 1, "content": "回复一号"}]},
    )

    with pytest.raises(ValueError, match="必须恰好包含 2 条回复"):
        reply_messages.resolve_reply_targets(args.messages, direct_target_count=2)


def test_semantic_duplicates_are_removed_for_normal_replies():
    args = reply_messages.ReplyArgs.model_validate(
        {"messages": [{"content": "哈"}, {"content": "哈"}]},
    )

    deduped = reply_messages.dedupe_reply_items(args.messages)

    assert [message.content for message in deduped] == ["哈"]
    assert reply_messages.dedupe_reply_items(args.messages, allow_reply_duplicates=True) == args.messages


def test_legacy_separator_has_no_structural_meaning():
    args = reply_messages.ReplyArgs.model_validate(
        {"messages": [{"content": "路径 /n 只是正文\n下一行"}]},
    )

    assert [message.content for message in args.messages] == ["路径 /n 只是正文\n下一行"]
