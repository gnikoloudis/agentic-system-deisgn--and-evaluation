"""Global configuration and settings for HarnessForge."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Literal, Optional
from pydantic import BaseModel, Field


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BLUEPRINTS_DIR = ROOT_DIR / "blueprints"
TASKS_DIR = ROOT_DIR / "tasks"
SAMPLE_REPOS_DIR = TASKS_DIR / "sample_repos"
WORKSPACES_DIR = ROOT_DIR / ".harness-workspaces"
DATA_DIR = ROOT_DIR / ".harness-data"
DB_PATH = DATA_DIR / "harnessforge.db"
APP_CONFIG_PATH = DATA_DIR / "app_config.json"


class TokenPriceRate(BaseModel):
    """Token cost rates in USD per 1,000,000 tokens."""

    input_per_1m: float = Field(default=3.0, ge=0.0)
    output_per_1m: float = Field(default=15.0, ge=0.0)
    cache_read_per_1m: float = Field(default=0.30, ge=0.0)


def build_default_provider_pricing() -> Dict[str, Dict[str, TokenPriceRate]]:
    """Default per-LLM-provider, per-tier token pricing (USD per 1M tokens)."""
    return {
        "anthropic": {
            "default": TokenPriceRate(input_per_1m=3.0, output_per_1m=15.0, cache_read_per_1m=0.30),
            "reasoning": TokenPriceRate(input_per_1m=15.0, output_per_1m=75.0, cache_read_per_1m=1.50),
            "coding": TokenPriceRate(input_per_1m=3.0, output_per_1m=15.0, cache_read_per_1m=0.30),
            "fast": TokenPriceRate(input_per_1m=0.80, output_per_1m=4.0, cache_read_per_1m=0.08),
            "free": TokenPriceRate(input_per_1m=0.0, output_per_1m=0.0, cache_read_per_1m=0.0),
        },
        "google": {
            "default": TokenPriceRate(input_per_1m=2.50, output_per_1m=12.0, cache_read_per_1m=0.25),
            "reasoning": TokenPriceRate(input_per_1m=10.0, output_per_1m=40.0, cache_read_per_1m=1.00),
            "coding": TokenPriceRate(input_per_1m=4.0, output_per_1m=18.0, cache_read_per_1m=0.40),
            "fast": TokenPriceRate(input_per_1m=0.50, output_per_1m=2.50, cache_read_per_1m=0.05),
            "free": TokenPriceRate(input_per_1m=0.0, output_per_1m=0.0, cache_read_per_1m=0.0),
        },
        "opencode": {
            "default": TokenPriceRate(input_per_1m=1.80, output_per_1m=7.50, cache_read_per_1m=0.18),
            "reasoning": TokenPriceRate(input_per_1m=3.0, output_per_1m=12.0, cache_read_per_1m=0.30),
            "coding": TokenPriceRate(input_per_1m=1.80, output_per_1m=7.50, cache_read_per_1m=0.18),
            "fast": TokenPriceRate(input_per_1m=0.40, output_per_1m=1.60, cache_read_per_1m=0.04),
            "free": TokenPriceRate(input_per_1m=0.0, output_per_1m=0.0, cache_read_per_1m=0.0),
        },
        "openai": {
            "default": TokenPriceRate(input_per_1m=2.50, output_per_1m=10.0, cache_read_per_1m=1.25),
            "reasoning": TokenPriceRate(input_per_1m=15.0, output_per_1m=60.0, cache_read_per_1m=7.50),
            "coding": TokenPriceRate(input_per_1m=2.50, output_per_1m=10.0, cache_read_per_1m=1.25),
            "fast": TokenPriceRate(input_per_1m=0.15, output_per_1m=0.60, cache_read_per_1m=0.075),
            "free": TokenPriceRate(input_per_1m=0.0, output_per_1m=0.0, cache_read_per_1m=0.0),
        },
    }


class TokenPricingConfig(BaseModel):
    """Configurable token pricing per LLM provider & tier, plus optional per-model ID overrides."""

    providers: Dict[str, Dict[str, TokenPriceRate]] = Field(default_factory=build_default_provider_pricing)
    model_overrides: Dict[str, TokenPriceRate] = Field(default_factory=dict)


class AppUserConfig(BaseModel):
    """User-configurable application settings persisted to .harness-data/app_config.json."""

    target_harness: Literal["claude_code", "antigravity", "opencode"] = Field(
        default="claude_code",
        description="Selected target harness for the session.",
    )
    harness_locked: bool = Field(
        default=False,
        description="When True, locks the target harness across the Studio until explicitly unlocked.",
    )
    token_pricing: TokenPricingConfig = Field(default_factory=TokenPricingConfig)


def get_app_config() -> AppUserConfig:
    """Load persisted AppUserConfig from .harness-data/app_config.json (creating defaults if absent)."""
    ensure_directories()
    if APP_CONFIG_PATH.exists():
        try:
            raw = json.loads(APP_CONFIG_PATH.read_text(encoding="utf-8"))
            cfg = AppUserConfig.model_validate(raw)
            # Ensure built-in providers always exist even if older config omitted one
            defaults = build_default_provider_pricing()
            for prov, tiers in defaults.items():
                if prov not in cfg.token_pricing.providers:
                    cfg.token_pricing.providers[prov] = tiers
                else:
                    for tier_k, rate in tiers.items():
                        cfg.token_pricing.providers[prov].setdefault(tier_k, rate)
            return cfg
        except Exception:
            pass
    default_cfg = AppUserConfig()
    APP_CONFIG_PATH.write_text(default_cfg.model_dump_json(indent=2), encoding="utf-8")
    return default_cfg


def save_app_config(cfg: AppUserConfig) -> AppUserConfig:
    """Persist AppUserConfig to .harness-data/app_config.json."""
    ensure_directories()
    APP_CONFIG_PATH.write_text(cfg.model_dump_json(indent=2), encoding="utf-8")
    return cfg


def reset_app_token_pricing() -> AppUserConfig:
    """Reset token pricing back to built-in per-provider defaults while preserving harness lock settings."""
    cfg = get_app_config()
    cfg.token_pricing = TokenPricingConfig()
    return save_app_config(cfg)


class JudgeProviderConfig(BaseModel):
    """Configuration for LLM-as-a-Judge and AI Architecture Advisor."""

    mode: Literal["harness_cli", "api_key", "heuristic_fallback"] = Field(
        default="harness_cli",
        description="Whether to use an installed harness CLI (claude/opencode/agy) or direct LLM API key.",
    )
    harness_cli: Literal["claude_code", "opencode", "antigravity"] = Field(
        default="claude_code",
        description="Which harness CLI to invoke when mode == 'harness_cli'.",
    )
    api_provider: Literal["anthropic", "openai", "gemini", "openrouter", "ollama"] = Field(
        default="anthropic",
        description="Which direct API provider to call when mode == 'api_key'.",
    )
    model: str = Field(
        default="claude-3-7-sonnet-latest",
        description="Model identifier for API or CLI invocation.",
    )
    api_key: Optional[str] = Field(
        default=None,
        description="Optional API key override (falls back to environment variables).",
    )
    base_url: Optional[str] = Field(
        default=None,
        description="Optional custom endpoint (e.g. Ollama http://localhost:11434/v1 or OpenRouter).",
    )


class AppSettings(BaseModel):
    """Runtime settings for HarnessForge server and CLI."""

    host: str = "127.0.0.1"
    port: int = 8765
    claude_binary: str = os.environ.get("CLAUDE_BINARY", "claude")
    opencode_binary: str = os.environ.get("OPENCODE_BINARY", "opencode")
    antigravity_binary: str = os.environ.get("AGY_BINARY", "agy")
    judge: JudgeProviderConfig = Field(default_factory=JudgeProviderConfig)


def ensure_directories() -> None:
    """Ensure required project directories exist."""
    for directory in (BLUEPRINTS_DIR, TASKS_DIR, SAMPLE_REPOS_DIR, WORKSPACES_DIR, DATA_DIR):
        directory.mkdir(parents=True, exist_ok=True)


settings = AppSettings()
