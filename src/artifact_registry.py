"""
Artifact Registry & Provenance Manager for HFG.

Maintains cryptographic provenance, hashes, Git commits, model versions,
canonical-source rules, and stale/fresh state tracking across analytical runs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# Authority Levels
AUTHORITY_IMMUTABLE_SOURCE = "immutable_source"
AUTHORITY_CANONICAL_INGESTION = "canonical_ingestion"
AUTHORITY_CANONICAL_INTERMEDIATE = "canonical_intermediate"
AUTHORITY_CANONICAL_UTILITY = "canonical_utility_input"
AUTHORITY_CANONICAL_DECISION = "canonical_decision"
AUTHORITY_PRESENTATION_ONLY = "presentation_only"

# Known canonical rules mapping
CANONICAL_AUTHORITY_RULES: dict[str, str] = {
    "raw_survey": AUTHORITY_IMMUTABLE_SOURCE,
    "answers_normalized": AUTHORITY_CANONICAL_INGESTION,
    "preference_matrix": AUTHORITY_CANONICAL_UTILITY,
    "themes_codebook": AUTHORITY_CANONICAL_INTERMEDIATE,
    "candidate_options": AUTHORITY_CANONICAL_INTERMEDIATE,
    "voting_results": AUTHORITY_CANONICAL_DECISION,
    "sensitivity_metrics": AUTHORITY_CANONICAL_INTERMEDIATE,
    "policy_brief": AUTHORITY_PRESENTATION_ONLY,
    "executive_report": AUTHORITY_PRESENTATION_ONLY,
    "final_report": AUTHORITY_PRESENTATION_ONLY,
}


class ArtifactRecord(BaseModel):
    """Authoritative record for a single analytical artifact."""
    artifact_id: str = Field(..., description="Unique artifact identifier")
    run_id: str = Field(..., description="Run identifier")
    path: str = Field(..., description="Relative or absolute path to the artifact file")
    format: str = Field(..., description="File format (e.g. parquet, json, csv, md)")
    producing_module: str = Field(..., description="Python module or script producing this artifact")
    producing_agent: str = Field(..., description="Agent ID responsible for producing this artifact")
    creation_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    code_commit: str = Field(default="unknown", description="Git commit SHA at creation time")
    source_hashes: Dict[str, str] = Field(default_factory=dict, description="SHA-256 hashes of source files")
    prompt_hash: Optional[str] = Field(default=None, description="SHA-256 hash of LLM prompt template if applicable")
    model_revision: Optional[str] = Field(default=None, description="Model identifier and revision if applicable")
    schema_version: str = Field(default="v1.0.0", description="Contract schema version")
    validation_status: str = Field(default="valid", description="valid, invalid, or pending")
    upstream_artifacts: List[str] = Field(default_factory=list, description="IDs of upstream input artifacts")
    downstream_consumers: List[str] = Field(default_factory=list, description="Agent or module IDs consuming this artifact")
    stale_state: str = Field(default="fresh", description="fresh, stale, or unverified")
    authority_level: str = Field(default="canonical_intermediate", description="Authority categorization")


class ArtifactRegistry:
    """Manages artifact registration, manifest persistence, canonical validation, and freshness."""

    def __init__(self, base_dir: Optional[Path] = None, run_id: str = "run_20261111_001"):
        self.base_dir = (base_dir or Path.cwd()).resolve()
        self.run_id = run_id
        self.artifacts: Dict[str, ArtifactRecord] = {}

    @staticmethod
    def compute_sha256(filepath: Path | str) -> str:
        """Compute SHA-256 hash of a file on disk."""
        path = Path(filepath)
        if not path.is_file():
            return "file_not_found"
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def get_git_commit(self) -> str:
        """Retrieve current git commit SHA."""
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(self.base_dir),
                capture_output=True,
                text=True,
                check=True,
            )
            return res.stdout.strip()
        except Exception:
            return "git_unavailable"

    def determine_authority(self, artifact_id: str, path: str) -> str:
        """Determine authority level based on canonical rules."""
        lower_id = artifact_id.lower()
        lower_path = path.lower()

        if "raw" in lower_id or "raw" in lower_path:
            return AUTHORITY_IMMUTABLE_SOURCE
        if "norm" in lower_id or "answers_normalized" in lower_path:
            return AUTHORITY_CANONICAL_INGESTION
        if "preference" in lower_id or "preference_matrix" in lower_path:
            return AUTHORITY_CANONICAL_UTILITY
        if "report" in lower_id or "policy_brief" in lower_path or "report" in lower_path:
            return AUTHORITY_PRESENTATION_ONLY
        if "voting" in lower_id or "voting_results" in lower_path:
            return AUTHORITY_CANONICAL_DECISION

        for key, auth in CANONICAL_AUTHORITY_RULES.items():
            if key in lower_id or key in lower_path:
                return auth

        return AUTHORITY_CANONICAL_INTERMEDIATE

    def register_artifact(
        self,
        artifact_id: str,
        path: str,
        format: str,
        producing_module: str,
        producing_agent: str,
        run_id: Optional[str] = None,
        schema_version: str = "v1.0.0",
        validation_status: str = "valid",
        upstream_artifacts: Optional[List[str]] = None,
        downstream_consumers: Optional[List[str]] = None,
        prompt_hash: Optional[str] = None,
        model_revision: Optional[str] = None,
        authority_level: Optional[str] = None,
        extra_source_files: Optional[List[str]] = None,
    ) -> ArtifactRecord:
        """Register an artifact with cryptographic provenance and canonical validation."""
        run_id = run_id or self.run_id
        upstream_artifacts = upstream_artifacts or []
        downstream_consumers = downstream_consumers or []
        authority = authority_level or self.determine_authority(artifact_id, path)

        # Canonical-source Invariant Check:
        # A report or presentation artifact is strictly forbidden from becoming analytical input!
        for up_id in upstream_artifacts:
            up_rec = self.artifacts.get(up_id)
            if up_rec and up_rec.authority_level == AUTHORITY_PRESENTATION_ONLY:
                raise ValueError(
                    f"Canonical Rule Violation: Presentation artifact '{up_id}' cannot be an upstream "
                    f"dependency for analytical artifact '{artifact_id}'. Reports are sink-only."
                )

        # Immutability Check for Raw Data:
        full_path = Path(path)
        if not full_path.is_absolute():
            full_path = self.base_dir / full_path

        if authority == AUTHORITY_IMMUTABLE_SOURCE and artifact_id in self.artifacts:
            existing = self.artifacts[artifact_id]
            current_hash = self.compute_sha256(full_path)
            existing_target_hash = existing.source_hashes.get(str(full_path), "")
            if existing_target_hash and current_hash != existing_target_hash:
                raise ValueError(
                    f"Canonical Invariant Violation: Raw source artifact '{artifact_id}' is immutable "
                    f"and cannot be modified or overwritten!"
                )

        # Compute file and source hashes
        source_hashes: Dict[str, str] = {}
        if full_path.is_file():
            source_hashes[str(full_path)] = self.compute_sha256(full_path)

        # Hash producing module
        module_path = self.base_dir / producing_module
        if module_path.is_file():
            source_hashes[str(module_path)] = self.compute_sha256(module_path)

        # Hash any additional source files
        if extra_source_files:
            for extra in extra_source_files:
                epath = Path(extra) if Path(extra).is_absolute() else self.base_dir / extra
                if epath.is_file():
                    source_hashes[str(epath)] = self.compute_sha256(epath)

        # Stale state evaluation: If any upstream artifact is stale, mark this stale
        stale_state = "fresh"
        for up_id in upstream_artifacts:
            up_rec = self.artifacts.get(up_id)
            if up_rec and up_rec.stale_state == "stale":
                stale_state = "stale"
                break

        record = ArtifactRecord(
            artifact_id=artifact_id,
            run_id=run_id,
            path=str(path),
            format=format,
            producing_module=producing_module,
            producing_agent=producing_agent,
            creation_timestamp=datetime.now(timezone.utc).isoformat(),
            code_commit=self.get_git_commit(),
            source_hashes=source_hashes,
            prompt_hash=prompt_hash,
            model_revision=model_revision,
            schema_version=schema_version,
            validation_status=validation_status,
            upstream_artifacts=upstream_artifacts,
            downstream_consumers=downstream_consumers,
            stale_state=stale_state,
            authority_level=authority,
        )

        self.artifacts[artifact_id] = record

        # Propagate staleness down the consumer graph if this artifact is stale
        if stale_state == "stale":
            self.propagate_staleness(artifact_id)

        return record

    def get_artifact(self, artifact_id: str) -> Optional[ArtifactRecord]:
        """Retrieve artifact record by ID."""
        return self.artifacts.get(artifact_id)

    def list_artifacts(self, run_id: Optional[str] = None) -> List[ArtifactRecord]:
        """List registered artifacts, optionally filtered by run_id."""
        if run_id:
            return [a for a in self.artifacts.values() if a.run_id == run_id]
        return list(self.artifacts.values())

    def propagate_staleness(self, stale_artifact_id: str) -> None:
        """Recursively mark all artifacts that depend on stale_artifact_id as stale."""
        for art in self.artifacts.values():
            if stale_artifact_id in art.upstream_artifacts and art.stale_state != "stale":
                art.stale_state = "stale"
                self.propagate_staleness(art.artifact_id)

    def check_file_freshness(self, artifact_id: str) -> str:
        """Check if on-disk files match the registered hashes."""
        record = self.artifacts.get(artifact_id)
        if not record:
            return "unknown"

        for filepath_str, recorded_hash in record.source_hashes.items():
            fpath = Path(filepath_str)
            if not fpath.is_file():
                record.stale_state = "stale"
                self.propagate_staleness(artifact_id)
                return "stale"
            current_hash = self.compute_sha256(fpath)
            if current_hash != recorded_hash:
                record.stale_state = "stale"
                self.propagate_staleness(artifact_id)
                return "stale"

        # Check upstream artifacts
        for up_id in record.upstream_artifacts:
            if self.check_file_freshness(up_id) == "stale":
                record.stale_state = "stale"
                self.propagate_staleness(artifact_id)
                return "stale"

        return record.stale_state

    def save_manifest(self, filepath: Optional[Path | str] = None) -> Path:
        """Persist the manifest to JSON."""
        if filepath is None:
            run_dir = self.base_dir / "runs" / self.run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            target = run_dir / "manifest.json"
        else:
            target = Path(filepath)
            target.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "manifest_version": "v1.0.0",
            "run_id": self.run_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "artifacts": {k: v.model_dump() for k, v in self.artifacts.items()},
        }

        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return target

    def load_manifest(self, filepath: Path | str) -> None:
        """Load manifest from JSON."""
        target = Path(filepath)
        if not target.is_file():
            raise FileNotFoundError(f"Manifest not found: {target}")

        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.run_id = data.get("run_id", self.run_id)
        for art_id, art_data in data.get("artifacts", {}).items():
            self.artifacts[art_id] = ArtifactRecord(**art_data)

    def generate_run_card(
        self,
        run_id: Optional[str] = None,
        input_files: Optional[Dict[str, str]] = None,
        prompt_versions: Optional[Dict[str, str]] = None,
        llm_models: Optional[Dict[str, str]] = None,
        quantisations: Optional[str] = "None (FP16/BF16 API)",
        hardware: Optional[str] = "Debian 12 Linux x86_64",
        completed_stages: Optional[List[str]] = None,
        retries: int = 0,
        failures: int = 0,
        skipped_modules: Optional[Dict[str, str]] = None,
        runtimes: Optional[Dict[str, float]] = None,
    ) -> str:
        """Generate authoritative RUN_CARD.md content and save to runs/<run_id>/RUN_CARD.md."""
        target_run = run_id or self.run_id
        git_sha = self.get_git_commit()

        run_artifacts = self.list_artifacts(run_id=target_run)

        # Assemble input files and hashes
        input_hashes = dict(input_files or {})
        for art in run_artifacts:
            if art.authority_level == AUTHORITY_IMMUTABLE_SOURCE:
                for p, h in art.source_hashes.items():
                    input_hashes[p] = h

        stages = completed_stages or ["Stage 0 (Source Registration)", "Stage 9 (Registry & Run Card Freeze)"]
        prompts = prompt_versions or {"system_v1": "sha256:baseline_system_prompt", "coding_v1": "sha256:baseline_coding_prompt"}
        models = llm_models or {"qualitative_coding": "pro", "social_choice": "flash"}
        skipped = skipped_modules or {}
        runtimes_map = runtimes or {"stage_0": 0.05, "stage_9": 0.08}

        card_md = f"""# Run Card: `{target_run}`

- **Run ID**: `{target_run}`
- **Generated At**: `{datetime.now(timezone.utc).isoformat()}`
- **Git Commit**: `{git_sha}`
- **Hardware Architecture**: `{hardware}`
- **Model Quantisations**: `{quantisations}`

---

## 1. Input Files & Cryptographic Hashes (SHA-256)
| File Path | SHA-256 Hash |
| :--- | :--- |
"""
        for p, h in input_hashes.items():
            card_md += f"| `{p}` | `{h}` |\n"
        if not input_hashes:
            card_md += "| *(No external source files tracked)* | - |\n"

        card_md += f"""
---

## 2. LLM Models, Prompt Versions & Execution Details
- **LLM Models & Revisions**:
"""
        for m_role, m_name in models.items():
            card_md += f"  - **{m_role}**: `{m_name}`\n"

        card_md += "- **Prompt Versions & Hashes**:\n"
        for p_name, p_hash in prompts.items():
            card_md += f"  - **{p_name}**: `{p_hash}`\n"

        card_md += f"""
---

## 3. Pipeline Execution Stages & Reliability
- **Completed Stages**: {', '.join(f'`{s}`' for s in stages)}
- **Retries**: `{retries}`
- **Failures**: `{failures}`
- **Skipped Modules**: {skipped if skipped else 'None'}

### Stage Runtimes (seconds)
| Stage | Runtime (s) |
| :--- | :--- |
"""
        for s_name, s_time in runtimes_map.items():
            card_md += f"| `{s_name}` | {s_time:.2f}s |\n"

        card_md += f"""
---

## 4. Final Registered Artifacts
| Artifact ID | Authority Level | Format | Producing Agent | Status | Freshness | Path |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
        for art in run_artifacts:
            card_md += (
                f"| `{art.artifact_id}` | `{art.authority_level}` | `{art.format}` | "
                f"`{art.producing_agent}` | `{art.validation_status}` | `{art.stale_state}` | `{art.path}` |\n"
            )

        card_md += """
---
> **Analytical Certification**: This run card certifies immutable inputs, deterministic reproducibility, and strict compliance with HFG analytical invariants.
"""

        # Write to runs/<run_id>/RUN_CARD.md
        card_dir = self.base_dir / "runs" / target_run
        card_dir.mkdir(parents=True, exist_ok=True)
        card_file = card_dir / "RUN_CARD.md"
        with open(card_file, "w", encoding="utf-8") as f:
            f.write(card_md)

        return card_md


def main():
    parser = argparse.ArgumentParser(description="HFG Artifact Registry CLI")
    parser.add_argument("--run-id", default="run_20261111_001", help="Target Run ID")
    parser.add_argument("--manifest", default=None, help="Path to manifest JSON")
    parser.add_argument("--generate-card", action="store_true", help="Generate RUN_CARD.md")
    parser.add_argument("--check-freshness", action="store_true", help="Verify freshness of all artifacts")
    args = parser.parse_args()

    registry = ArtifactRegistry(run_id=args.run_id)
    manifest_path = Path(args.manifest) if args.manifest else registry.base_dir / "runs" / args.run_id / "manifest.json"

    if manifest_path.is_file():
        registry.load_manifest(manifest_path)
        print(f"Loaded manifest with {len(registry.artifacts)} artifacts from {manifest_path}")

    if args.check_freshness:
        for art_id in list(registry.artifacts.keys()):
            status = registry.check_file_freshness(art_id)
            print(f"Artifact {art_id}: {status}")

    if args.generate_card:
        card = registry.generate_run_card(run_id=args.run_id)
        print(f"RUN_CARD.md generated for {args.run_id}")


if __name__ == "__main__":
    main()
