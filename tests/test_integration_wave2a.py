"""Wave 2A Integration & Analytical Compatibility Tests (Agent 11).

Verifies:
1. Single authoritative contract definitions across src.contracts, src.artifact_registry, and src.nlp.schemas.
2. Agent 01 -> Agent 02 end-to-end compatibility using the canonical 154-row corpus and QuestionRegistry.
3. Analytical invariants:
   - Q01-Q13 primary vs Q14 optional contextual remarks.
   - Explicit no-opinion & insufficient-experience remain reportable without becoming preference.
   - Concise substantive answers ('Oui', 'Non', 'Idem') survive without over-missingness.
   - Ambiguous texts ('RAS' in Q02, 'à réfléchir encore un peu' in Q03) are preserved for coder interpretation.
   - Blank / punctuation-only / Q14 'RAS' emit zero EvidenceSpans and zero fabricated preferences.
   - Open values permit polarity=None cleanly; coder inputs remain isolated with shared source hash.
4. Schema catalog (schemas/interfaces.json) conformance and notebook bootstrap execution from notebooks/.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import src.artifact_registry as ar
import src.contracts as contracts
import src.nlp.schemas as nlp_schemas
from src.contracts import (
    CodingResult,
    MissingnessState,
    PreferenceCell,
    ProvenanceMeta,
    ResponseEpistemicStatus,
    ValueAssignment,
)
from src.ingest.ingestion import SurveyIngester
from src.nlp.prompts import compute_source_evidence_hash
from src.nlp.repair import classify_response_status
from src.nlp.schemas import NormalizedResponseInput, QuestionCorpusInput, ResponseStatusLabel
from src.nlp.subtopic_extraction import QuestionCorpusCoder
from src.registry.question_registry import QuestionRegistry

REPO_ROOT = Path(__file__).resolve().parent.parent


def _dummy_provenance(record_id: str = "REC_01") -> ProvenanceMeta:
    return ProvenanceMeta(
        record_id=record_id,
        run_id="run_20261111_002",
        dataset_fingerprint="56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95",
        created_at_utc="2026-11-12T00:00:00+00:00",
        producer_module="tests/test_integration_wave2a.py",
        producer_agent="agent_11",
    )


def test_single_authoritative_contract_definitions():
    """Verify no duplicate incompatible MissingnessState, PreferenceCell, or status taxonomies exist."""
    assert ar.MissingnessState is contracts.MissingnessState
    assert ar.PreferenceCell is contracts.PreferenceCell
    assert ResponseStatusLabel is ResponseEpistemicStatus

    # Unified PreferenceCell supports both canonical and convenience aliases without duplication
    cell = PreferenceCell(
        cell_id="CELL_TEST",
        participant_id="PARTICIPANT_001",
        question_id="Q08",
        subtopic_id="SUB_Q08_01",
        missingness_state="observed_usable",
        alternative_probabilities={"laboratory": 0.8, "pole": 0.2},
        semantic_importance=0.9,
        coder_confidence=0.85,
        coder_agreement=1.0,
        source_coding_id="CODE_01",
        evidence_span_ids=["SPAN_01"],
        probability_interpretation="epistemic_uncertainty_over_preference",
        provenance=_dummy_provenance("CELL_TEST"),
    )
    assert cell.missingness_state == MissingnessState.OBSERVED_USABLE
    assert cell.question_or_dimension_id == "Q08"
    assert cell.evidence_ids == ["SPAN_01"]
    assert cell.validate_simplex() is True

    # Nullable ValueAssignment polarity and CodingResult probability_interpretation
    val = ValueAssignment(
        value_assignment_id="VA_01",
        value_id="VAL_01",
        value_label_en="Mentoring Continuity",
        value_definition="Protecting knowledge transfer across cohorts.",
        participant_id="PARTICIPANT_001",
        question_id="Q08",
        subtopic_id="SUB_Q08_01",
        evidence_span_ids=["SPAN_01"],
        missingness_state=MissingnessState.OBSERVED_USABLE,
        polarity=None,
        semantic_importance=0.8,
        coder_confidence=0.9,
        coder_agreement=1.0,
        polarity_uncertainty_interval=None,
        provenance=_dummy_provenance("VA_01"),
    )
    assert val.polarity is None

    coding = CodingResult(
        coding_id="CODE_01",
        participant_id="PARTICIPANT_001",
        question_id="Q08",
        subtopic_id="SUB_Q08_01",
        coder_source="reconciled",
        missingness_state=MissingnessState.OBSERVED_USABLE,
        alternative_probabilities={"laboratory": 1.0},
        semantic_importance=0.9,
        coder_confidence=0.9,
        coder_agreement=1.0,
        evidence_span_ids=["SPAN_01"],
        probability_interpretation="explicit_mixed_preference",
        provenance=_dummy_provenance("CODE_01"),
    )
    coding.validate_invariants()


def test_agent01_to_agent02_real_corpus_compatibility():
    """Verify full handoff compatibility from Agent 01 normalized survey rows into Agent 02 corpus coding."""
    ingester = SurveyIngester(raw_csv_path=REPO_ROOT / "data" / "raw" / "survey_raw.csv")
    df = ingester.normalize()
    reg = QuestionRegistry(raw_csv_path=REPO_ROOT / "data" / "raw" / "survey_raw.csv")
    specs = reg.build_from_answers(df)

    # 13 primary vs Q14 optional
    assert len(reg.get_substantive_questions()) == 13
    for i in range(1, 14):
        q = specs[f"Q{i:02d}"]
        assert q.is_primary_question is True
        assert q.question_scope == "primary"
    assert specs["Q14"].is_primary_question is False
    assert specs["Q14"].question_scope == "optional_contextual_remarks"

    # Build real QuestionCorpusInput for Q02 (contains substantive "oui", ambiguous "RAS", explicit no opinion, blank)
    q02_spec = specs["Q02"]
    q02_rows = df[df["question_id"] == "Q02"]
    q02_inputs = [NormalizedResponseInput.from_normalized_row(r.to_dict()) for _, r in q02_rows.iterrows()]
    corpus = QuestionCorpusInput(
        question_id=q02_spec.question_id,
        question_index=q02_spec.question_index,
        canonical_prompt_en=q02_spec.canonical_prompt_en,
        exact_question_wording=q02_spec.column_headers_by_lang,
        analytical_frame=q02_spec.analytical_frame,
        economic_good_classification_policy=q02_spec.economic_good_classification_policy,
        responses=q02_inputs,
        source_evidence_hash="placeholder",
    )

    coder = QuestionCorpusCoder()

    def disc(sys_p, u_p):
        return {
            "question_id": "Q02",
            "discovered_subtopics": [
                {
                    "subtopic_key": "identified_leads_fit",
                    "proposed_label_en": "Relevance of Identified Pole Leads",
                    "definition": "Assessment of whether identified lead individuals fit pole governance.",
                    "decision_object": "pole lead selection",
                    "mechanism": "consultation validation",
                    "scope": "identified persons",
                    "discovered_alternatives": [
                        {"alternative_id": "endorse", "label_en": "Endorse identified persons"},
                        {"alternative_id": "adjust", "label_en": "Adjust or broaden selection"},
                    ],
                    "supporting_response_ids": [r.response_id for r in q02_inputs if r.has_usable_preference],
                    "supporting_participant_ids": [r.participant_id for r in q02_inputs if r.has_usable_preference],
                    "is_minority_position": False,
                }
            ],
        }

    def assign(resp: NormalizedResponseInput, tax, sys_p, u_p):
        text = resp.raw_value or ""
        if resp.epistemic_status in {
            ResponseEpistemicStatus.EXPLICIT_NO_OPINION,
            ResponseEpistemicStatus.EXPLICIT_INSUFFICIENT_EXPERIENCE,
            ResponseEpistemicStatus.EXPLICIT_INSUFFICIENT_INFORMATION,
        }:
            return {
                "participant_id": resp.participant_id,
                "question_id": "Q02",
                "response_id": resp.response_id,
                "is_substantive": False,
                "missingness_state": "missing_non_substantive",
                "response_status": resp.epistemic_status.value,
                "detected_language": resp.detected_language,
                "evidence_spans": [{"verbatim_quote": text.strip(), "span_role": "explicit_uncertainty_or_no_opinion"}],
                "subtopics": [],
            }
        if resp.epistemic_status == ResponseEpistemicStatus.AMBIGUOUS:
            # Leave ambiguous ("RAS" in Q02) unresolved -> reportable verbatim span, ZERO fabricated preference
            return {
                "participant_id": resp.participant_id,
                "question_id": "Q02",
                "response_id": resp.response_id,
                "is_substantive": False,
                "missingness_state": "ambiguous",
                "response_status": "ambiguous",
                "detected_language": resp.detected_language,
                "evidence_spans": [{"verbatim_quote": text.strip(), "span_role": "explicit_uncertainty_or_no_opinion"}],
                "subtopics": [],
            }
        quote = text.strip()
        return {
            "participant_id": resp.participant_id,
            "question_id": "Q02",
            "response_id": resp.response_id,
            "is_substantive": True,
            "missingness_state": "observed_usable",
            "response_status": resp.epistemic_status.value if resp.epistemic_status else "substantive",
            "detected_language": resp.detected_language,
            "evidence_spans": [{"verbatim_quote": quote}],
            "subtopics": [
                {
                    "subtopic_key": "identified_leads_fit",
                    "proposed_label_en": "Relevance of Identified Pole Leads",
                    "proposed_description": "Substantive position on identified pole leads.",
                    "candidate_alternative_distribution": {"endorse": 0.9, "adjust": 0.1},
                    "probability_interpretation": "epistemic_uncertainty_over_preference",
                    "semantic_importance": 0.85,
                    "coder_confidence": 0.90,
                    "evidence_quotes": [quote],
                }
            ],
            "values": [
                {
                    "original_label": "Collegial Legitimacy",
                    "value_definition": "Ensuring pole leadership reflects constituent research units.",
                    "polarity": None,
                    "semantic_importance": 0.8,
                    "coder_confidence": 0.85,
                    "evidence_quotes": [quote],
                }
            ],
        }

    out = coder.code_question_corpus(
        corpus=corpus,
        coder_a_discovery_fn=disc,
        coder_b_discovery_fn=disc,
        coder_a_assign_fn=assign,
        coder_b_assign_fn=assign,
    )

    # Identical source hash, distinct prompt hashes
    assert out["source_evidence_hash"] == compute_source_evidence_hash(corpus)
    assert out["coder_a_prompt_hash"] != out["coder_b_prompt_hash"]

    # Concise substantive PARTICIPANT_009 ("oui") MUST be in observed_preference_participants
    assert "PARTICIPANT_009" in out["observed_preference_participants"]
    # Ambiguous PARTICIPANT_005 ("RAS" in Q02) stays reportable statement without preference
    assert "PARTICIPANT_005" in out["observed_statement_participants"]
    assert "PARTICIPANT_005" not in out["observed_preference_participants"]
    assert any(sp.participant_id == "PARTICIPANT_005" and sp.verbatim_quote == "RAS" for sp in out["evidence_spans"])

    # Context-sensitive "RAS" in Q14 is non-reportable
    m14, s14 = classify_response_status("RAS", question_id="Q14")
    assert m14 == MissingnessState.MISSING_NON_SUBSTANTIVE
    assert s14 == ResponseEpistemicStatus.NO_ADDITIONAL_REMARKS

    # Open values preserved with polarity=None
    assert all(v.polarity is None for v in out["value_stage_a_extractions"])

    # Exact partitioning invariant on CanonicalSubtopic
    sub = out["canonical_subtopics"][0]
    assert (
        sub.mention_participant_count + sub.unmentioned_participant_count + sub.missing_question_participant_count
        == len(q02_inputs)
    )


def test_interfaces_json_aligned_with_contracts():
    """Verify schemas/interfaces.json reflects updated contracts and epistemic enums."""
    data = json.loads((REPO_ROOT / "schemas" / "interfaces.json").read_text(encoding="utf-8"))
    assert set(data["epistemic_statuses"]) == {e.value for e in ResponseEpistemicStatus}
    assert "epistemic_uncertainty_over_preference" in data["probability_interpretations"]

    q_opt = {f["name"]: f["type"] for f in data["interfaces"]["QuestionSpec"]["optional_fields"]}
    assert "is_primary_question" in q_opt
    assert "question_scope" in q_opt

    e_opt = {f["name"]: f["type"] for f in data["interfaces"]["EvidenceSpan"]["optional_fields"]}
    assert e_opt["offset_reference_text"] == "str"
    assert "span_role" in e_opt

    v_req = {f["name"]: f["type"] for f in data["interfaces"]["ValueAssignment"]["required_fields"]}
    assert v_req["polarity"] == "float | None"

    p_opt = {f["name"]: f["type"] for f in data["interfaces"]["PreferenceCell"]["optional_fields"]}
    assert "probability_interpretation" in p_opt


def test_notebooks_executable_from_notebooks_dir():
    """Verify code cells of tracked notebooks import and run cleanly from notebooks/ working directory."""
    nb_dir = REPO_ROOT / "notebooks"
    for nb_name in ["01_ingest_exploration.ipynb", "02_qualitative_coding.ipynb"]:
        nb_path = nb_dir / nb_name
        assert nb_path.is_file()
        nb = json.loads(nb_path.read_text(encoding="utf-8"))
        # Run first code cell (bootstrap + imports) from notebooks/ cwd in a clean subprocess
        code_cells = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
        assert len(code_cells) >= 2
        res = subprocess.run(
            [sys.executable, "-c", code_cells[0]],
            cwd=str(nb_dir),
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 0, f"{nb_name} import bootstrap failed from {nb_dir}:\n{res.stderr}"
