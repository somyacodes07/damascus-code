"""
Damascus Configuration System
==============================
Layered configuration following the hierarchy defined in docs:

  Layer 1: Code defaults (built into this file)
  Layer 2: .env file (damascus.toml is future work; for now we use .env)
  Layer 3: Environment variables (always override .env)
  Layer 4: Workspace settings (stored in DB, handled by workspace service)
  Layer 5: CLI arguments (handled per-command)

All settings follow the naming convention: DAMASCUS_{SECTION}_{SETTING}
Secrets (API keys, passwords) must NEVER be logged or committed to source control.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class ServerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DAMASCUS_SERVER_", env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    debug: bool = False


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DAMASCUS_DATABASE_", env_file=".env", extra="ignore")

    url: str = "postgresql+asyncpg://damascus:damascus_dev@localhost:5432/damascus"
    pool_size: int = 20
    max_overflow: int = 10
    pool_pre_ping: bool = True


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DAMASCUS_REDIS_", env_file=".env", extra="ignore")

    url: str = "redis://localhost:6379"
    db: int = 0
    max_connections: int = 50


class QdrantSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DAMASCUS_QDRANT_", env_file=".env", extra="ignore")

    url: str = "http://localhost:6333"
    collection_memories: str = "damascus_memories"
    vector_size: int = 1536  # Compatible with OpenAI/Ollama embedding dimensions


class NATSSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DAMASCUS_NATS_", env_file=".env", extra="ignore")

    url: str = "nats://localhost:4222"
    stream_name: str = "DAMASCUS"


class StorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DAMASCUS_STORAGE_", env_file=".env", extra="ignore")

    endpoint: str = "localhost:9000"
    access_key: str = "damascus"
    secret_key: str = "damascus_dev"
    bucket: str = "damascus"
    secure: bool = False


class OllamaModelSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DAMASCUS_MODELS_OLLAMA_", env_file=".env", extra="ignore")

    enabled: bool = True
    endpoint: str = "http://localhost:11434"
    default_model: str = "llama3.1"


class OpenAIModelSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DAMASCUS_MODELS_OPENAI_", env_file=".env", extra="ignore")

    enabled: bool = False
    api_key: str = ""
    default_model: str = "gpt-4o-mini"


class AnthropicModelSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DAMASCUS_MODELS_ANTHROPIC_", env_file=".env", extra="ignore")

    enabled: bool = False
    api_key: str = ""
    default_model: str = "claude-3-5-haiku-20241022"


class GeminiModelSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DAMASCUS_MODELS_GEMINI_", env_file=".env", extra="ignore")

    enabled: bool = False
    api_key: str = ""
    default_model: str = "gemini-1.5-flash"


class OpenRouterModelSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DAMASCUS_MODELS_OPENROUTER_", env_file=".env", extra="ignore")

    enabled: bool = False
    api_key: str = ""
    default_model: str = "openai/gpt-4o-mini"


class ModelsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ollama: OllamaModelSettings = Field(default_factory=OllamaModelSettings)
    openai: OpenAIModelSettings = Field(default_factory=OpenAIModelSettings)
    anthropic: AnthropicModelSettings = Field(default_factory=AnthropicModelSettings)
    gemini: GeminiModelSettings = Field(default_factory=GeminiModelSettings)
    openrouter: OpenRouterModelSettings = Field(default_factory=OpenRouterModelSettings)

    @property
    def has_any_provider(self) -> bool:
        """Returns True if at least one model provider is enabled."""
        return any([
            self.ollama.enabled,
            self.openai.enabled and bool(self.openai.api_key),
            self.anthropic.enabled and bool(self.anthropic.api_key),
            self.gemini.enabled and bool(self.gemini.api_key),
            self.openrouter.enabled and bool(self.openrouter.api_key),
        ])


class SecuritySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DAMASCUS_SECURITY_", env_file=".env", extra="ignore")

    secret_key: str = "change-this-to-a-random-secret-in-production"
    require_approval_for_tools: bool = True
    sandbox_enabled: bool = True
    audit_enabled: bool = True


class EvolutionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DAMASCUS_EVOLUTION_", env_file=".env", extra="ignore")

    enabled: bool = False
    auto_promote: bool = False
    max_concurrent_experiments: int = 3


class ObservabilitySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DAMASCUS_OBSERVABILITY_", env_file=".env", extra="ignore")

    tracing_enabled: bool = True
    metrics_enabled: bool = True
    log_level: Literal["debug", "info", "warning", "error", "critical"] = "info"


class FeatureFlags(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DAMASCUS_FEATURES_", env_file=".env", extra="ignore")

    # Phase 2+ features — disabled by default in V1
    dynamic_team_generation: bool = False
    active_research: bool = False
    knowledge_graph: bool = False
    evolution_arena: bool = False
    mcp_gateway: bool = False


class Settings(BaseSettings):
    """
    Root configuration object for Damascus.
    Access via the module-level `settings` singleton.
    """
    model_config = SettingsConfigDict(env_prefix="DAMASCUS_", env_file=".env", extra="ignore")

    env: Environment = Environment.DEVELOPMENT
    debug: bool = False
    log_level: Literal["debug", "info", "warning", "error", "critical"] = "info"

    # Sub-configurations
    server: ServerSettings = Field(default_factory=ServerSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    nats: NATSSettings = Field(default_factory=NATSSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    models: ModelsSettings = Field(default_factory=ModelsSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    evolution: EvolutionSettings = Field(default_factory=EvolutionSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    features: FeatureFlags = Field(default_factory=FeatureFlags)

    @field_validator("env", mode="before")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Normalize environment string."""
        return v.lower() if isinstance(v, str) else v

    @property
    def is_development(self) -> bool:
        return self.env == Environment.DEVELOPMENT

    @property
    def is_testing(self) -> bool:
        return self.env == Environment.TESTING

    @property
    def is_production(self) -> bool:
        return self.env == Environment.PRODUCTION


# ---------------------------------------------------------------------------
# Module-level singleton — import this in all modules
# ---------------------------------------------------------------------------
settings = Settings()
