from langchain_core.messages import HumanMessage

from tests.helpers import load_module

prompt_cache = load_module("prompt_cache_under_test", "agent/prompt_cache.py")


def test_build_system_messages_marks_stable_prompt_when_enabled():
    messages = prompt_cache.build_system_messages(
        "stable prompt",
        "dynamic prompt",
        use_cache_control=True,
    )

    assert len(messages) == 2
    first_content = messages[0].content
    assert isinstance(first_content, list)
    assert first_content[0]["text"] == "stable prompt"
    assert first_content[0]["cache_control"] == {"type": "ephemeral"}
    assert messages[1].content == "dynamic prompt"


def test_add_ephemeral_cache_marker_marks_last_text_message():
    messages = [
        HumanMessage(content="first"),
        HumanMessage(content=[{"type": "text", "text": "second"}]),
    ]

    marked = prompt_cache.add_ephemeral_cache_marker(messages)

    assert messages[1].content == [{"type": "text", "text": "second"}]
    assert marked[0].content == "first"
    assert marked[1].content == [
        {
            "type": "text",
            "text": "second",
            "cache_control": {"type": "ephemeral"},
        }
    ]


def test_should_use_explicit_prompt_cache_only_for_supported_backends():
    enabled = prompt_cache.should_use_explicit_prompt_cache

    class Config:
        chat_explicit_prompt_cache = True
        chat_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    assert enabled(Config()) is True

    Config.chat_base_url = "https://api.openai.com/v1"
    assert enabled(Config()) is False

    Config.chat_explicit_prompt_cache = False
    Config.chat_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert enabled(Config()) is False
