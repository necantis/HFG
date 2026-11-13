"""Question Registry Engine for HFG.

Owned by: Agent 01 — Data & Question Registry
Schema Version: 1.0.0 / v1.1.0
Contract: QuestionSpec (src/contracts.py, docs/DATA_CONTRACTS.md)

Refinements:
1. Distinguishes Q01-Q13 as primary questions from Q14 as optional contextual remarks.
2. Does not permanently prohibit economic good classification solely because a question is
   labelled perception or open comment. Question-level policy serves as an initial guide;
   subtopic-level classification is conditional on evidence evaluated by Agent 02.
3. Dynamically computes observed vs. missing response counts and participant partitions.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import pandas as pd

from src.contracts import AnalyticalFrameType, ProvenanceMeta, QuestionSpec
from src.ingest.ingestion import (
    ACTIVE_RUN_ID,
    EXPECTED_RAW_SHA256,
    OPTIONAL_REMARKS_QUESTIONS,
    PRIMARY_QUESTIONS,
    QUESTION_MAP,
    compute_sha256,
)

QUESTION_METADATA: dict[str, dict[str, Any]] = {
    "Q01": {
        "index": 1,
        "is_primary": True,
        "question_scope": "primary",
        "column_fr": "1. Pertinence_de_ces_poles",
        "canonical_prompt_en": "Relevance of the proposed poles of competence",
        "prompt_fr": "Pertinence de ces pôles",
        "analytical_frame": AnalyticalFrameType.PERCEPTION_AND_DIAGNOSTIC,
        "economic_good_policy": "CONDITIONAL",  # Initial guide: perception; Agent 02 decides subtopics conditionally
        "alternative_classification_scheme": "perception_diagnostic",
        "domain_tags": ["poles", "relevance", "strategic_alignment"],
    },
    "Q02": {
        "index": 2,
        "is_primary": True,
        "question_scope": "primary",
        "column_fr": "2. Pertinence_des_personnes_identifiees",
        "canonical_prompt_en": "Relevance and appropriateness of identified individuals and role assignments",
        "prompt_fr": "Pertinence des personnes identifiées",
        "analytical_frame": AnalyticalFrameType.PERCEPTION_AND_DIAGNOSTIC,
        "economic_good_policy": "CONDITIONAL",
        "alternative_classification_scheme": "personnel_diagnostic",
        "domain_tags": ["people", "composition", "leadership"],
    },
    "Q03": {
        "index": 3,
        "is_primary": True,
        "question_scope": "primary",
        "column_fr": "3. Denomination_de_ces_poles",
        "canonical_prompt_en": "Denomination and naming conventions of the poles",
        "prompt_fr": "Dénomination de ces pôles",
        "analytical_frame": AnalyticalFrameType.PERCEPTION_AND_DIAGNOSTIC,
        "economic_good_policy": "CONDITIONAL",
        "alternative_classification_scheme": "taxonomy_naming",
        "domain_tags": ["nomenclature", "branding", "terminology"],
    },
    "Q04": {
        "index": 4,
        "is_primary": True,
        "question_scope": "primary",
        "column_fr": "4. Faut-il_un_fonctionnement_unifie_entre_l",
        "canonical_prompt_en": "Necessity and modalities of unified operation across institutes and laboratories",
        "prompt_fr": "Faut-il un fonctionnement unifié entre les pôles / instituts ?",
        "analytical_frame": AnalyticalFrameType.INSTITUTIONAL_DESIGN_DECISION,
        "economic_good_policy": "CONDITIONAL",
        "alternative_classification_scheme": "governance_integration",
        "domain_tags": ["integration", "autonomy", "standardization"],
    },
    "Q05": {
        "index": 5,
        "is_primary": True,
        "question_scope": "primary",
        "column_fr": "5. Quelle_coordination_de_pole_choisir_Scen",
        "canonical_prompt_en": "Selection of pole coordination scenario (leadership and steering structure)",
        "prompt_fr": "Quelle coordination de pôle choisir (Scénario 1, 2 ou 3) ?",
        "analytical_frame": AnalyticalFrameType.INSTITUTIONAL_DESIGN_DECISION,
        "economic_good_policy": "CONDITIONAL",
        "alternative_classification_scheme": "coordination_scenarios",
        "domain_tags": ["coordination", "leadership", "decision_rights"],
    },
    "Q06": {
        "index": 6,
        "is_primary": True,
        "question_scope": "primary",
        "column_fr": "6. Tres_concretement_avez-vous_des_inputs_c",
        "canonical_prompt_en": "Concrete inputs, priorities, and bottom-up collaboration feedback for coordination",
        "prompt_fr": "Très concrètement, avez-vous des inputs / propositions pour la coordination ?",
        "analytical_frame": AnalyticalFrameType.PERCEPTION_AND_DIAGNOSTIC,
        "economic_good_policy": "CONDITIONAL",
        "alternative_classification_scheme": "operational_proposals",
        "domain_tags": ["feedback", "operational", "collaboration"],
    },
    "Q07": {
        "index": 7,
        "is_primary": True,
        "question_scope": "primary",
        "column_fr": "7. Les_engagements_doivent-ils_etre_faits_e",
        "canonical_prompt_en": "Level at which contractual and project commitments should be made (pole vs. laboratory)",
        "prompt_fr": "Les engagements doivent-ils être faits au niveau du pôle ou du laboratoire ?",
        "analytical_frame": AnalyticalFrameType.GOVERNANCE_GOODS_ALLOCATION,
        "economic_good_policy": "ENABLED",
        "alternative_classification_scheme": "commitment_level",
        "domain_tags": ["commitments", "responsibility", "contracting"],
    },
    "Q08": {
        "index": 8,
        "is_primary": True,
        "question_scope": "primary",
        "column_fr": "8. A_quel_niveau_la_gestion_RH_notamment_le",
        "canonical_prompt_en": "Level of HR and recruitment management (institute, pole, laboratory, or professor)",
        "prompt_fr": "À quel niveau la gestion RH, notamment les recrutements, doit-elle se situer ?",
        "analytical_frame": AnalyticalFrameType.GOVERNANCE_GOODS_ALLOCATION,
        "economic_good_policy": "ENABLED",
        "alternative_classification_scheme": "hr_authority_level",
        "domain_tags": ["hr", "recruitment", "authority"],
    },
    "Q09": {
        "index": 9,
        "is_primary": True,
        "question_scope": "primary",
        "column_fr": "9. Le_pole_dans_son_ensemble_est_responsabl",
        "canonical_prompt_en": "Financial and budgetary responsibility of the pole as a whole (handling deficits/surpluses)",
        "prompt_fr": "Le pôle dans son ensemble est-il responsable de son budget / équilibre financier ?",
        "analytical_frame": AnalyticalFrameType.GOVERNANCE_GOODS_ALLOCATION,
        "economic_good_policy": "ENABLED",
        "alternative_classification_scheme": "financial_responsibility",
        "domain_tags": ["finance", "risk_pooling", "solidarity"],
    },
    "Q10": {
        "index": 10,
        "is_primary": True,
        "question_scope": "primary",
        "column_fr": "10. Comment_le_socle_doit-il_etre_gere_Scena",
        "canonical_prompt_en": "Management and allocation mechanism for core funding (socle) (Scenario 1, 2, or 3)",
        "prompt_fr": "Comment le socle doit-il être géré (Scénarios) ?",
        "analytical_frame": AnalyticalFrameType.GOVERNANCE_GOODS_ALLOCATION,
        "economic_good_policy": "ENABLED",
        "alternative_classification_scheme": "core_funding_scenarios",
        "domain_tags": ["core_funding", "budget_distribution", "resource_allocation"],
    },
    "Q11": {
        "index": 11,
        "is_primary": True,
        "question_scope": "primary",
        "column_fr": "11. Comment_les_overheads_doivent-ils_etre_g",
        "canonical_prompt_en": "Allocation and redistribution rules for indirect research overheads",
        "prompt_fr": "Comment les overheads doivent-ils être gérés et répartis ?",
        "analytical_frame": AnalyticalFrameType.GOVERNANCE_GOODS_ALLOCATION,
        "economic_good_policy": "ENABLED",
        "alternative_classification_scheme": "overheads_allocation",
        "domain_tags": ["overheads", "indirect_costs", "redistribution"],
    },
    "Q12": {
        "index": 12,
        "is_primary": True,
        "question_scope": "primary",
        "column_fr": "12. Comment_les_primes_de_depot_doivent_etre",
        "canonical_prompt_en": "Allocation and incentive rules for proposal submission bonuses (primes de dépôt)",
        "prompt_fr": "Comment les primes de dépôt doivent-elles être attribuées ?",
        "analytical_frame": AnalyticalFrameType.GOVERNANCE_GOODS_ALLOCATION,
        "economic_good_policy": "ENABLED",
        "alternative_classification_scheme": "submission_bonus_incentives",
        "domain_tags": ["incentives", "proposal_bonus", "research_promotion"],
    },
    "Q13": {
        "index": 13,
        "is_primary": True,
        "question_scope": "primary",
        "column_fr": "13. Comment_gerer_les_evaluations_individuel",
        "canonical_prompt_en": "Governance and criteria for individual evaluations and collaborative performance",
        "prompt_fr": "Comment gérer les évaluations individuelles et collectives ?",
        "analytical_frame": AnalyticalFrameType.INSTITUTIONAL_DESIGN_DECISION,
        "economic_good_policy": "CONDITIONAL",
        "alternative_classification_scheme": "evaluation_governance",
        "domain_tags": ["performance_evaluation", "incentives", "collaboration"],
    },
    "Q14": {
        "index": 14,
        "is_primary": False,
        "question_scope": "optional_contextual_remarks",
        "column_fr": "14. Avez-vous_des_remarques__suggestions",
        "canonical_prompt_en": "Open remarks, suggestions, and broader organizational feedback",
        "prompt_fr": "Avez-vous des remarques / suggestions supplémentaires ?",
        "analytical_frame": AnalyticalFrameType.OPEN_STRATEGIC_PRIORITY,
        "economic_good_policy": "CONDITIONAL",
        "alternative_classification_scheme": "open_strategic_priority",
        "domain_tags": ["remarks", "suggestions", "open_feedback"],
    },
}


class QuestionRegistry:
    """Manages the 13 substantive survey questions plus optional remarks as QuestionSpec instances."""

    def __init__(
        self,
        raw_csv_path: Path | str = "data/raw/survey_raw.csv",
        run_id: str = ACTIVE_RUN_ID,
    ):
        self.raw_csv_path = Path(raw_csv_path)
        self.run_id = run_id
        self.specs: Dict[str, QuestionSpec] = {}

    def build_from_answers(
        self, answers_df_or_path: pd.DataFrame | Path | str
    ) -> Dict[str, QuestionSpec]:
        """Build question registry dynamically by linking questions with observed/missing response data."""
        if isinstance(answers_df_or_path, (str, Path)):
            path = Path(answers_df_or_path)
            if path.suffix == ".parquet":
                df = pd.read_parquet(path)
            else:
                df = pd.read_json(path)
        else:
            df = answers_df_or_path

        raw_sha256 = (
            compute_sha256(self.raw_csv_path)
            if self.raw_csv_path.is_file()
            else EXPECTED_RAW_SHA256
        )
        created_at_utc = datetime.now(timezone.utc).isoformat()

        all_participant_ids = sorted(df["participant_id"].unique().tolist())
        self.specs = {}

        for q_id, meta in QUESTION_METADATA.items():
            q_subset = df[df["question_id"] == q_id]
            # Use has_usable_preference if present, otherwise fallback to missingness_state == observed_usable
            if "has_usable_preference" in q_subset.columns:
                usable_mask = q_subset["has_usable_preference"] == True
            else:
                usable_mask = q_subset["missingness_state"] == "observed_usable"

            observed_participants = set(q_subset[usable_mask]["participant_id"])
            missing_participants = sorted(
                list(set(all_participant_ids) - observed_participants)
            )

            observed_count = len(observed_participants)
            missing_count = len(missing_participants)

            column_headers = {
                "fr": meta["column_fr"],
                "en": meta["canonical_prompt_en"],
            }

            domain_tags = list(meta["domain_tags"])
            if meta["is_primary"]:
                domain_tags.append("primary_question")
            else:
                domain_tags.append("optional_contextual_remarks")

            provenance = ProvenanceMeta(
                record_id=f"QSPEC_{q_id}_{self.run_id}",
                run_id=self.run_id,
                dataset_fingerprint=raw_sha256,
                created_at_utc=created_at_utc,
                producer_module="src/registry/question_registry.py",
                producer_agent="agent_01",
                upstream_artifact_ids=["raw_survey_v1"],
            )

            spec = QuestionSpec(
                question_id=q_id,
                question_index=meta["index"],
                column_headers_by_lang=column_headers,
                canonical_prompt_en=meta["canonical_prompt_en"],
                analytical_frame=meta["analytical_frame"],
                economic_good_classification_policy=meta["economic_good_policy"],
                alternative_classification_scheme=meta["alternative_classification_scheme"],
                observed_response_count=observed_count,
                missing_response_count=missing_count,
                missing_participant_ids=missing_participants,
                frame_assignment_source="DECLARED_CONFIG",
                prompt_fr=meta["prompt_fr"],
                prompt_de=None,
                domain_tags=domain_tags,
                provenance=provenance,
            )
            self.specs[q_id] = spec

        return self.specs

    def get_question(self, question_id: str) -> QuestionSpec:
        """Retrieve QuestionSpec by ID."""
        if question_id not in self.specs:
            raise KeyError(f"Question '{question_id}' not found in registry.")
        return self.specs[question_id]

    def list_questions(self) -> List[QuestionSpec]:
        """List all questions (Q01-Q14)."""
        return list(self.specs.values())

    def get_substantive_questions(self) -> List[QuestionSpec]:
        """Return the 13 substantive primary questions (Q01-Q13)."""
        return [s for s in self.specs.values() if s.question_index <= 13]

    def save_registry(self, output_path: Path | str = "data/normalized/question_registry.json") -> Path:
        """Serialize question specs to JSON."""
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        questions_dict = {}
        for k, v in self.specs.items():
            meta = QUESTION_METADATA.get(k, {})
            d = asdict(v)
            d["is_primary_question"] = meta.get("is_primary", True)
            d["question_scope"] = meta.get("question_scope", "primary")
            questions_dict[k] = d

        data = {
            "schema_version": "1.0.0",
            "run_id": self.run_id,
            "question_count": len(self.specs),
            "primary_question_count": len(self.get_substantive_questions()),
            "substantive_question_count": len(self.get_substantive_questions()),
            "optional_remarks_question_count": len(self.specs) - len(self.get_substantive_questions()),
            "questions": questions_dict,
        }

        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return target


def build_question_registry(
    answers_df_or_path: pd.DataFrame | Path | str = "data/normalized/answers_normalized.parquet",
    raw_csv_path: Path | str = "data/raw/survey_raw.csv",
    output_json: Path | str = "data/normalized/question_registry.json",
    run_id: str = ACTIVE_RUN_ID,
) -> QuestionRegistry:
    """Convenience function to build and save question registry."""
    registry = QuestionRegistry(raw_csv_path=raw_csv_path, run_id=run_id)
    registry.build_from_answers(answers_df_or_path)
    registry.save_registry(output_json)
    return registry


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build and serialize question registry.")
    parser.add_argument("--answers", default="data/normalized/answers_normalized.parquet", help="Path to normalized answers.")
    parser.add_argument("--raw-csv", default="data/raw/survey_raw.csv", help="Path to raw CSV.")
    parser.add_argument("--out-json", default="data/normalized/question_registry.json", help="Output JSON path.")
    parser.add_argument("--run-id", default=ACTIVE_RUN_ID, help="Active run ID.")
    args = parser.parse_args()

    reg = build_question_registry(
        answers_df_or_path=args.answers,
        raw_csv_path=args.raw_csv,
        output_json=args.out_json,
        run_id=args.run_id,
    )
    print(f"Successfully registered {len(reg.specs)} questions ({len(reg.get_substantive_questions())} primary).")
    for q in reg.list_questions():
        print(f"  {q.question_id} (Q{q.question_index:02d}): observed={q.observed_response_count}, missing={q.missing_response_count}, frame={q.analytical_frame.value}, economic_good_policy={q.economic_good_classification_policy}")
