"""Multilingual test fixtures and declared QuestionSpec samples for French, German, and English.

Owned by: Agent 02 — Qualitative Coding
Schema Version: 1.0.0 / v1.1.0
Active Run: run_20261111_002

Provides realistic survey responses in French (fr), German (de), and English (en) across
diverse analytical frames, epistemic response statuses (no opinion, insufficient experience/info,
mixed uncertainty + substantive), unseen values, and truly blank/placeholder missingness.
"""

from __future__ import annotations

from typing import Any, Dict
from src.contracts import AnalyticalFrameType, MissingnessState, ProvenanceMeta, QuestionSpec, SCHEMA_VERSION


def get_sample_question_specs() -> Dict[str, QuestionSpec]:
    """Return QuestionSpec definitions for substantive questions spanning all 4 analytical frames."""
    dummy_prov = ProvenanceMeta(
        record_id="PROV_SPEC_SAMPLE",
        run_id="run_20261111_002",
        dataset_fingerprint="56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95",
        created_at_utc="2026-11-12T00:00:00Z",
        producer_module="src/nlp/fixtures.py",
        producer_agent="agent_02",
        schema_version=SCHEMA_VERSION,
    )

    specs = {
        "Q01": QuestionSpec(
            question_id="Q01",
            question_index=1,
            column_headers_by_lang={"fr": "1. Pertinence_de_ces_poles"},
            canonical_prompt_en="Relevance of the thematic research poles",
            analytical_frame=AnalyticalFrameType.PERCEPTION_AND_DIAGNOSTIC,
            economic_good_classification_policy="DISABLED",
            alternative_classification_scheme="perception_diagnostic_valence",
            observed_response_count=10,
            missing_response_count=1,
            missing_participant_ids=["PARTICIPANT_011"],
            provenance=dummy_prov,
        ),
        "Q04": QuestionSpec(
            question_id="Q04",
            question_index=4,
            column_headers_by_lang={"fr": "4. Faut-il_un_fonctionnement_unifie_entre_l"},
            canonical_prompt_en="Should operations be unified across poles and institutes?",
            analytical_frame=AnalyticalFrameType.INSTITUTIONAL_DESIGN_DECISION,
            economic_good_classification_policy="CONDITIONAL",
            alternative_classification_scheme="institutional_operational_postures",
            observed_response_count=9,
            missing_response_count=2,
            missing_participant_ids=["PARTICIPANT_005", "PARTICIPANT_011"],
            provenance=dummy_prov,
        ),
        "Q08": QuestionSpec(
            question_id="Q08",
            question_index=8,
            column_headers_by_lang={"fr": "8. A_quel_niveau_la_gestion_RH_notamment_le"},
            canonical_prompt_en="At what level should HR management and recruitment take place?",
            analytical_frame=AnalyticalFrameType.GOVERNANCE_GOODS_ALLOCATION,
            economic_good_classification_policy="ENABLED",
            alternative_classification_scheme="hr_decision_rights_allocation",
            observed_response_count=10,
            missing_response_count=1,
            missing_participant_ids=["PARTICIPANT_009"],
            provenance=dummy_prov,
        ),
        "Q11": QuestionSpec(
            question_id="Q11",
            question_index=11,
            column_headers_by_lang={"fr": "11. Comment_les_overheads_doivent-ils_etre_g"},
            canonical_prompt_en="How should grant overheads and indirect costs be managed and distributed?",
            analytical_frame=AnalyticalFrameType.GOVERNANCE_GOODS_ALLOCATION,
            economic_good_classification_policy="ENABLED",
            alternative_classification_scheme="overhead_distribution_taxonomies",
            observed_response_count=10,
            missing_response_count=1,
            missing_participant_ids=["PARTICIPANT_007"],
            provenance=dummy_prov,
        ),
        "Q14": QuestionSpec(
            question_id="Q14",
            question_index=14,
            column_headers_by_lang={"fr": "14. Avez-vous_des_remarques__suggestions"},
            canonical_prompt_en="Open strategic remarks and governance suggestions",
            analytical_frame=AnalyticalFrameType.OPEN_STRATEGIC_PRIORITY,
            economic_good_classification_policy="CONDITIONAL",
            alternative_classification_scheme="strategic_priorities",
            observed_response_count=8,
            missing_response_count=3,
            missing_participant_ids=["PARTICIPANT_002", "PARTICIPANT_006", "PARTICIPANT_011"],
            provenance=dummy_prov,
        ),
    }
    return specs


def get_multilingual_test_fixtures() -> Dict[str, Any]:
    """Return realistic multilingual response fixtures for unit and integration testing."""
    fixtures = {
        # French substantive responses
        "FR_01": {
            "participant_id": "PART_FR_01",
            "question_id": "Q08",
            "language": "fr",
            "text": "La gestion RH et les recrutements doivent impérativement rester au niveau du laboratoire et des professeurs. Le pôle peut coordonner, mais pas décider.",
            "is_substantive": True,
            "response_status": "observed_substantive",
            "expected_quotes": [
                "gestion RH et les recrutements doivent impérativement rester au niveau du laboratoire et des professeurs",
                "Le pôle peut coordonner, mais pas décider",
            ],
            "expected_subtopics": [
                {
                    "label": "Decentralized Lab-Level Recruitment",
                    "description": "Retention of hiring authority at the laboratory and professor level.",
                    "alternatives": {"laboratory_level": 0.85, "pole_level": 0.15},
                    "importance": 0.95,
                    "confidence": 0.90,
                    "good_class": "club_good",
                }
            ],
            "expected_values": [
                {
                    "original_label": "Academic Autonomy",
                    "polarity": 1.0,
                    "quotes": ["gestion RH et les recrutements doivent impérativement rester au niveau du laboratoire et des professeurs"],
                },
                {
                    "original_label": "Operational Subsidiarity",
                    "polarity": 1.0,
                    "quotes": ["Le pôle peut coordonner, mais pas décider"],
                },
            ],
        },
        "FR_02": {
            "participant_id": "PART_FR_02",
            "question_id": "Q11",
            "language": "fr",
            "text": "Les overheads doivent être redistribués avec justice : 40% au laboratoire porteur pour inciter les chercheurs, 30% au pôle mutualisé, et 30% au socle commun.",
            "is_substantive": True,
            "response_status": "observed_substantive",
            "expected_quotes": [
                "40% au laboratoire porteur pour inciter les chercheurs",
                "30% au pôle mutualisé, et 30% au socle commun",
            ],
            "expected_subtopics": [
                {
                    "label": "Three-Tier Overhead Sharing Formula",
                    "description": "Proportional split between PI laboratory, thematic pole, and central core.",
                    "alternatives": {"formula_40_30_30": 0.70, "full_lab_return": 0.20, "centralized_pool": 0.10},
                    "importance": 0.90,
                    "confidence": 0.95,
                    "good_class": "common_good",
                }
            ],
            "expected_values": [
                {
                    "original_label": "Inter-Team Redistribution Fairness",
                    "polarity": 1.0,
                    "quotes": ["30% au pôle mutualisé, et 30% au socle commun"],
                },
            ],
        },
        "FR_MIXED": {
            "participant_id": "PART_FR_MIX",
            "question_id": "Q08",
            "language": "fr",
            "text": "Je ne connais pas assez la répartition budgétaire actuelle, mais pour les recrutements doctoraux la décision doit rester au laboratoire.",
            "is_substantive": True,
            "response_status": "mixed_substantive_and_uncertainty",
            "expected_quotes": [
                "pour les recrutements doctoraux la décision doit rester au laboratoire",
            ],
            "uncertainty_quotes": [
                "Je ne connais pas assez la répartition budgétaire actuelle",
            ],
            "expected_subtopics": [
                {
                    "label": "Doctoral Recruitment Authority",
                    "description": "Decision rights for doctoral hiring placed at laboratory level.",
                    "alternatives": {"laboratory_level": 0.95, "pole_level": 0.05},
                    "importance": 0.85,
                    "confidence": 0.90,
                    "good_class": "club_good",
                }
            ],
        },
        # German substantive responses
        "DE_01": {
            "participant_id": "PART_DE_01",
            "question_id": "Q08",
            "language": "de",
            "text": "Personalentscheidungen und Stellenbesetzungen müssen dezentral bei den Forschungsgruppen verbleiben. Eine zentrale Steuerung führt nur zu bürokratischen Verzögerungen.",
            "is_substantive": True,
            "response_status": "observed_substantive",
            "expected_quotes": [
                "Personalentscheidungen und Stellenbesetzungen müssen dezentral bei den Forschungsgruppen verbleiben",
                "Eine zentrale Steuerung führt nur zu bürokratischen Verzögerungen",
            ],
            "expected_subtopics": [
                {
                    "label": "Decentralized Research Group Staffing",
                    "description": "Opposition to centralized hiring oversight due to administrative delay.",
                    "alternatives": {"laboratory_level": 0.90, "central_university": 0.10},
                    "importance": 0.92,
                    "confidence": 0.88,
                    "good_class": "private_good",
                }
            ],
            "expected_values": [
                {
                    "original_label": "Academic Autonomy",
                    "polarity": 1.0,
                    "quotes": ["Personalentscheidungen und Stellenbesetzungen müssen dezentral bei den Forschungsgruppen verbleiben"],
                },
            ],
        },
        "DE_02": {
            "participant_id": "PART_DE_02",
            "question_id": "Q01",
            "language": "de",
            "text": "Die thematischen Schwerpunkte der Zentren sind sinnvoll gewählt, aber es herrscht Unklarheit über die strategische Zielsetzung im Vergleich zu den Instituten.",
            "is_substantive": True,
            "response_status": "observed_substantive",
            "expected_quotes": [
                "thematischen Schwerpunkte der Zentren sind sinnvoll gewählt",
                "Unklarheit über die strategische Zielsetzung",
            ],
            "expected_subtopics": [
                {
                    "label": "Strategic Role Ambiguity of Centers",
                    "description": "Diagnostic observation of unclear boundaries between thematic centers and faculties.",
                    "alternatives": {"positive_diagnostic": 0.40, "ambiguous_role_diagnostic": 0.60},
                    "importance": 0.75,
                    "confidence": 0.90,
                    "good_class": "NOT_APPLICABLE",
                    "frame_label": "diagnostic_role_clarity",
                }
            ],
        },
        # English substantive response
        "EN_01": {
            "participant_id": "PART_EN_01",
            "question_id": "Q04",
            "language": "en",
            "text": "A unified administrative framework is essential to reduce overhead duplication, but laboratories must retain budget execution autonomy and mentoring continuity.",
            "is_substantive": True,
            "response_status": "observed_substantive",
            "expected_quotes": [
                "unified administrative framework is essential to reduce overhead duplication",
                "laboratories must retain budget execution autonomy and mentoring continuity",
            ],
            "expected_subtopics": [
                {
                    "label": "Hybrid Unified Administration with Decentralized Execution",
                    "description": "Harmonized administrative rules combined with local laboratory spending authority.",
                    "alternatives": {"unified_framework": 0.55, "decentralized_execution": 0.45},
                    "importance": 0.85,
                    "confidence": 0.92,
                    "good_class": "public_good",
                }
            ],
            "expected_values": [
                {
                    "original_label": "Mentoring Continuity",
                    "polarity": None,
                    "quotes": ["laboratories must retain budget execution autonomy and mentoring continuity"],
                },
            ],
        },
        # Reportable epistemic non-preference statements (preserved with zero fabricated preference)
        "FR_NO_OPINION": {
            "participant_id": "PART_EPI_01",
            "question_id": "Q08",
            "language": "fr",
            "text": "Pas d'avis sur cette question.",
            "is_substantive": True,
            "response_status": "explicit_no_opinion",
            "expected_state": MissingnessState.OBSERVED_USABLE,
        },
        "DE_INSUFF_EXP": {
            "participant_id": "PART_EPI_02",
            "question_id": "Q08",
            "language": "de",
            "text": "Ich habe zu wenig Erfahrung mit dem System, um das zu beurteilen.",
            "is_substantive": True,
            "response_status": "insufficient_experience",
            "expected_state": MissingnessState.OBSERVED_USABLE,
        },
        "EN_INSUFF_INFO": {
            "participant_id": "PART_EPI_03",
            "question_id": "Q11",
            "language": "en",
            "text": "Insufficient information about the overhead figures to take a stance.",
            "is_substantive": True,
            "response_status": "insufficient_information",
            "expected_state": MissingnessState.OBSERVED_USABLE,
        },
        # Non-substantive cases (True missingness -> zero coding)
        "MISSING_BLANK": {
            "participant_id": "PART_MISSING_01",
            "question_id": "Q08",
            "language": "fr",
            "text": "   ",
            "is_substantive": False,
            "expected_state": MissingnessState.MISSING_RAW_BLANK,
        },
        "MISSING_NA": {
            "participant_id": "PART_MISSING_02",
            "question_id": "Q08",
            "language": "en",
            "text": "N/A",
            "is_substantive": False,
            "expected_state": MissingnessState.MISSING_NON_SUBSTANTIVE,
        },
        "MISSING_FRENCH_NONE": {
            "participant_id": "PART_MISSING_03",
            "question_id": "Q11",
            "language": "fr",
            "text": "Pas de remarque.",
            "is_substantive": False,
            "expected_state": MissingnessState.MISSING_NON_SUBSTANTIVE,
        },
        "MISSING_GERMAN": {
            "participant_id": "PART_MISSING_04",
            "question_id": "Q04",
            "language": "de",
            "text": "Keine Angabe.",
            "is_substantive": False,
            "expected_state": MissingnessState.MISSING_NON_SUBSTANTIVE,
        },
    }
    return fixtures
