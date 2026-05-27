"""SentinelQA configuration layer.

Loads, validates, and renders ``sentinel.config.yaml`` (PRD §17). All
configuration goes through this package; ad-hoc YAML reads in other
modules are forbidden (CLAUDE.md §12).
"""

from __future__ import annotations

from engine.config.loader import dump_config, load_config
from engine.config.schema import (
    AuthConfig,
    ModulesConfig,
    PerformanceBudgets,
    PerformanceConfig,
    PolicyConfig,
    ProjectConfig,
    ReportConfig,
    RootConfig,
    SecurityConfig,
    SourceConfig,
    TargetConfig,
    VisualConfig,
)
from engine.config.schema_check import ConfigCheckError, validate_config_dict

__all__ = [
    "load_config",
    "dump_config",
    "RootConfig",
    "ProjectConfig",
    "SourceConfig",
    "TargetConfig",
    "AuthConfig",
    "ModulesConfig",
    "SecurityConfig",
    "PerformanceConfig",
    "PerformanceBudgets",
    "VisualConfig",
    "PolicyConfig",
    "ReportConfig",
    "validate_config_dict",
    "ConfigCheckError",
]
