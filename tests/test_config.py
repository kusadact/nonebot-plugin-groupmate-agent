from tests.helpers import load_module

config = load_module("groupmate_agent_config_under_test", "config.py")


def test_chat_settings_prefer_openai_compat_values():
    cfg = config.ScopedConfig(
        qwen_key=" qwen-key ",
        base_url=" https://dashscope.example/v1 ",
        model=" qwen-model ",
        openai_base_url=" https://openai.example/v1 ",
        openai_model=" gpt-test ",
        openai_token=" openai-key ",
    )

    assert cfg.chat_base_url == "https://openai.example/v1"
    assert cfg.chat_model == "gpt-test"
    assert cfg.chat_api_key == "openai-key"


def test_interaction_defaults_are_conservative():
    cfg = config.ScopedConfig()

    assert cfg.continuous_conversation_minutes == 5.0
    assert cfg.proactive_private_message is False


def test_usage_webui_defaults_are_conservative():
    cfg = config.ScopedConfig()

    assert cfg.usage_webui_enabled is False
    assert cfg.usage_webui_path == "/groupmate-agent/usage"
    assert cfg.usage_webui_token == ""
    assert cfg.chat_input_cost_per_million == 2.0
    assert cfg.chat_output_cost_per_million == 8.0
    assert cfg.chat_cached_input_cost_per_million == 0.4
    assert cfg.chat_explicit_cached_input_cost_per_million == 0.2
    assert cfg.chat_cache_creation_input_cost_per_million == 2.5
    assert cfg.chat_explicit_prompt_cache is True
    assert cfg.chat_long_context_threshold_tokens == 256000
    assert cfg.chat_long_explicit_cached_input_cost_per_million == 0.6
    assert cfg.chat_long_cache_creation_input_cost_per_million == 7.5


def test_summary_key_falls_back_in_priority_order():
    cfg = config.ScopedConfig(qwen_key=" qwen-key ", openai_token=" openai-key ")
    assert cfg.summary_api_key_resolved == "qwen-key"

    cfg.summary_api_key = " summary-key "
    assert cfg.summary_api_key_resolved == "summary-key"


def test_dashscope_media_embedding_defaults_are_resolved():
    cfg = config.ScopedConfig(qwen_key=" qwen-key ")

    assert cfg.remote_media_embedding_provider_resolved == config.DASHSCOPE_MEDIA_EMBEDDING_PROVIDER
    assert cfg.remote_media_embedding_base_url_resolved == config.DASHSCOPE_MEDIA_EMBEDDING_BASE_URL
    assert cfg.remote_media_embedding_model_resolved == config.DASHSCOPE_MEDIA_EMBEDDING_MODEL
    assert cfg.remote_media_embedding_api_key_resolved == "qwen-key"


def test_openai_media_embedding_provider_uses_explicit_values_only():
    cfg = config.ScopedConfig(
        qwen_key=" qwen-key ",
        remote_media_embedding_provider=" openai ",
        remote_media_embedding_base_url=" https://embedding.example/v1 ",
        remote_media_embedding_model=" clip-test ",
        remote_media_embedding_api_key=" media-key ",
    )

    assert cfg.remote_media_embedding_provider_resolved == "openai"
    assert cfg.remote_media_embedding_base_url_resolved == "https://embedding.example/v1"
    assert cfg.remote_media_embedding_model_resolved == "clip-test"
    assert cfg.remote_media_embedding_api_key_resolved == "media-key"
