"""
Tests for HFG Artifact Registry & Provenance Manager.
"""

import json
from pathlib import Path
import pytest
from src.artifact_registry import (
    ArtifactRegistry,
    AUTHORITY_IMMUTABLE_SOURCE,
    AUTHORITY_PRESENTATION_ONLY,
    AUTHORITY_CANONICAL_INGESTION,
    AUTHORITY_CANONICAL_UTILITY,
)


def test_register_artifact_and_provenance(tmp_path):
    registry = ArtifactRegistry(base_dir=tmp_path, run_id="run_test_001")

    # Create dummy source file and code module
    code_file = tmp_path / "src" / "dummy_module.py"
    code_file.parent.mkdir(parents=True, exist_ok=True)
    code_file.write_text("print('test')", encoding="utf-8")

    out_file = tmp_path / "data" / "out.parquet"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("binary_dummy_content", encoding="utf-8")

    record = registry.register_artifact(
        artifact_id="test_art_01",
        path="data/out.parquet",
        format="parquet",
        producing_module="src/dummy_module.py",
        producing_agent="agent_01",
        schema_version="v1.0.0",
        validation_status="valid",
        upstream_artifacts=[],
        downstream_consumers=["agent_02"],
    )

    assert record.artifact_id == "test_art_01"
    assert record.run_id == "run_test_001"
    assert record.producing_agent == "agent_01"
    assert record.stale_state == "fresh"
    assert str(out_file) in record.source_hashes
    assert str(code_file) in record.source_hashes


def test_canonical_rule_forbids_report_as_analytical_input(tmp_path):
    registry = ArtifactRegistry(base_dir=tmp_path, run_id="run_test_001")

    # Register a presentation report
    report_file = tmp_path / "runs" / "run_test_001" / "reports" / "brief.md"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text("# Policy Brief", encoding="utf-8")

    registry.register_artifact(
        artifact_id="final_report_v1",
        path="runs/run_test_001/reports/brief.md",
        format="md",
        producing_module="src/reporting/report.py",
        producing_agent="agent_07",
        authority_level=AUTHORITY_PRESENTATION_ONLY,
    )

    # Attempting to register an analytical artifact that depends on final_report_v1 MUST FAIL!
    with pytest.raises(ValueError, match="Canonical Rule Violation"):
        registry.register_artifact(
            artifact_id="illegal_analytical_artifact",
            path="data/processed/illegal.json",
            format="json",
            producing_module="src/preference/learn.py",
            producing_agent="agent_04",
            upstream_artifacts=["final_report_v1"],
        )


def test_raw_source_immutability(tmp_path):
    registry = ArtifactRegistry(base_dir=tmp_path, run_id="run_test_001")

    raw_file = tmp_path / "data" / "raw" / "survey.csv"
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    raw_file.write_text("id,ans\n1,yes\n", encoding="utf-8")

    registry.register_artifact(
        artifact_id="raw_survey_test",
        path="data/raw/survey.csv",
        format="csv",
        producing_module="data/raw/survey.csv",
        producing_agent="external",
        authority_level=AUTHORITY_IMMUTABLE_SOURCE,
    )

    # Modify raw file on disk
    raw_file.write_text("id,ans\n1,corrupted\n", encoding="utf-8")

    # Re-registering with different content must violate immutability invariant
    with pytest.raises(ValueError, match="Canonical Invariant Violation"):
        registry.register_artifact(
            artifact_id="raw_survey_test",
            path="data/raw/survey.csv",
            format="csv",
            producing_module="data/raw/survey.csv",
            producing_agent="external",
            authority_level=AUTHORITY_IMMUTABLE_SOURCE,
        )


def test_staleness_cascade_propagation(tmp_path):
    registry = ArtifactRegistry(base_dir=tmp_path, run_id="run_test_001")

    # 1. Upstream
    f1 = tmp_path / "f1.txt"
    f1.write_text("hello", encoding="utf-8")
    registry.register_artifact(
        artifact_id="art_upstream",
        path="f1.txt",
        format="txt",
        producing_module="mod1.py",
        producing_agent="agent_01",
    )

    # 2. Downstream
    f2 = tmp_path / "f2.txt"
    f2.write_text("world", encoding="utf-8")
    registry.register_artifact(
        artifact_id="art_downstream",
        path="f2.txt",
        format="txt",
        producing_module="mod2.py",
        producing_agent="agent_02",
        upstream_artifacts=["art_upstream"],
    )

    assert registry.get_artifact("art_downstream").stale_state == "fresh"

    # Mark upstream stale and propagate
    registry.artifacts["art_upstream"].stale_state = "stale"
    registry.propagate_staleness("art_upstream")

    assert registry.get_artifact("art_downstream").stale_state == "stale"


def test_manifest_and_run_card_generation(tmp_path):
    registry = ArtifactRegistry(base_dir=tmp_path, run_id="run_test_card")

    manifest_file = registry.save_manifest()
    assert manifest_file.is_file()

    # Load into new registry instance
    new_reg = ArtifactRegistry(base_dir=tmp_path, run_id="run_test_card")
    new_reg.load_manifest(manifest_file)
    assert new_reg.run_id == "run_test_card"

    card_text = new_reg.generate_run_card(
        run_id="run_test_card",
        completed_stages=["Stage 1", "Stage 2"],
    )
    assert "Run Card: `run_test_card`" in card_text
    assert (tmp_path / "runs" / "run_test_card" / "RUN_CARD.md").is_file()
