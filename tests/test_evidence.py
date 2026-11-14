"""Tests for Agent 03 Evidence Ledger, Provenance Lock, and Production Reconciliation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import pytest

from src.contracts import MissingnessState, ResponseEpistemicStatus
from src.evidence.evidence_ledger import (
    EvidenceIntegrityError,
    EvidenceLedger,
    ProvenanceVerificationError,
)
from src.evidence.reconciliation import (
    EvidenceReconciler,
    align_alternative_vocabularies,
)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_fixture_workspace(tmp_path: Path) -> Dict[str, Any]:
    """Create a minimal valid dual-coder workspace for isolated unit testing."""
    (tmp_path / "data" / "normalized").mkdir(parents=True)
    (tmp_path / "data" / "processed").mkdir(parents=True)

    # 3 participants x 2 questions (136 not required when require_baseline_raw_sha=False; matches usable count)
    resp_texts = {
        ("P1", "Q07"): ("Prefer option alpha strongly over beta.", MissingnessState.OBSERVED_USABLE.value, ResponseEpistemicStatus.SUBSTANTIVE.value, True),
        ("P2", "Q07"): ("I prefer option beta cleanly.", MissingnessState.OBSERVED_USABLE.value, ResponseEpistemicStatus.SUBSTANTIVE.value, True),
        ("P3", "Q07"): ("", MissingnessState.MISSING_RAW_BLANK.value, ResponseEpistemicStatus.RAW_BLANK.value, False),
        ("P1", "Q08"): ("Assign responsibility centrally at institute level.", MissingnessState.OBSERVED_USABLE.value, ResponseEpistemicStatus.SUBSTANTIVE.value, True),
        ("P2", "Q08"): ("No opinion on this matter.", MissingnessState.MISSING_NON_SUBSTANTIVE.value, ResponseEpistemicStatus.EXPLICIT_NO_OPINION.value, True),
        ("P3", "Q08"): ("???", MissingnessState.MISSING_NON_SUBSTANTIVE.value, ResponseEpistemicStatus.PUNCTUATION_UNINTERPRETABLE.value, True),
    }

    rows: List[Dict[str, Any]] = []
    for (pid, qid), (txt, miss, ep, supplied) in sorted(resp_texts.items()):
        rows.append(
            {
                "response_id": f"RESP_{pid}_{qid}",
                "participant_id": pid,
                "question_id": qid,
                "detected_language": "en",
                "source_text": txt,
                "raw_value": txt,
                "raw_response_sha256": _sha256_text(txt),
                "text_supplied": supplied,
                "missingness_state": miss,
                "epistemic_status": ep,
            }
        )

    df = pd.DataFrame(rows)
    parquet_path = tmp_path / "data" / "normalized" / "answers_normalized.parquet"
    json_path = tmp_path / "data" / "normalized" / "answers_normalized.json"
    df.to_parquet(parquet_path, index=False)
    json_path.write_text(json.dumps({"records": rows}, indent=2), encoding="utf-8")

    q_reg = {
        "questions": {
            "Q07": {
                "question_id": "Q07",
                "question_index": 7,
                "is_primary_question": True,
                "question_scope": "primary",
                "canonical_prompt_en": "Decision question 7",
                "column_headers_by_lang": {"en": "Question 7"},
                "analytical_frame": "GOVERNANCE_GOODS_ALLOCATION",
                "economic_good_classification_policy": "ENABLED",
                "missing_response_count": 1,
            },
            "Q08": {
                "question_id": "Q08",
                "question_index": 8,
                "is_primary_question": True,
                "question_scope": "primary",
                "canonical_prompt_en": "Governance question 8",
                "column_headers_by_lang": {"en": "Question 8"},
                "analytical_frame": "GOVERNANCE_GOODS_ALLOCATION",
                "economic_good_classification_policy": "ENABLED",
                "missing_response_count": 2,
            },
        }
    }
    q_reg_path = tmp_path / "data" / "normalized" / "question_registry.json"
    q_reg_path.write_text(json.dumps(q_reg, indent=2), encoding="utf-8")

    def _span(sp_id: str, pid: str, qid: str, quote: str) -> Dict[str, Any]:
        src = resp_texts[(pid, qid)][0]
        start = src.index(quote)
        end = start + len(quote)
        return {
            "span_id": sp_id,
            "participant_id": pid,
            "question_id": qid,
            "response_id": f"RESP_{pid}_{qid}",
            "detected_language": "en",
            "verbatim_quote": quote,
            "char_start": start,
            "char_end": end,
            "raw_response_sha256": _sha256_text(src),
            "missingness_state": resp_texts[(pid, qid)][1],
            "span_role": "substantive_evidence",
        }

    # Build Coder A and Coder B payloads
    spans_a = [
        _span("SA_1", "P1", "Q07", "Prefer option alpha strongly over beta."),
        _span("SA_2", "P2", "Q07", "I prefer option beta cleanly."),
        _span("SA_3", "P1", "Q08", "Assign responsibility centrally at institute level."),
    ]
    spans_b = [
        _span("SB_1", "P1", "Q07", "Prefer option alpha strongly over beta."),
        _span("SB_2", "P2", "Q07", "I prefer option beta cleanly."),
        _span("SB_3", "P1", "Q08", "Assign responsibility centrally at institute level."),
    ]

    def _non_pref_crs(coder_id: str) -> List[Dict[str, Any]]:
        out = []
        for (pid, qid), (_, miss, ep, _) in sorted(resp_texts.items()):
            if miss == MissingnessState.OBSERVED_USABLE.value:
                continue
            out.append(
                {
                    "coding_id": f"COD_{coder_id}_{qid}_{pid}_NP",
                    "participant_id": pid,
                    "question_id": qid,
                    "subtopic_id": f"{qid}_MISSING",
                    "coder_source": coder_id,
                    "missingness_state": miss,
                    "epistemic_status": ep,
                    "alternative_probabilities": {},
                    "semantic_importance": None,
                    "coder_confidence": None,
                    "coder_agreement": 0.0,
                    "coder_agreement_status": "PRE_RECONCILIATION_AGENT_03_PENDING",
                    "derived_scalar_score": None,
                    "economic_good_class": None,
                    "probability_interpretation": None,
                    "evidence_span_ids": [],
                }
            )
        return out

    common_src_hash = "deadbeef" * 8
    coder_a_payload = {
        "run_id": "run_test_001",
        "coder_id": "coder_a",
        "execution_profile": "production",
        "production_eligible": True,
        "synthetic_or_test_execution": False,
        "execution_mode": "GPU_LIVE",
        "execution_metadata": {
            "execution_profile": "production",
            "production_eligible": True,
            "synthetic_or_test_execution": False,
            "execution_mode": "GPU_LIVE",
            "model_family": "deepseek",
            "model_repo": "example/coder-a",
            "model_revision": "rev_a_111",
            "quantization": "AWQ",
            "prompt_hash": "a" * 64,
            "source_evidence_hash": common_src_hash,
            "model_load_succeeded": True,
            "gpu_resident": True,
            "inference_occurred": True,
            "responses_attempted": 3,
            "responses_completed": 3,
            "responses_failed": 0,
            "non_preference_cells_preserved": 3,
            "reconciled_by_agent_03": False,
        },
        "discovered_subtopics": [
            {
                "subtopic_id": "Q07_option_choice",
                "question_id": "Q07",
                "proposed_label_en": "Option Choice",
                "definition": "Choice between option alpha and option beta.",
                "decision_object": "option choice",
                "discovered_alternatives": [
                    {"alternative_id": "option_alpha", "label_en": "Alpha"},
                    {"alternative_id": "option_beta", "label_en": "Beta"},
                ],
                "goods_assessment": {"goods_applicability": "NOT_APPLICABLE"},
                "supporting_span_ids": ["SA_1", "SA_2"],
                "supporting_response_ids": ["RESP_P1_Q07", "RESP_P2_Q07"],
                "supporting_participant_ids": ["P1", "P2"],
            },
            {
                "subtopic_id": "Q08_minority_a_only",
                "question_id": "Q08",
                "proposed_label_en": "Centralized Responsibility Minor Facet",
                "definition": "Minority point raised only by Coder A.",
                "decision_object": "centralized responsibility",
                "discovered_alternatives": [
                    {"alternative_id": "central_institute", "label_en": "Central Institute"},
                ],
                "goods_assessment": {"goods_applicability": "NOT_APPLICABLE"},
                "is_minority_position": True,
                "supporting_span_ids": ["SA_3"],
                "supporting_response_ids": ["RESP_P1_Q08"],
                "supporting_participant_ids": ["P1"],
            },
        ],
        "evidence_spans": spans_a,
        "coding_results": [
            {
                "coding_id": "COD_A_1",
                "participant_id": "P1",
                "question_id": "Q07",
                "subtopic_id": "Q07_option_choice",
                "coder_source": "coder_a",
                "missingness_state": MissingnessState.OBSERVED_USABLE.value,
                "epistemic_status": ResponseEpistemicStatus.SUBSTANTIVE.value,
                "alternative_probabilities": {"option_alpha": 1.0, "option_beta": 0.0},
                "semantic_importance": 0.9,
                "coder_confidence": 0.95,
                "coder_agreement": 0.0,
                "coder_agreement_status": "PRE_RECONCILIATION_AGENT_03_PENDING",
                "derived_scalar_score": None,
                "economic_good_class": None,
                "probability_interpretation": "epistemic_uncertainty_over_preference",
                "evidence_span_ids": ["SA_1"],
            },
            {
                "coding_id": "COD_A_2",
                "participant_id": "P2",
                "question_id": "Q07",
                "subtopic_id": "Q07_option_choice",
                "coder_source": "coder_a",
                "missingness_state": MissingnessState.OBSERVED_USABLE.value,
                "epistemic_status": ResponseEpistemicStatus.SUBSTANTIVE.value,
                "alternative_probabilities": {"option_alpha": 0.2, "option_beta": 0.8},
                "semantic_importance": 0.8,
                "coder_confidence": 0.9,
                "coder_agreement": 0.0,
                "coder_agreement_status": "PRE_RECONCILIATION_AGENT_03_PENDING",
                "derived_scalar_score": None,
                "economic_good_class": None,
                "probability_interpretation": "epistemic_uncertainty_over_preference",
                "evidence_span_ids": ["SA_2"],
            },
            {
                "coding_id": "COD_A_3",
                "participant_id": "P1",
                "question_id": "Q08",
                "subtopic_id": "Q08_minority_a_only",
                "coder_source": "coder_a",
                "missingness_state": MissingnessState.OBSERVED_USABLE.value,
                "epistemic_status": ResponseEpistemicStatus.SUBSTANTIVE.value,
                "alternative_probabilities": {"central_institute": 1.0},
                "semantic_importance": 0.7,
                "coder_confidence": 0.85,
                "coder_agreement": 0.0,
                "coder_agreement_status": "PRE_RECONCILIATION_AGENT_03_PENDING",
                "derived_scalar_score": None,
                "economic_good_class": None,
                "probability_interpretation": "epistemic_uncertainty_over_preference",
                "evidence_span_ids": ["SA_3"],
            },
            *_non_pref_crs("coder_a"),
        ],
        "value_assignments": [
            {
                "value_assignment_id": "VA_A_1",
                "value_id": "transparency",
                "original_label": "Transparency",
                "value_definition": "Clear governance rules.",
                "participant_id": "P1",
                "question_id": "Q07",
                "subtopic_id": "Q07_option_choice",
                "evidence_span_ids": ["SA_1"],
                "polarity": None,
                "semantic_importance": 0.8,
                "coder_confidence": 0.9,
            },
            {
                "value_assignment_id": "VA_A_2",
                "value_id": "transparency",
                "original_label": "Transparency",
                "value_definition": "Clear governance rules.",
                "participant_id": "P1",
                "question_id": "Q08",
                "subtopic_id": "Q08_minority_a_only",
                "evidence_span_ids": ["SA_3"],
                "polarity": 0.7,
                "semantic_importance": 0.8,
                "coder_confidence": 0.9,
            },
        ],
    }

    coder_b_payload = {
        "run_id": "run_test_001",
        "coder_id": "coder_b",
        "execution_profile": "production",
        "production_eligible": True,
        "synthetic_or_test_execution": False,
        "execution_mode": "GPU_LIVE",
        "execution_metadata": {
            "execution_profile": "production",
            "production_eligible": True,
            "synthetic_or_test_execution": False,
            "execution_mode": "GPU_LIVE",
            "model_family": "mistral",
            "model_repo": "example/coder-b",
            "model_revision": "rev_b_222",
            "quantization": "W4A16",
            "prompt_hash": "b" * 64,
            "source_evidence_hash": common_src_hash,
            "model_load_succeeded": True,
            "gpu_resident": True,
            "inference_occurred": True,
            "responses_attempted": 3,
            "responses_completed": 3,
            "responses_failed": 0,
            "non_preference_cells_preserved": 3,
            "reconciled_by_agent_03": False,
        },
        "discovered_subtopics": [
            {
                "subtopic_id": "Q07_option_choice",
                "question_id": "Q07",
                "proposed_label_en": "Option Choice",
                "definition": "Choice between option alpha and option beta.",
                "decision_object": "option choice",
                "discovered_alternatives": [
                    {"alternative_id": "option_alpha", "label_en": "Alpha"},
                    {"alternative_id": "option_beta", "label_en": "Beta"},
                ],
                "goods_assessment": {"goods_applicability": "NOT_APPLICABLE"},
                "supporting_span_ids": ["SB_1", "SB_2"],
                "supporting_response_ids": ["RESP_P1_Q07", "RESP_P2_Q07"],
                "supporting_participant_ids": ["P1", "P2"],
            },
        ],
        "evidence_spans": spans_b,
        "coding_results": [
            {
                "coding_id": "COD_B_1",
                "participant_id": "P1",
                "question_id": "Q07",
                "subtopic_id": "Q07_option_choice",
                "coder_source": "coder_b",
                "missingness_state": MissingnessState.OBSERVED_USABLE.value,
                "epistemic_status": ResponseEpistemicStatus.SUBSTANTIVE.value,
                "alternative_probabilities": {"option_alpha": 1.0, "option_beta": 0.0},
                "semantic_importance": 0.9,
                "coder_confidence": 0.9,
                "coder_agreement": 0.0,
                "coder_agreement_status": "PRE_RECONCILIATION_AGENT_03_PENDING",
                "derived_scalar_score": None,
                "economic_good_class": None,
                "probability_interpretation": "epistemic_uncertainty_over_preference",
                "evidence_span_ids": ["SB_1"],
            },
            {
                "coding_id": "COD_B_2",
                "participant_id": "P2",
                "question_id": "Q07",
                "subtopic_id": "Q07_option_choice",
                "coder_source": "coder_b",
                "missingness_state": MissingnessState.OBSERVED_USABLE.value,
                "epistemic_status": ResponseEpistemicStatus.SUBSTANTIVE.value,
                "alternative_probabilities": {"option_alpha": 0.0, "option_beta": 1.0},
                "semantic_importance": 0.85,
                "coder_confidence": 0.85,
                "coder_agreement": 0.0,
                "coder_agreement_status": "PRE_RECONCILIATION_AGENT_03_PENDING",
                "derived_scalar_score": None,
                "economic_good_class": None,
                "probability_interpretation": "epistemic_uncertainty_over_preference",
                "evidence_span_ids": ["SB_2"],
            },
            *_non_pref_crs("coder_b"),
        ],
        "value_assignments": [
            {
                "value_assignment_id": "VA_B_1",
                "value_id": "transparency",
                "original_label": "Transparency",
                "value_definition": "Clear governance rules.",
                "participant_id": "P1",
                "question_id": "Q07",
                "subtopic_id": "Q07_option_choice",
                "evidence_span_ids": ["SB_1"],
                "polarity": None,
                "semantic_importance": 0.85,
                "coder_confidence": 0.85,
            },
        ],
    }

    ca_path = tmp_path / "data" / "processed" / "coder_a_outputs.json"
    cb_path = tmp_path / "data" / "processed" / "coder_b_outputs.json"
    ca_path.write_text(json.dumps(coder_a_payload, indent=2), encoding="utf-8")
    cb_path.write_text(json.dumps(coder_b_payload, indent=2), encoding="utf-8")
    return {
        "tmp_path": tmp_path,
        "coder_a_path": ca_path,
        "coder_b_path": cb_path,
        "coder_a_payload": coder_a_payload,
        "coder_b_payload": coder_b_payload,
    }


def test_rejects_non_production_and_synthetic_inputs(tmp_path: Path) -> None:
    fx = _build_fixture_workspace(tmp_path)
    for bad_profile in ("smoke_tiny", "pilot_subset", "synthetic"):
        bad = json.loads(json.dumps(fx["coder_a_payload"]))
        bad["execution_profile"] = bad_profile
        bad["execution_metadata"]["execution_profile"] = bad_profile
        fx["coder_a_path"].write_text(json.dumps(bad), encoding="utf-8")
        ledger = EvidenceLedger(base_dir=tmp_path, run_id="run_test_001", require_baseline_raw_sha=False)
        with pytest.raises(ProvenanceVerificationError, match="non-production"):
            ledger.load_and_lock_provenance()

    # Reset and test synthetic_or_test_execution=True
    bad_synth = json.loads(json.dumps(fx["coder_a_payload"]))
    bad_synth["synthetic_or_test_execution"] = True
    bad_synth["execution_metadata"]["synthetic_or_test_execution"] = True
    fx["coder_a_path"].write_text(json.dumps(bad_synth), encoding="utf-8")
    ledger = EvidenceLedger(base_dir=tmp_path, run_id="run_test_001", require_baseline_raw_sha=False)
    with pytest.raises(ProvenanceVerificationError, match="synthetic"):
        ledger.load_and_lock_provenance()

    # Test CPU_FALLBACK rejection
    bad_cpu = json.loads(json.dumps(fx["coder_a_payload"]))
    bad_cpu["execution_mode"] = "CPU_FALLBACK"
    bad_cpu["execution_metadata"]["execution_mode"] = "CPU_FALLBACK"
    fx["coder_a_path"].write_text(json.dumps(bad_cpu), encoding="utf-8")
    ledger = EvidenceLedger(base_dir=tmp_path, run_id="run_test_001", require_baseline_raw_sha=False)
    with pytest.raises(ProvenanceVerificationError, match="CPU_FALLBACK"):
        ledger.load_and_lock_provenance()


def test_rejects_same_model_family_prompt_collision_and_source_mismatch(tmp_path: Path) -> None:
    fx = _build_fixture_workspace(tmp_path)

    # Identical model_family rejected
    same_fam = json.loads(json.dumps(fx["coder_b_payload"]))
    same_fam["execution_metadata"]["model_family"] = "deepseek"
    fx["coder_b_path"].write_text(json.dumps(same_fam), encoding="utf-8")
    ledger = EvidenceLedger(base_dir=tmp_path, run_id="run_test_001", require_baseline_raw_sha=False)
    with pytest.raises(ValueError):
        ledger.load_and_lock_provenance()

    # Prompt hash collision rejected
    same_prompt = json.loads(json.dumps(fx["coder_b_payload"]))
    same_prompt["execution_metadata"]["prompt_hash"] = fx["coder_a_payload"]["execution_metadata"]["prompt_hash"]
    fx["coder_b_path"].write_text(json.dumps(same_prompt), encoding="utf-8")
    ledger = EvidenceLedger(base_dir=tmp_path, run_id="run_test_001", require_baseline_raw_sha=False)
    with pytest.raises(ProvenanceVerificationError, match="prompt_hash"):
        ledger.load_and_lock_provenance()

    # Differing common source_evidence_hash rejected
    diff_src = json.loads(json.dumps(fx["coder_b_payload"]))
    diff_src["execution_metadata"]["source_evidence_hash"] = "1" * 64
    fx["coder_b_path"].write_text(json.dumps(diff_src), encoding="utf-8")
    ledger = EvidenceLedger(base_dir=tmp_path, run_id="run_test_001", require_baseline_raw_sha=False)
    with pytest.raises(ProvenanceVerificationError, match="source_evidence_hash"):
        ledger.load_and_lock_provenance()


def test_span_verification_rejects_offsets_sha_and_orphan_refs(tmp_path: Path) -> None:
    fx = _build_fixture_workspace(tmp_path)

    # 1. Bad char offset
    bad_off = json.loads(json.dumps(fx["coder_a_payload"]))
    bad_off["evidence_spans"][0]["char_end"] -= 2
    fx["coder_a_path"].write_text(json.dumps(bad_off), encoding="utf-8")
    ledger = EvidenceLedger(base_dir=tmp_path, run_id="run_test_001", require_baseline_raw_sha=False)
    with pytest.raises(EvidenceIntegrityError, match="offsets=1"):
        ledger.verify_spans_and_missingness()

    # 2. Bad response sha256
    bad_sha = json.loads(json.dumps(fx["coder_a_payload"]))
    bad_sha["evidence_spans"][0]["raw_response_sha256"] = "0" * 64
    fx["coder_a_path"].write_text(json.dumps(bad_sha), encoding="utf-8")
    ledger = EvidenceLedger(base_dir=tmp_path, run_id="run_test_001", require_baseline_raw_sha=False)
    with pytest.raises(EvidenceIntegrityError, match="sha=1"):
        ledger.verify_spans_and_missingness()

    # 3. Orphan span ID reference in coding_results
    orphan = json.loads(json.dumps(fx["coder_a_payload"]))
    orphan["coding_results"][0]["evidence_span_ids"] = ["SPAN_DOES_NOT_EXIST"]
    fx["coder_a_path"].write_text(json.dumps(orphan), encoding="utf-8")
    ledger = EvidenceLedger(base_dir=tmp_path, run_id="run_test_001", require_baseline_raw_sha=False)
    with pytest.raises(EvidenceIntegrityError, match="orphans=1"):
        ledger.verify_spans_and_missingness()


def test_non_preference_cell_violation_detected(tmp_path: Path) -> None:
    fx = _build_fixture_workspace(tmp_path)
    tampered = json.loads(json.dumps(fx["coder_a_payload"]))
    # Fabricate probabilities inside a non-preference record
    for cr in tampered["coding_results"]:
        if cr["missingness_state"] != MissingnessState.OBSERVED_USABLE.value:
            cr["alternative_probabilities"] = {"fabricated_option": 1.0}
            break
    fx["coder_a_path"].write_text(json.dumps(tampered), encoding="utf-8")
    ledger = EvidenceLedger(base_dir=tmp_path, run_id="run_test_001", require_baseline_raw_sha=False)
    with pytest.raises(EvidenceIntegrityError, match="non_pref="):
        ledger.verify_spans_and_missingness()


def test_reconciliation_no_silent_averaging_and_disagreement_stop(tmp_path: Path) -> None:
    fx = _build_fixture_workspace(tmp_path)

    # Also add a Phase-2 split facet in Coder B coding_results without a Phase-1 entry
    cb_mod = json.loads(json.dumps(fx["coder_b_payload"]))
    cb_mod["coding_results"].append(
        {
            "coding_id": "COD_B_SPLIT",
            "participant_id": "P2",
            "question_id": "Q07",
            "subtopic_id": "Q07_option_choice_2",
            "coder_source": "coder_b",
            "missingness_state": MissingnessState.OBSERVED_USABLE.value,
            "epistemic_status": ResponseEpistemicStatus.SUBSTANTIVE.value,
            "alternative_probabilities": {"beta_variant": 1.0},
            "semantic_importance": 0.6,
            "coder_confidence": 0.7,
            "coder_agreement": 0.0,
            "coder_agreement_status": "PRE_RECONCILIATION_AGENT_03_PENDING",
            "derived_scalar_score": None,
            "economic_good_class": None,
            "probability_interpretation": "explicit_mixed_preference",
            "evidence_span_ids": ["SB_2"],
        }
    )
    fx["coder_b_path"].write_text(json.dumps(cb_mod), encoding="utf-8")

    ledger = EvidenceLedger(base_dir=tmp_path, run_id="run_test_001", require_baseline_raw_sha=False)
    reconciler = EvidenceReconciler(ledger=ledger)
    result = reconciler.run_reconciliation(write_outputs=True)

    qa = result["qa_report"]
    assert qa["all_reconciliation_invariants_passed"] is True
    assert qa["agent_04_release"] == "PENDING_INTEGRATION_AND_GOVERNANCE_GATE"
    assert qa["qa_checks"]["adr0008_preference_cells_validated"] is True
    assert qa["qa_checks"]["forbidden_reconciliation_methods_zero"] is True
    assert qa["qa_checks"]["no_resolved_point_for_uncertain_cells"] is True
    assert qa["counts"]["phase1_discovered_subtopics_total"] == 3
    assert qa["counts"]["phase2_split_subtopics_total"] == 1
    assert qa["counts"]["unresolved_by_adr0008_class"]["DATA_CONTRACT_VIOLATION"] == 0

    rec_ev = json.loads((tmp_path / "data" / "processed" / "reconciliation" / "reconciled_evidence.json").read_text())
    recs = rec_ev["preference_reconciliation_records"]

    # P1 Q07: exact match -> AGREEMENT_EXACT / NONE_CONSENSUS with preserved point distribution
    p1_q07 = [r for r in recs if r["participant_id"] == "P1" and r["question_id"] == "Q07"][0]
    assert p1_q07["reconciliation_status"] == "AGREEMENT_EXACT"
    assert p1_q07["uncertainty_class"] == "NONE_CONSENSUS"
    assert p1_q07["crosswalk_status"] == "EXACT_KEY_MATCH"
    assert p1_q07["resolved_point_distribution"] == {"option_alpha": 1.0, "option_beta": 0.0}
    assert p1_q07["reconciled_alternative_probabilities"] == {"option_alpha": 1.0, "option_beta": 0.0}
    assert p1_q07["preference_uncertainty_set"]["representation_type"] == "SINGLETON"

    # P2 Q07 matched pair: differing distributions (0.2/0.8 vs 0.0/1.0) -> ADR-0008 DISCRETE_CODER_SET (NO averaging!)
    p2_q07 = [
        r for r in recs
        if r["participant_id"] == "P2" and r["question_id"] == "Q07" and r["coder_b_subtopic_id"] == "Q07_option_choice"
    ][0]
    assert p2_q07["reconciliation_status"] == "RESOLVED_WITH_UNCERTAINTY_SET"
    assert p2_q07["reconciliation_method"] == "UNCERTAINTY_SET_PRESERVED"
    assert p2_q07["uncertainty_class"] == "DUAL_CODER_DISTRIBUTION_SET"
    assert p2_q07["agreement_status"] == "DISTRIBUTION_DISAGREEMENT"
    assert p2_q07["resolved_point_distribution"] is None
    assert p2_q07["reconciled_alternative_probabilities"] is None
    assert p2_q07["coder_a_distribution"] == {"option_alpha": 0.2, "option_beta": 0.8}
    assert p2_q07["coder_b_distribution"] == {"option_alpha": 0.0, "option_beta": 1.0}
    assert p2_q07["preference_uncertainty_set"]["representation_type"] == "DISCRETE_CODER_SET"
    assert len(p2_q07["preference_uncertainty_set"]["discrete_scenarios"]) == 2
    assert p2_q07["total_variation_distance"] == pytest.approx(0.2, abs=1e-6)

    # Minority Coder A subtopic & Phase-2 split subtopic retained as SINGLE_CODER_PARTIAL_ID without 0.0-fill
    p1_q08 = [r for r in recs if r["participant_id"] == "P1" and r["question_id"] == "Q08"][0]
    assert p1_q08["cell_observation_category"] == "SINGLE_CODER_SUBTOPIC_ONLY"
    assert p1_q08["reconciliation_status"] == "RESOLVED_WITH_UNCERTAINTY_SET"
    assert p1_q08["reconciliation_method"] == "SINGLE_CODER_PARTIAL_ID"
    assert p1_q08["uncertainty_class"] == "SINGLE_CODER_PARTIAL_ID_GRANULARITY"
    assert p1_q08["resolved_point_distribution"] is None
    assert p1_q08["coder_b_distribution"] is None
    assert p1_q08["preference_uncertainty_set"]["single_coder_active_side"] == "coder_a"
    assert p1_q08["preference_uncertainty_set"]["non_coding_coder_state"] == "EPISTEMICALLY_UNOBSERVED"

    p2_split = [r for r in recs if r.get("coder_b_subtopic_id") == "Q07_option_choice_2"][0]
    assert p2_split["resolved_point_distribution"] is None
    assert p2_split["coder_a_distribution"] is None
    assert p2_split["preference_uncertainty_set"]["double_count_guard_applied"] is True

    # Agreement stats keep 4 modules separate, suppress omnibus score, and do not report 0.0 placeholder
    agree = result["agreement_stats"]
    assert agree["omnibus_score_suppressed"] is True
    assert agree["goods_classification_agreement"]["forced_classifications_count"] == 0
    assert agree["preference_and_alternative_agreement"]["mean_one_minus_tvd"] == pytest.approx(0.9, abs=1e-4)

    # Unresolved cases registry has 5-class ADR-0008 taxonomy counts
    unres = json.loads((tmp_path / "data" / "processed" / "reconciliation" / "unresolved_cases_registry.json").read_text())
    assert set(unres["adr0008_resolution_class_counts"].keys()) == {
        "RESOLVED_AS_UNCERTAINTY",
        "PARTIALLY_IDENTIFIED",
        "CROSSWALK_UNRESOLVED",
        "SEMANTICALLY_UNRESOLVED",
        "DATA_CONTRACT_VIOLATION",
    }

    # Alternative crosswalk summary written alongside reconciliation artifacts
    cw_summary = json.loads(
        (tmp_path / "data" / "processed" / "reconciliation" / "alternative_crosswalk_summary.json").read_text()
    )
    assert "EXACT_KEY_MATCH" in cw_summary["dual_observed_crosswalk_status_counts"]

    # Consolidated values span cross-question Q07+Q08, preserve null polarity, prohibit Pareto pruning
    vals = json.loads((tmp_path / "data" / "processed" / "reconciliation" / "reconciled_values.json").read_text())
    assert vals["pareto_pruning_prohibited"] is True
    assert len(vals["reconciled_values"]) == 1
    assert vals["reconciled_values"][0]["supporting_question_ids"] == ["Q07", "Q08"]
    assert vals["reconciled_values"][0]["polarity_null_count"] == 2
    assert vals["reconciled_values"][0]["polarity_non_null_values"] == [0.7]

    # Candidate options allow constraint-only evaluation with zero cluster/value pruning
    cand_payload = json.loads((tmp_path / "data" / "processed" / "candidate_options.json").read_text())
    assert cand_payload["pruning_policy"] == "CONSTRAINT_ONLY_NO_CLUSTER_OR_VALUE_PRUNING"
    assert all(c["pruned_by_clusters_or_values"] is False for c in cand_payload["candidates"])


def test_antonym_guard_and_scoped_key_crosswalk() -> None:
    # Vague vs clear must NEVER map as semantic equivalents
    res_opp = align_alternative_vocabularies({"vague_denominations": 1.0}, {"clear_terminology": 1.0})
    assert res_opp.comparable is False
    assert res_opp.crosswalk_status == "NO_VALID_CROSSWALK"
    assert res_opp.mapping_type == "NO_VALID_CROSSWALK"

    # Scenario prefix alignment succeeds cleanly 1-to-1
    res_scen = align_alternative_vocabularies(
        {"scenario_1_centralized": 0.5, "scenario_2_flat": 0.5},
        {"scenario_1_ri": 0.5, "scenario_2_fixed": 0.5},
        question_id="Q10",
        canonical_subtopic_id="Q10_core",
    )
    assert res_scen.comparable is True
    assert res_scen.crosswalk_status == "SCENARIO_PREFIX_MATCH"
    assert res_scen.aligned_keys == ["scenario_1", "scenario_2"]

    # Explicit scoped crosswalk rules support SEMANTIC_KEY_MATCH, PARTIAL_CROSSWALK, NO_VALID_CROSSWALK, and reject cross-scope misuse
    rule = {
        "crosswalk_rule_id": "CW_TEST_SCOPE",
        "question_id": "Q07",
        "canonical_subtopic_id": "Q07_sub",
        "preferred_matched_status": "SEMANTIC_KEY_MATCH",
        "coder_a_to_canonical": {"a_key": "canon_1", "a_other": "canon_2"},
        "coder_b_to_canonical": {"b_key": "canon_1"},
        "provenance_rationale": "Test scoped mapping.",
    }
    res_partial = align_alternative_vocabularies(
        {"a_key": 0.7, "a_unmapped": 0.3},
        {"b_key": 1.0},
        question_id="Q07",
        canonical_subtopic_id="Q07_sub",
        crosswalk_rule=rule,
    )
    assert res_partial.comparable is False
    assert res_partial.crosswalk_status == "PARTIAL_CROSSWALK"
    assert res_partial.unmapped_keys_a == ["a_unmapped"]
    assert res_partial.unmapped_mass_a == pytest.approx(0.3, abs=1e-6)

    with pytest.raises(ValueError, match="scope mismatch"):
        align_alternative_vocabularies(
            {"a_key": 1.0},
            {"b_key": 1.0},
            question_id="Q08",
            canonical_subtopic_id="Q07_sub",
            crosswalk_rule=rule,
        )


def test_issue_005_interpretation_divergence_and_crosswalk_uncertainty_sets(tmp_path: Path) -> None:
    """Verify ISSUE-005 Rule 4A/4C interpretation divergence + PARTIAL_CROSSWALK / NO_VALID_CROSSWALK."""
    fx = _build_fixture_workspace(tmp_path)
    (tmp_path / "runs" / "run_test_001").mkdir(parents=True)

    # P1 Q07: numerically identical [1.0, 0.0], differing probability_interpretation -> INTERPRETATION_DIVERGENCE
    ca_mod = json.loads(json.dumps(fx["coder_a_payload"]))
    cb_mod = json.loads(json.dumps(fx["coder_b_payload"]))
    cb_mod["coding_results"][0]["probability_interpretation"] = "explicit_mixed_preference"

    # P2 Q07: test PARTIAL_CROSSWALK via scoped rule where Coder B introduces an unmapped residual key
    cb_mod["coding_results"][1]["alternative_probabilities"] = {"opt_b_shared": 0.6, "extra_b_only": 0.4}
    ca_mod["coding_results"][1]["alternative_probabilities"] = {"opt_a_shared": 0.8, "option_alpha": 0.2}

    cw_cfg = {
        "schema_version": "1.0.0",
        "run_id": "run_test_001",
        "rules": [
            {
                "crosswalk_rule_id": "CW_Q07_TEST",
                "question_id": "Q07",
                "canonical_subtopic_id": "Q07_option_choice",
                "preferred_matched_status": "EXACT_KEY_MATCH",
                "coder_a_to_canonical": {"option_alpha": "option_alpha", "option_beta": "option_beta", "opt_a_shared": "shared_opt"},
                "coder_b_to_canonical": {"option_alpha": "option_alpha", "option_beta": "option_beta", "opt_b_shared": "shared_opt"},
                "provenance_rationale": "Test scoped rule leaving extra_b_only unmapped.",
            }
        ],
    }
    (tmp_path / "runs" / "run_test_001" / "alternative_crosswalk.json").write_text(
        json.dumps(cw_cfg, indent=2), encoding="utf-8"
    )
    fx["coder_a_path"].write_text(json.dumps(ca_mod), encoding="utf-8")
    fx["coder_b_path"].write_text(json.dumps(cb_mod), encoding="utf-8")

    ledger = EvidenceLedger(base_dir=tmp_path, run_id="run_test_001", require_baseline_raw_sha=False)
    res = EvidenceReconciler(ledger=ledger).run_reconciliation(write_outputs=True)
    assert res["qa_report"]["all_reconciliation_invariants_passed"] is True

    rec_ev = json.loads((tmp_path / "data" / "processed" / "reconciliation" / "reconciled_evidence.json").read_text())
    recs = rec_ev["preference_reconciliation_records"]

    p1 = [r for r in recs if r["participant_id"] == "P1" and r["question_id"] == "Q07"][0]
    assert p1["uncertainty_class"] == "INTERPRETATION_DIVERGENCE"
    assert p1["agreement_status"] == "DISTRIBUTION_AGREEMENT_INTERP_FLAGGED"
    assert p1["reconciliation_status"] == "AGREEMENT_DISTRIBUTION_ONLY_INTERPRETATION_FLAGGED"
    assert p1["resolved_point_distribution"] is None
    assert set(p1["preference_uncertainty_set"]["interpretation_variants"]) == {
        "epistemic_uncertainty_over_preference",
        "explicit_mixed_preference",
    }

    p2 = [r for r in recs if r["participant_id"] == "P2" and r["question_id"] == "Q07"][0]
    assert p2["crosswalk_status"] == "PARTIAL_CROSSWALK"
    assert p2["uncertainty_class"] == "CROSSWALK_PARTIAL_OR_UNALIGNED"
    assert p2["reconciliation_status"] == "UNRESOLVED_CROSSWALK"
    assert p2["resolved_point_distribution"] is None
    assert p2["preference_uncertainty_set"]["representation_type"] == "PARTIAL_CROSSWALK_SET"


def test_production_run_20261111_002_integration() -> None:
    """Verify full Agent 03 ADR-0008 invariants and Condition 7 when run_20261111_002 outputs exist."""
    from src.contracts import FORBIDDEN_RECONCILIATION_METHODS
    from src.pipeline.orchestrator import evaluate_pipeline_state

    repo_root = Path(__file__).resolve().parents[1]
    ca_path = repo_root / "data" / "processed" / "coder_a_outputs.json"
    cb_path = repo_root / "data" / "processed" / "coder_b_outputs.json"
    qa_path = repo_root / "data" / "processed" / "reconciliation" / "reconciliation_qa_report.json"
    if not (ca_path.is_file() and cb_path.is_file() and qa_path.is_file()):
        pytest.skip("Production Coder A/B runtime artifacts not staged locally.")

    reconciler = EvidenceReconciler(base_dir=repo_root, run_id="run_20261111_002")
    summary = reconciler.run_reconciliation(write_outputs=False)

    lock = summary["provenance_lock"]
    assert lock["validation_status"] == "LOCKED_VERIFIED"
    assert lock["common_source_evidence_hash"] == "0b814c3b6f6a88ec8e5d895a025cb146ed2e73e08f814ace145c0237c17c9753"
    assert lock["recomputed_source_evidence_hash"] == lock["common_source_evidence_hash"]
    assert lock["coder_a"]["prompt_hash"] == (
        "4d1279f0" "46aa4460" "707cb81b" "4e291cce" "30179cc0" "60659fcd" "b4f796e2" "24864377"
    )
    assert lock["coder_b"]["prompt_hash"] == "d880fc917663268813188f833ad0bd7b0a2a3fa26a3096df5e36959965e3083b"
    assert lock["coder_a"]["responses_attempted"] == 136
    assert lock["coder_a"]["responses_completed"] == 136
    assert lock["coder_a"]["responses_failed"] == 0
    assert lock["coder_b"]["responses_attempted"] == 136
    assert lock["coder_b"]["responses_completed"] == 136
    assert lock["coder_b"]["responses_failed"] == 0
    assert lock["non_preference_response_cells"] == 18

    qa = summary["qa_report"]
    assert qa["all_reconciliation_invariants_passed"] is True
    assert qa["qa_checks"]["adr0008_preference_cells_validated"] is True
    assert qa["qa_checks"]["forbidden_reconciliation_methods_zero"] is True
    assert qa["qa_checks"]["no_resolved_point_for_uncertain_cells"] is True
    assert qa["counts"]["primary_question_count"] == 13
    assert qa["counts"]["non_preference_cells_preserved"] == 18
    assert qa["counts"]["phase1_discovered_subtopics_total"] == 99
    assert qa["counts"]["phase2_split_subtopics_total"] == 2
    assert qa["counts"]["unresolved_by_adr0008_class"]["DATA_CONTRACT_VIOLATION"] == 0
    assert qa["agent_04_release"] == "PENDING_INTEGRATION_AND_GOVERNANCE_GATE"

    rec_text = (repo_root / "data" / "processed" / "reconciliation" / "reconciled_evidence.json").read_text(encoding="utf-8")
    for forb in FORBIDDEN_RECONCILIATION_METHODS:
        assert forb not in rec_text

    report = evaluate_pipeline_state(base_dir=repo_root, run_id="run_20261111_002", write_log=False)
    assert report.agent_04_release_checklist["6_agent_03_outputs_exist"] is True
    assert report.agent_04_release_checklist["7_agent_03_crosswalk_and_uncertainty_sets_valid"] is True

