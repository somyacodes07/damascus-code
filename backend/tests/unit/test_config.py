"""
Unit tests for the Damascus configuration system.
Tests the layered config, environment parsing, and validation.
"""

from __future__ import annotations

import os
import pytest

from damascus.config import Environment, Settings


def test_default_settings():
    """Configuration should have sensible defaults."""
    s = Settings()
    assert s.env == Environment.DEVELOPMENT
    assert s.server.port == 8000
    assert s.database.pool_size == 20
    assert s.redis.db == 0
    assert s.models.ollama.enabled is True


def test_environment_enum():
    """Environment enum values should be lowercase strings."""
    assert Environment.DEVELOPMENT == "development"
    assert Environment.TESTING == "testing"
    assert Environment.PRODUCTION == "production"


def test_is_development(monkeypatch):
    """is_development should return True in development mode."""
    monkeypatch.setenv("DAMASCUS_ENV", "development")
    s = Settings()
    assert s.is_development is True
    assert s.is_production is False


def test_is_production(monkeypatch):
    """is_production should return True in production mode."""
    monkeypatch.setenv("DAMASCUS_ENV", "production")
    s = Settings()
    assert s.is_production is True
    assert s.is_development is False


def test_has_any_provider_ollama_enabled(monkeypatch):
    """has_any_provider should be True when Ollama is enabled."""
    monkeypatch.setenv("DAMASCUS_MODELS_OLLAMA_ENABLED", "true")
    s = Settings()
    assert s.models.has_any_provider is True


def test_has_any_provider_all_disabled(monkeypatch):
    """has_any_provider should be False when all providers are disabled."""
    monkeypatch.setenv("DAMASCUS_MODELS_OLLAMA_ENABLED", "false")
    monkeypatch.setenv("DAMASCUS_MODELS_OPENAI_ENABLED", "false")
    monkeypatch.setenv("DAMASCUS_MODELS_ANTHROPIC_ENABLED", "false")
    monkeypatch.setenv("DAMASCUS_MODELS_GEMINI_ENABLED", "false")
    monkeypatch.setenv("DAMASCUS_MODELS_OPENROUTER_ENABLED", "false")
    s = Settings()
    assert s.models.has_any_provider is False


def test_feature_flags_default_off():
    """All Phase 2+ feature flags should be disabled by default in V1."""
    s = Settings()
    assert s.features.dynamic_team_generation is False
    assert s.features.active_research is False
    assert s.features.knowledge_graph is False
    assert s.features.evolution_arena is False
    assert s.features.mcp_gateway is False


def test_evolution_disabled_by_default():
    """Evolution should be disabled and manual-approval-only by default."""
    s = Settings()
    assert s.evolution.enabled is False
    assert s.evolution.auto_promote is False


def test_security_defaults():
    """Security should be in strict mode by default."""
    s = Settings()
    assert s.security.require_approval_for_tools is True
    assert s.security.sandbox_enabled is True
    assert s.security.audit_enabled is True
