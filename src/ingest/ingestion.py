"""Survey Ingestion & Normalization Engine for HFG.

Owned by: Agent 01 — Data & Question Registry
Schema Version: 1.0.0 / v1.1.0
Contract: answers_normalized_v1 (data/normalized/answers_normalized.parquet)
Input: survey_raw_v1 (data/raw/survey_raw.csv, write-once immutable source)

Refinements (Wave 2 Refinement):
1. Distinguishes text presence (text_supplied) from preference availability (has_usable_preference)
   and fine-grained epistemic status (epistemic_status).
2. Preserves explicit no-opinion and insufficient-experience statements as observed evidence
   for descriptive reporting, without assigning invented institutional preference scores.
3. Preserves ambiguous statements and mixed uncertainty-preference responses for downstream
   qualitative coding (Agent 02).
4. Strictly preserves original untrimmed source_text (raw_value) and documents that evidence
   offsets (char_start, char_end) refer to source_text.
5. Explicitly differentiates primary questions (Q01-Q13) from optional contextual remarks (Q14).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

import pandas as pd

from src.contracts import MissingnessState, ProvenanceMeta

# Authoritative run coordinates and expected raw hash
EXPECTED_RAW_SHA256 = "56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95"
EXPECTED_RESPONDENT_COUNT = 11
EXPECTED_COLUMN_COUNT = 27
ACTIVE_RUN_ID = "run_20261111_002"
PRODUCER_AGENT = "agent_01"
PRODUCER_MODULE = "src/ingest/ingestion.py"

# Substantive question definitions (Q01-Q13 primary + Q14 optional contextual remarks)
QUESTION_MAP: dict[str, str] = {
    "1. Pertinence_de_ces_poles": "Q01",
    "2. Pertinence_des_personnes_identifiees": "Q02",
    "3. Denomination_de_ces_poles": "Q03",
    "4. Faut-il_un_fonctionnement_unifie_entre_l": "Q04",
    "5. Quelle_coordination_de_pole_choisir_Scen": "Q05",
    "6. Tres_concretement_avez-vous_des_inputs_c": "Q06",
    "7. Les_engagements_doivent-ils_etre_faits_e": "Q07",
    "8. A_quel_niveau_la_gestion_RH_notamment_le": "Q08",
    "9. Le_pole_dans_son_ensemble_est_responsabl": "Q09",
    "10. Comment_le_socle_doit-il_etre_gere_Scena": "Q10",
    "11. Comment_les_overheads_doivent-ils_etre_g": "Q11",
    "12. Comment_les_primes_de_depot_doivent_etre": "Q12",
    "13. Comment_gerer_les_evaluations_individuel": "Q13",
    "14. Avez-vous_des_remarques__suggestions": "Q14",
}

PRIMARY_QUESTIONS: set[str] = {f"Q{i:02d}" for i in range(1, 14)}
OPTIONAL_REMARKS_QUESTIONS: set[str] = {"Q14"}


def compute_sha256(filepath: Path | str) -> str:
    """Compute SHA-256 digest of a file on disk."""
    path = Path(filepath)
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def detect_language(text: str, fallback_lang: str = "fr") -> Literal["fr", "de", "en"]:
    """Detect language of a text snippet using token set intersections.
    
    Supported: 'fr', 'de', 'en'.
    Fallback: participant's declared language or 'fr'.
    """
    if not text or not text.strip():
        if fallback_lang.lower() in ("fr", "de", "en"):
            return fallback_lang.lower()  # type: ignore
        return "fr"

    tokens = set(re.findall(r"\b[a-zA-ZàâäéèêëîïôöùûüçÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ]+\b", text.lower()))
    if not tokens:
        if fallback_lang.lower() in ("fr", "de", "en"):
            return fallback_lang.lower()  # type: ignore
        return "fr"

    fr_markers = {
        "le", "la", "les", "de", "des", "du", "un", "une", "et", "en", "dans", "pour", "sur",
        "avec", "par", "ce", "cette", "ces", "est", "sont", "au", "aux", "qui", "que", "ne",
        "pas", "se", "son", "sa", "ses", "leur", "leurs", "nous", "vous", "ils", "plus", "ou",
        "mais", "être", "avoir", "fait", "faire", "pôle", "pôles", "doit", "doivent", "comment",
        "comme", "bien", "aussi", "tout", "tous", "très", "donc", "sous", "vers", "sans"
    }
    de_markers = {
        "der", "die", "das", "und", "nicht", "ein", "eine", "für", "mit", "auf", "ist", "wir",
        "sollte", "keine", "dass", "oder", "aber", "über", "auch", "von", "zu", "im", "dem",
        "den", "sind", "werden", "wenn", "kann", "können", "noch", "hier"
    }
    en_markers = {
        "the", "and", "is", "for", "with", "should", "not", "are", "this", "that", "have",
        "from", "about", "which", "will", "would", "could", "all", "our", "their", "into"
    }

    fr_cnt = len(tokens & fr_markers)
    de_cnt = len(tokens & de_markers)
    en_cnt = len(tokens & en_markers)

    counts = {"fr": fr_cnt, "de": de_cnt, "en": en_cnt}
    best_lang, best_cnt = max(counts.items(), key=lambda item: item[1])

    if best_cnt > 0:
        return best_lang  # type: ignore

    if fallback_lang.lower() in ("fr", "de", "en"):
        return fallback_lang.lower()  # type: ignore

    return "fr"


def classify_response_semantics(
    raw_val: Optional[str], question_id: str = ""
) -> Dict[str, Any]:
    """Refined classification separating text presence, epistemic status, and preference availability.
    
    Distinguishes:
    - raw_blank
    - punctuation_uninterpretable
    - explicit_no_opinion
    - explicit_insufficient_experience
    - mixed_uncertainty_and_preference
    - ambiguous
    - no_additional_remarks
    - substantive
    """
    if raw_val is None:
        return {
            "text_supplied": False,
            "response_presence": "blank",
            "epistemic_status": "raw_blank",
            "has_usable_preference": False,
            "missingness_state": MissingnessState.MISSING_RAW_BLANK.value,
            "is_valid": False,
            "validation_flags": ["RAW_BLANK"],
        }

    cleaned = raw_val.strip()
    if not cleaned:
        return {
            "text_supplied": False,
            "response_presence": "blank",
            "epistemic_status": "raw_blank",
            "has_usable_preference": False,
            "missingness_state": MissingnessState.MISSING_RAW_BLANK.value,
            "is_valid": False,
            "validation_flags": ["RAW_BLANK"],
        }

    # 1. Punctuation only / uninterpretable symbols
    if re.fullmatch(r"[\?\.\-\/\!\:\;\,\s]+", cleaned):
        return {
            "text_supplied": True,
            "response_presence": "provided",
            "epistemic_status": "punctuation_uninterpretable",
            "has_usable_preference": False,
            "missingness_state": MissingnessState.MISSING_NON_SUBSTANTIVE.value,
            "is_valid": False,
            "validation_flags": ["PUNCTUATION_UNINTERPRETABLE"],
        }

    cleaned_lower = cleaned.lower()

    # 2. Context-sensitive "RAS"
    if cleaned_lower in ("ras", "r.a.s.", "rien à signaler", "rien a signaler"):
        if question_id in OPTIONAL_REMARKS_QUESTIONS:
            return {
                "text_supplied": True,
                "response_presence": "provided",
                "epistemic_status": "no_additional_remarks",
                "has_usable_preference": False,
                "missingness_state": MissingnessState.MISSING_NON_SUBSTANTIVE.value,
                "is_valid": False,
                "validation_flags": ["NO_ADDITIONAL_REMARKS"],
            }
        else:
            # In a substantive evaluation question (e.g. Q02), "RAS" is ambiguous
            # (could mean "no objection / fine as is" or "no comment").
            # Preserve text for downstream qualitative interpretation.
            return {
                "text_supplied": True,
                "response_presence": "provided",
                "epistemic_status": "ambiguous",
                "has_usable_preference": False,
                "missingness_state": MissingnessState.AMBIGUOUS.value,
                "is_valid": False,
                "validation_flags": ["MARKED_FOR_DOWNSTREAM_INTERPRETATION"],
            }

    # 3. Pure explicit no-opinion (without an accompanying alternative preference)
    if any(
        re.fullmatch(p, cleaned_lower.strip(" .!"))
        for p in [
            r"aucun avis",
            r"pas d\'avis",
            r"sans avis",
            r"je n\'ai aucun avis",
            r"je n\'ai aucun avis l[aà]-dessus",
            r"keine meinung",
            r"no opinion",
        ]
    ):
        return {
            "text_supplied": True,
            "response_presence": "provided",
            "epistemic_status": "explicit_no_opinion",
            "has_usable_preference": False,
            "missingness_state": MissingnessState.MISSING_NON_SUBSTANTIVE.value,
            "is_valid": False,
            "validation_flags": ["EXPLICIT_NO_OPINION"],
        }

    # 4. Pure explicit insufficient experience or information (pure refusal)
    if any(
        re.fullmatch(p, cleaned_lower.strip(" .!"))
        for p in [
            r"pas d\'exp[eé]rience",
            r"pas d\'exp[eé]rience,\s*pas d\'avis",
            r"je ne peux pas (?:encore )?r[eé]pondre.*pas assez d\'exp[eé]rience",
            r"keine angabe",
            r"pas assez d\'informations",
        ]
    ):
        return {
            "text_supplied": True,
            "response_presence": "provided",
            "epistemic_status": "explicit_insufficient_experience",
            "has_usable_preference": False,
            "missingness_state": MissingnessState.MISSING_NON_SUBSTANTIVE.value,
            "is_valid": False,
            "validation_flags": ["EXPLICIT_INSUFFICIENT_EXPERIENCE"],
        }

    # 5. Mixed response: uncertainty/inexperience combined with a substantive question/position
    has_uncertainty_marker = any(
        re.search(p, cleaned_lower)
        for p in [
            r"pas d\'exp[eé]rience",
            r"je ne peux pas (?:encore )?r[eé]pondre",
            r"je ne sais pas",
            r"difficile pour moi de donner une r[eé]ponse",
            r"ne comprends pas la question",
        ]
    )
    has_substantive_continuation = len(cleaned) > 80 or any(
        w in cleaned_lower
        for w in [
            "mais",
            "pourquoi",
            "préfère",
            "prefere",
            "soumis",
            "propose",
            "si on veut",
            "plutôt",
            "plutot",
            "en concertation",
            "néanmoins",
            "neanmoins",
        ]
    )

    if has_uncertainty_marker and has_substantive_continuation:
        return {
            "text_supplied": True,
            "response_presence": "provided",
            "epistemic_status": "mixed_uncertainty_and_preference",
            "has_usable_preference": True,
            "missingness_state": MissingnessState.OBSERVED_USABLE.value,
            "is_valid": True,
            "validation_flags": ["UNCERTAINTY_WITH_QUALITATIVE_CRITIQUE"],
        }

    # 6. Ambiguous reservations (preserve for downstream coding)
    if cleaned_lower in ("à réfléchir encore un peu", "a reflechir encore un peu"):
        return {
            "text_supplied": True,
            "response_presence": "provided",
            "epistemic_status": "ambiguous",
            "has_usable_preference": False,
            "missingness_state": MissingnessState.AMBIGUOUS.value,
            "is_valid": False,
            "validation_flags": ["MARKED_FOR_DOWNSTREAM_INTERPRETATION"],
        }

    # 7. Substantive qualitative responses (including "Oui", "Non", "Idem", detailed proposals)
    return {
        "text_supplied": True,
        "response_presence": "provided",
        "epistemic_status": "substantive",
        "has_usable_preference": True,
        "missingness_state": MissingnessState.OBSERVED_USABLE.value,
        "is_valid": True,
        "validation_flags": [],
    }


def classify_missingness(raw_val: str, question_id: str = "") -> Tuple[str, bool, List[str]]:
    """Backward-compatible wrapper returning (missingness_state, is_valid, validation_flags)."""
    res = classify_response_semantics(raw_val, question_id=question_id)
    return (res["missingness_state"], res["is_valid"], res["validation_flags"])


class SurveyIngester:
    """Ingests raw survey CSV and produces canonical normalized answers."""

    def __init__(
        self,
        raw_csv_path: Path | str = "data/raw/survey_raw.csv",
        expected_sha256: str = EXPECTED_RAW_SHA256,
        run_id: str = ACTIVE_RUN_ID,
    ):
        self.raw_csv_path = Path(raw_csv_path)
        self.expected_sha256 = expected_sha256
        self.run_id = run_id

    def verify_raw_source_integrity(self) -> str:
        """Verify that the immutable raw source exists and matches expected hash."""
        if not self.raw_csv_path.is_file():
            raise FileNotFoundError(f"Raw survey CSV not found at: {self.raw_csv_path}")

        computed_hash = compute_sha256(self.raw_csv_path)
        if self.expected_sha256 and computed_hash != self.expected_sha256:
            raise ValueError(
                f"Raw survey cryptographic integrity failure!\n"
                f"Expected SHA-256: {self.expected_sha256}\n"
                f"Computed SHA-256: {computed_hash}"
            )
        return computed_hash

    def parse_raw_csv(self) -> Tuple[List[str], List[Dict[str, str]]]:
        """Parse raw CSV using RFC-compliant DictReader to properly handle multiline fields."""
        with open(self.raw_csv_path, mode="r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            rows: List[Dict[str, str]] = []
            f.seek(0)
            raw_reader = csv.reader(f)
            header = next(raw_reader)
            clean_header = [h.lstrip("\ufeff") for h in header]
            for row_vals in raw_reader:
                row_dict = dict(zip(clean_header, row_vals))
                rows.append(row_dict)

        if len(rows) != EXPECTED_RESPONDENT_COUNT:
            raise ValueError(
                f"RFC CSV parse dimension violation: expected {EXPECTED_RESPONDENT_COUNT} respondents, "
                f"got {len(rows)}"
            )

        if len(clean_header) != EXPECTED_COLUMN_COUNT:
            raise ValueError(
                f"RFC CSV column dimension violation: expected {EXPECTED_COLUMN_COUNT} columns, "
                f"got {len(clean_header)}"
            )

        return clean_header, rows

    def normalize(self) -> pd.DataFrame:
        """Normalize raw survey responses into canonical long-format answers."""
        raw_sha256 = self.verify_raw_source_integrity()
        header, rows = self.parse_raw_csv()

        normalized_records: List[Dict[str, Any]] = []
        created_at_utc = datetime.now(timezone.utc).isoformat()

        for obs_idx, row in enumerate(rows, start=1):
            obs_no_str = row.get("Obs_No", str(obs_idx)).strip()
            obs_num = int(obs_no_str) if obs_no_str.isdigit() else obs_idx
            participant_id = f"PARTICIPANT_{obs_num:03d}"
            declared_lang = row.get("22. LANG_SAISIE", "FR").strip().lower()

            for col_name, q_id in QUESTION_MAP.items():
                raw_value = row.get(col_name, "")
                cleaned_value = raw_value.strip() if raw_value else ""

                # Compute SHA-256 of raw string
                raw_cell_sha256 = hashlib.sha256(raw_value.encode("utf-8")).hexdigest()
                char_length = len(raw_value)

                # Classify response semantics (separating presence, epistemic status, usable preference)
                sem = classify_response_semantics(raw_value, question_id=q_id)

                # Detect language
                detected_lang = detect_language(cleaned_value, fallback_lang=declared_lang)

                response_id = f"RESP_{obs_num:03d}_{q_id}"
                is_primary = q_id in PRIMARY_QUESTIONS
                question_scope = "primary" if is_primary else "optional_contextual_remarks"

                record = {
                    "response_id": response_id,
                    "participant_id": participant_id,
                    "question_id": q_id,
                    "raw_question_header": col_name,
                    "is_primary_question": is_primary,
                    "question_scope": question_scope,
                    "response_type": "open_text",
                    "detected_language": detected_lang,
                    "raw_value": raw_value,
                    "source_text": raw_value,  # Explicit source text for character offsets
                    "normalized_value": cleaned_value,
                    "normalized_text": cleaned_value,
                    "offset_reference_text": "source_text",  # Invariant: EvidenceSpan offsets refer to source_text
                    "raw_response_sha256": raw_cell_sha256,
                    "char_length": char_length,
                    "text_supplied": sem["text_supplied"],
                    "response_presence": sem["response_presence"],
                    "epistemic_status": sem["epistemic_status"],
                    "has_usable_preference": sem["has_usable_preference"],
                    "missingness_state": sem["missingness_state"],
                    "is_valid": sem["is_valid"],
                    "validation_flags": sem["validation_flags"],
                    "participant_declared_lang": declared_lang,
                    "run_id": self.run_id,
                    "dataset_fingerprint": raw_sha256,
                    "producer_agent": PRODUCER_AGENT,
                    "producer_module": PRODUCER_MODULE,
                    "created_at_utc": created_at_utc,
                }
                normalized_records.append(record)

        df = pd.DataFrame(normalized_records)
        return df

    def export(
        self,
        df: pd.DataFrame,
        parquet_path: Path | str = "data/normalized/answers_normalized.parquet",
        json_path: Optional[Path | str] = "data/normalized/answers_normalized.json",
    ) -> Tuple[Path, Optional[Path]]:
        """Export normalized DataFrame to parquet and json."""
        p_path = Path(parquet_path)
        p_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(p_path, engine="pyarrow", index=False)

        j_path = None
        if json_path:
            j_path = Path(json_path)
            j_path.parent.mkdir(parents=True, exist_ok=True)
            records = df.to_dict(orient="records")
            with open(j_path, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, ensure_ascii=False)

        return p_path, j_path


def ingest_survey(
    raw_csv_path: Path | str = "data/raw/survey_raw.csv",
    output_parquet: Path | str = "data/normalized/answers_normalized.parquet",
    output_json: Optional[Path | str] = "data/normalized/answers_normalized.json",
    run_id: str = ACTIVE_RUN_ID,
) -> pd.DataFrame:
    """Convenience function to ingest raw survey and persist normalized outputs."""
    ingester = SurveyIngester(raw_csv_path=raw_csv_path, run_id=run_id)
    df = ingester.normalize()
    ingester.export(df, parquet_path=output_parquet, json_path=output_json)
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest raw survey CSV into normalized long-format answers.")
    parser.add_argument("--raw-csv", default="data/raw/survey_raw.csv", help="Path to raw CSV file.")
    parser.add_argument("--out-parquet", default="data/normalized/answers_normalized.parquet", help="Output parquet path.")
    parser.add_argument("--out-json", default="data/normalized/answers_normalized.json", help="Output json path.")
    parser.add_argument("--run-id", default=ACTIVE_RUN_ID, help="Active run ID.")
    args = parser.parse_args()

    print(f"Ingesting raw survey from {args.raw_csv}...")
    df_out = ingest_survey(
        raw_csv_path=args.raw_csv,
        output_parquet=args.out_parquet,
        output_json=args.out_json,
        run_id=args.run_id,
    )
    print(f"Successfully normalized {len(df_out)} answer records across {df_out['participant_id'].nunique()} participants.")
    print("Epistemic Status Breakdown:")
    for status, count in df_out["epistemic_status"].value_counts().items():
        print(f"  {status}: {count}")
    print("Missingness State Breakdown:")
    for state, count in df_out["missingness_state"].value_counts().items():
        print(f"  {state}: {count}")
    print(f"Text supplied: {df_out['text_supplied'].sum()} / {len(df_out)}")
    print(f"Has usable preference: {df_out['has_usable_preference'].sum()} / {len(df_out)}")
