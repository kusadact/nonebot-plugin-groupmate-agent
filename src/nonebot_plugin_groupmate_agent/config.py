from pydantic import BaseModel, Field

DASHSCOPE_COMPATIBLE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DASHSCOPE_MEDIA_EMBEDDING_BASE_URL = (
    "https://dashscope.aliyuncs.com/api/v1/services/embeddings/multimodal-embedding/multimodal-embedding"
)
DASHSCOPE_CHAT_MODEL = "qwen3.5-plus"
DASHSCOPE_SUMMARY_MODEL = "qwen-flash"
DASHSCOPE_MULTIMODAL_MODEL = "qwen-vl-max"
DASHSCOPE_MEDIA_EMBEDDING_PROVIDER = "dashscope"
DASHSCOPE_MEDIA_EMBEDDING_MODEL = "qwen3-vl-embedding"


def _first_non_empty(*values: str) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return ""


class ScopedConfig(BaseModel):
    qwen_key: str = ""
    base_url: str = DASHSCOPE_COMPATIBLE_BASE_URL
    model: str = DASHSCOPE_CHAT_MODEL
    bot_name: str = "bot"
    reply_probability: float = 0.01
    continuous_conversation_minutes: float = 5.0
    proactive_private_message: bool = False
    usage_webui_enabled: bool = False
    usage_webui_path: str = "/groupmate-agent/usage"
    usage_webui_token: str = ""
    chat_input_cost_per_million: float = 2.0
    chat_output_cost_per_million: float = 8.0
    chat_cached_input_cost_per_million: float = 0.4
    chat_explicit_cached_input_cost_per_million: float = 0.2
    chat_cache_creation_input_cost_per_million: float = 2.5
    chat_explicit_prompt_cache: bool = True
    chat_long_context_threshold_tokens: int = 256000
    chat_long_input_cost_per_million: float = 6.0
    chat_long_output_cost_per_million: float = 24.0
    chat_long_cached_input_cost_per_million: float = 1.2
    chat_long_explicit_cached_input_cost_per_million: float = 0.6
    chat_long_cache_creation_input_cost_per_million: float = 7.5
    personality_setting: str = ""
    qdrant_uri: str = ""
    qdrant_api_key: str = ""
    chat_vector_dim: int = 1024
    media_vector_dim: int = 2560
    media_search_recall_limit: int = 6
    media_search_return_limit: int = 5
    # embedding 分路（硅基流动/OpenAI 风格接口）
    remote_embedding_base_url: str = ""
    remote_embedding_api_key: str = ""
    remote_embedding_model: str = ""
    # >0 时才透传给 embeddings API
    remote_embedding_dimensions: int = 1024
    # rerank 分路（硅基流动接口）
    remote_rerank_base_url: str = ""
    remote_rerank_api_key: str = ""
    remote_rerank_model: str = ""
    # 媒体 embedding 分路（OpenAI 风格 embeddings 接口）
    remote_media_embedding_provider: str = DASHSCOPE_MEDIA_EMBEDDING_PROVIDER  # 可选: "openai", "dashscope"
    remote_media_embedding_base_url: str = ""
    remote_media_embedding_api_key: str = ""
    remote_media_embedding_model: str = ""
    remote_media_embedding_dimensions: int = 2560
    # 媒体 rerank 分路（/v1/rerank）
    remote_media_rerank_provider: str = "openai"  # 可选: "openai", "dashscope"
    remote_media_rerank_base_url: str = ""
    remote_media_rerank_api_key: str = ""
    remote_media_rerank_model: str = ""
    tavily_api_key: str = ""
    summary_model: str = DASHSCOPE_SUMMARY_MODEL
    summary_base_url: str = DASHSCOPE_COMPATIBLE_BASE_URL
    summary_api_key: str = ""
    multimodal_model: str = DASHSCOPE_MULTIMODAL_MODEL
    multimodal_base_url: str = DASHSCOPE_COMPATIBLE_BASE_URL
    multimodal_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = ""
    openai_token: str = ""
    voice_enabled: bool = False
    voice_base_url: str = ""
    voice_text_lang: str = "zh"
    voice_speed_factor: float = 1.0
    voice_top_k: int = 15
    voice_top_p: float = 1.0
    voice_temperature: float = 1.0

    @property
    def chat_base_url(self) -> str:
        return _first_non_empty(
            self.openai_base_url,
            self.base_url,
        )

    @property
    def chat_model(self) -> str:
        return _first_non_empty(
            self.openai_model,
            self.model,
        )

    @property
    def chat_api_key(self) -> str:
        return _first_non_empty(self.openai_token, self.qwen_key)

    @property
    def summary_base_url_resolved(self) -> str:
        return self.summary_base_url.strip()

    @property
    def summary_model_resolved(self) -> str:
        return self.summary_model.strip()

    @property
    def summary_api_key_resolved(self) -> str:
        return _first_non_empty(self.summary_api_key, self.qwen_key, self.openai_token)

    @property
    def multimodal_base_url_resolved(self) -> str:
        return self.multimodal_base_url.strip()

    @property
    def multimodal_model_resolved(self) -> str:
        return self.multimodal_model.strip()

    @property
    def multimodal_api_key_resolved(self) -> str:
        return _first_non_empty(self.multimodal_api_key, self.qwen_key)

    @property
    def remote_media_embedding_provider_resolved(self) -> str:
        return _first_non_empty(self.remote_media_embedding_provider, DASHSCOPE_MEDIA_EMBEDDING_PROVIDER).lower()

    @property
    def remote_media_embedding_base_url_resolved(self) -> str:
        return _first_non_empty(
            self.remote_media_embedding_base_url,
            DASHSCOPE_MEDIA_EMBEDDING_BASE_URL
            if self.remote_media_embedding_provider_resolved == DASHSCOPE_MEDIA_EMBEDDING_PROVIDER
            else "",
        )

    @property
    def remote_media_embedding_model_resolved(self) -> str:
        return _first_non_empty(
            self.remote_media_embedding_model,
            DASHSCOPE_MEDIA_EMBEDDING_MODEL
            if self.remote_media_embedding_provider_resolved == DASHSCOPE_MEDIA_EMBEDDING_PROVIDER
            else "",
        )

    @property
    def remote_media_embedding_api_key_resolved(self) -> str:
        if self.remote_media_embedding_provider_resolved == DASHSCOPE_MEDIA_EMBEDDING_PROVIDER:
            return _first_non_empty(self.remote_media_embedding_api_key, self.qwen_key)
        return self.remote_media_embedding_api_key.strip()


class Config(BaseModel):
    groupmate_agent: ScopedConfig = Field(default_factory=ScopedConfig)
