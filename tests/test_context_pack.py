"""
Tests for HFG Context Pack Generator.
"""

from pathlib import Path
import pytest
from src.context_pack import ContextPackGenerator, AGENT_SPECS


def test_agent_specs_completeness():
    # Exactly 10 agents must be registered
    assert len(AGENT_SPECS) == 10
    for i in range(1, 11):
        key = f"agent_{i:02d}"
        assert key in AGENT_SPECS
        spec = AGENT_SPECS[key]
        assert spec.agent_id == key
        assert len(spec.owned_files) > 0
        assert spec.owned_notebook.startswith("notebooks/")
        assert len(spec.forbidden_files) > 0
        assert len(spec.acceptance_criteria) > 0
        assert len(spec.test_commands) > 0


def test_context_pack_generation(tmp_path):
    generator = ContextPackGenerator(base_dir=tmp_path)

    # Generate for Agent 01
    pack_path = generator.write_context_pack("agent_01")
    assert pack_path.is_file()
    content = pack_path.read_text(encoding="utf-8")

    assert "# Context Pack: Agent 01 — Ingestion & Normalization Engineer" in content
    assert "src/ingest/" in content
    assert "notebooks/01_ingest_exploration.ipynb" in content
    assert "answers_normalized_v1" in content
    assert "ADR-0001" in content
    assert "docs/AGENT_HANDOFFS/agent_01_handoff.md" in content


def test_context_pack_generator_all(tmp_path):
    generator = ContextPackGenerator(base_dir=tmp_path)
    paths = generator.write_all_context_packs()
    assert len(paths) == 10
    for p in paths:
        assert p.is_file()
