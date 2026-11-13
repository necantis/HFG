"""
Tests for HFG Context Pack Generator (12-Agent Architecture).
"""

from pathlib import Path
import pytest
from src.context_pack import ContextPackGenerator, AGENT_SPECS


def test_agent_specs_completeness():
    # Exactly 12 agents (agent_00 through agent_11) must be registered
    assert len(AGENT_SPECS) == 12
    for i in range(0, 12):
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
    pack_path_01 = generator.write_context_pack("agent_01")
    assert pack_path_01.is_file()
    content_01 = pack_path_01.read_text(encoding="utf-8")
    assert "# Context Pack: Agent 01 — Data & Question Registry" in content_01
    assert "src/ingest/" in content_01
    assert "notebooks/01_ingest_exploration.ipynb" in content_01
    assert "answers_normalized_v1" in content_01
    assert "ADR-0005" in content_01
    assert "docs/AGENT_HANDOFFS/agent_01_handoff.md" in content_01

    # Generate for Agent 09 (Reviewer, NOT Orchestrator)
    pack_path_09 = generator.write_context_pack("agent_09")
    content_09 = pack_path_09.read_text(encoding="utf-8")
    assert "# Context Pack: Agent 09 — Final Integration Reviewer" in content_09
    assert "DOES NOT orchestrate pipelines" in content_09

    # Generate for Agent 11 (Orchestration & QA)
    pack_path_11 = generator.write_context_pack("agent_11")
    content_11 = pack_path_11.read_text(encoding="utf-8")
    assert "# Context Pack: Agent 11 — Orchestration & QA" in content_11
    assert "Sole owner of end-to-end pipeline execution" in content_11


def test_context_pack_generator_all(tmp_path):
    generator = ContextPackGenerator(base_dir=tmp_path)
    paths = generator.write_all_context_packs()
    assert len(paths) == 12
    for p in paths:
        assert p.is_file()


def test_context_pack_collaboration_and_branches(tmp_path):
    generator = ContextPackGenerator(base_dir=tmp_path)

    expected_branches = {
        "agent_01": "agent/01-ingestion-refinement",
        "agent_02": "agent/02-qualitative-refinement",
        "agent_07": "agent/07-runtime",
        "agent_10": "agent/10-collaboration-policy",
        "agent_11": "integration/wave-2a",
    }
    for agent_id, branch in expected_branches.items():
        assert AGENT_SPECS[agent_id].suggested_branch == branch
        pack = generator.write_context_pack(agent_id)
        content = pack.read_text(encoding="utf-8")
        assert branch in content
        assert "ADR-0007" in content
        assert "## 9. Git Collaboration, Shared-File Ownership & Artifact Handoff" in content
        assert "never push directly to `main`" in content
        assert "A planned artifact is not a completed artifact" in content

