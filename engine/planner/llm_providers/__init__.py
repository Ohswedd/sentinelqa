"""Provider-specific LLM planner adapters (ADR-0011).

Each provider is imported lazily by :func:`engine.planner.llm_adapter.build_llm_planner`
so SentinelQA never imports a vendor SDK unless that vendor is selected.
"""

from __future__ import annotations
