"""Unit coverage for :mod:`modules.api.graphql`."""

from __future__ import annotations

from pathlib import Path

from modules.api.graphql import load_graphql


def test_load_graphql_returns_query_operations(tmp_path: Path) -> None:
    sdl = """
    type Query {
      hello: String
      count: Int!
      items: [Item!]!
    }

    type Item {
      id: ID!
      name: String!
    }
    """
    path = tmp_path / "schema.graphql"
    path.write_text(sdl, encoding="utf-8")
    schema = load_graphql(path)
    field_names = {op.field_name for op in schema.operations}
    assert {"hello", "count", "items"} <= field_names


def test_load_graphql_skips_ops_with_required_arguments(tmp_path: Path) -> None:
    sdl = """
    type Query {
      lookup(id: ID!): String
      free: String
    }
    """
    path = tmp_path / "schema.graphql"
    path.write_text(sdl, encoding="utf-8")
    schema = load_graphql(path)
    field_names = {op.field_name for op in schema.operations}
    assert "lookup" not in field_names
    assert "free" in field_names


def test_mutation_operations_are_extracted(tmp_path: Path) -> None:
    sdl = """
    type Query {
      ping: Boolean
    }
    type Mutation {
      reset: Boolean
    }
    """
    path = tmp_path / "schema.graphql"
    path.write_text(sdl, encoding="utf-8")
    schema = load_graphql(path)
    kinds = {op.kind for op in schema.operations}
    assert "query" in kinds
    assert "mutation" in kinds


def test_snapshot_endpoints_per_operation(tmp_path: Path) -> None:
    sdl = """
    type Query {
      stats: Stats!
    }
    type Stats {
      total: Int!
      label: String
    }
    """
    path = tmp_path / "schema.graphql"
    path.write_text(sdl, encoding="utf-8")
    schema = load_graphql(path)
    snapshot = schema.snapshot_endpoints()
    assert len(snapshot) == 1
    entry = snapshot[0]
    assert entry.method == "POST"
    assert "total" in entry.required_response_fields


def test_optional_arg_with_default_is_safe_to_probe(tmp_path: Path) -> None:
    sdl = """
    type Query {
      greet(name: String = "world"): String
    }
    """
    path = tmp_path / "schema.graphql"
    path.write_text(sdl, encoding="utf-8")
    schema = load_graphql(path)
    assert any(op.field_name == "greet" for op in schema.operations)


def test_selection_string_handles_scalar_return(tmp_path: Path) -> None:
    sdl = """
    type Query {
      version: String
    }
    """
    path = tmp_path / "schema.graphql"
    path.write_text(sdl, encoding="utf-8")
    schema = load_graphql(path)
    op = schema.operations[0]
    assert op.selection == ""
