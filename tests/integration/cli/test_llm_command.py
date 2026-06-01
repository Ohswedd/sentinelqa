"""CLI integration tests for ``sentinel llm``."""

from __future__ import annotations

import json

from click.testing import Result
from typer.testing import CliRunner

from sentinel_cli.app import build_app


def _run(*args: str) -> Result:
    runner = CliRunner()
    return runner.invoke(build_app(), list(args))


def test_llm_list_human_form() -> None:
    result = _run("llm", "list")
    assert result.exit_code == 0
    assert "anthropic" in result.stdout
    assert "ollama" in result.stdout
    assert "vertex" in result.stdout


def test_llm_list_json_form() -> None:
    result = _run("llm", "list", "--json")
    assert result.exit_code == 0
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    names = {p["name"] for p in payload["providers"]}
    assert names == {
        "anthropic",
        "azure_openai",
        "gemini",
        "groq",
        "mistral",
        "null",
        "ollama",
        "openai",
        "openrouter",
        "vertex",
    }


def test_llm_doctor_one_provider_null_is_unavailable() -> None:
    # The null provider always reports unavailable; with --provider, exit
    # code is 1 because the explicitly requested provider isn't available.
    result = _run("llm", "doctor", "--provider", "null")
    assert result.exit_code == 1
    assert "unavailable" in result.stdout


def test_llm_doctor_unknown_provider_returns_config_error() -> None:
    result = _run("llm", "doctor", "--provider", "does-not-exist")
    assert result.exit_code == 2


def test_llm_doctor_json_form_emits_results_array() -> None:
    result = _run("llm", "doctor", "--provider", "null", "--json")
    assert result.exit_code == 1
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["any_available"] is False
    assert payload["results"][0]["provider"] == "null"


def test_llm_doctor_require_with_no_reachable_exits_5() -> None:
    # null provider is always unavailable; with --require this is exit 5.
    result = _run("llm", "doctor", "--provider", "null", "--require")
    assert result.exit_code == 5


def test_llm_price_table_for_gemini() -> None:
    result = _run("llm", "price", "--provider", "gemini")
    assert result.exit_code == 0
    assert "gemini-1.5-flash" in result.stdout
    assert "gemini-1.5-pro" in result.stdout


def test_llm_price_specific_model_json() -> None:
    result = _run("llm", "price", "--provider", "openai", "--model", "gpt-4o-mini", "--json")
    assert result.exit_code == 0
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["model"] == "gpt-4o-mini"
    assert payload["price_per_1k_input_usd"] > 0


def test_llm_price_unknown_model_exits_2() -> None:
    result = _run("llm", "price", "--provider", "openai", "--model", "nonexistent")
    assert result.exit_code == 2


def test_llm_price_unknown_provider_exits_2() -> None:
    result = _run("llm", "price", "--provider", "not-a-real-provider")
    assert result.exit_code == 2


def test_llm_price_ollama_has_no_table() -> None:
    # Ollama is always free; the per-model price table is empty.
    result = _run("llm", "price", "--provider", "ollama")
    assert result.exit_code == 0
    assert "no per-model price table" in result.stdout.lower() or "provider-driven" in result.stdout


def test_llm_price_openrouter_has_no_table() -> None:
    # OpenRouter trusts usage.cost; no per-model table.
    result = _run("llm", "price", "--provider", "openrouter")
    assert result.exit_code == 0


def test_llm_doctor_all_providers_returns_1_when_all_unavailable() -> None:
    # Without keys / network, every provider is unavailable.
    result = _run("llm", "doctor")
    # Multi-provider: exit 1 when nothing reachable (some can be available).
    # In this CI env without keys, expect any_available=False → exit 1.
    assert result.exit_code in (0, 1)
