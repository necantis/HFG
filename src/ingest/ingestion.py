"""Survey Ingestion & Normalization Engine for HFG.

Owned by: Agent 01 — Data & Question Registry
Schema Version: 1.0.0 / v1.1.0
Contract: answers_normalized_v1 (data/normalized/answers_normalized.parquet)
Input: survey_raw_v1 (data/raw/survey_raw.csv, write-once immutable source)

Enforces:
1. Cryptographic SHA-256 integrity verification of the raw immutable survey.
2. RFC-compliant CSV parsing supporting multiline quoted cells.
3. Stable anonymized participant identifiers (PARTICIPANT_001 .. PARTICIPANT_011).
4. Stable response identifiers (RESP_001_Q01 .. RESP_011_Q14).
5. Per-cell language detection across supported languages ('fr', 'de', 'en').
6. Strict missingness classification (observed_usable, missing_raw_blank, missing_non_substantive).
7. Zero missingness imputation invariant: missing cells are never imputed with 0.0 or synthetic scores.
8. Parquet and JSON dual export with schema conformance.
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

# Substantive question definitions (Q01-Q13 + Q14 remarks)
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

# Non-substantive refusal or lack of opinion patterns
NON_SUBSTANTIVE_EXACT = {
    "?", "-", ".", "/", "na", "n/a", "none", "ras", "r.a.s.", "aucun", "sans", "nein", "no"
}

NON_SUBSTANTIVE_PHRASES = [
    r"aucun avis",
    r"pas d'avis",
    r"sans avis",
    r"je n'ai aucun avis",
    r"pas d'exp[eé]rience",
    r"je ne peux pas (?:encore )?r[eé]pondre",
    r"je ne sais pas",
    r"ne sais pas",
    r"keine angabe",
    r"keine meinung",
    r"wei[sß] nicht",
    r"don't know",
    r"no opinion",
    r"no idea",
]


def compute_sha256(filepath: Path | str) -> str:
    """Compute SHA-256 digest of a file."""
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


def classify_missingness(raw_val: str) -> Tuple[str, bool, List[str]]:
    """Classify missingness state for a raw survey cell.
    
    Returns:
        (missingness_state, is_valid, validation_flags)
    """
    if raw_val is None:
        return (MissingnessState.MISSING_RAW_BLANK.value, False, ["EMPTY_RESPONSE"])

    cleaned = raw_val.strip()
    if not cleaned:
        return (MissingnessState.MISSING_RAW_BLANK.value, False, ["EMPTY_RESPONSE"])

    # Check non-substantive exact tokens
    norm_token = re.sub(r"[^\w\?/]", "", cleaned.lower())
    if norm_token in NON_SUBSTANTIVE_EXACT or cleaned in NON_SUBSTANTIVE_EXACT:
        return (MissingnessState.MISSING_NON_SUBSTANTIVE.value, False, ["NON_SUBSTANTIVE_TEXT"])

    # Check short refusal/non-substantive phrases (only if response is concise / primarily refusal)
    if len(cleaned) < 180:
        cleaned_lower = cleaned.lower()
        for phrase in NON_SUBSTANTIVE_PHRASES:
            if re.search(phrase, cleaned_lower):
                return (MissingnessState.MISSING_NON_SUBSTANTIVE.value, False, ["NON_SUBSTANTIVE_TEXT"])

    return (MissingnessState.OBSERVED_USABLE.value, True, [])


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
            fieldnames = [fn.lstrip("\ufeff") for fn in (reader.fieldnames or [])]
            # Reconstruct reader with clean fieldnames if BOM was stripped
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

                # Classify missingness
                missingness_state, is_valid, validation_flags = classify_missingness(raw_value)

                # Detect language
                detected_lang = detect_language(cleaned_value, fallback_lang=declared_lang)

                response_id = f"RESP_{obs_num:03d}_{q_id}"

                record = {
                    "response_id": response_id,
                    "participant_id": participant_id,
                    "question_id": q_id,
                    "raw_question_header": col_name,
                    "response_type": "open_text",
                    "detected_language": detected_lang,
                    "raw_value": raw_value,
                    "normalized_value": cleaned_value,
                    "raw_response_sha256": raw_cell_sha256,
                    "char_length": char_length,
                    "missingness_state": missingness_state,
                    "is_valid": is_valid,
                    "validation_flags": validation_flags,
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
    print(f"Observed usable: {(df_out['missingness_state'] == 'observed_usable').sum()} cells.")
    print(f"Missing blank: {(df_out['missingness_state'] == 'missing_raw_blank').sum()} cells.")
    print(f"Missing non-substantive: {(df_out['missingness_state'] == 'missing_non_substantive').sum()} cells.")
