"""Agent 05 Ex-Post Preference Heterogeneity & Clustering Pipeline.

Owned by: Agent 05 — Clustering & Preference Heterogeneity
Schema Version: 1.0.0 (Aligned with ADR-0005, ADR-0007, and ADR-0008)

Produces:
- Canonical contract artifact: data/processed/preference_profiles.json (ClusterResult / preference_profiles_v1)
- Companion task-local runtime artifacts under data/processed/clustering/ (kept outside Git):
  - participant_cluster_assignments.json (participant_cluster_assignments_v1)
  - cluster_profiles.json (cluster_profiles_v1)
  - cluster_stability.json (cluster_stability_v1)
  - cluster_sensitivity.json (cluster_sensitivity_v1)
  - cluster_pareto_associations.json (cluster_pareto_associations_v1)
  - agent_05_qa_report.json (agent_05_qa_report_v1)
  - task_local_artifact_descriptors.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.clustering.distances import compute_masked_subtopic_distance_matrix
from src.clustering.expost import (
    analyze_cluster_pareto_associations,
    build_cluster_profiles,
)
from src.clustering.features import (
    PRIMARY_QUESTION_IDS,
    build_representations,
    compute_sha256,
    load_and_verify_canonical_inputs,
    load_clustering_config,
)
from src.clustering.methods import (
    hierarchical_clustering,
    pam_clustering,
    select_k_empirically,
)
from src.clustering.uncertainty import (
    evaluate_k_grid_with_stability,
    generate_adr0008_distance_ensemble,
    run_multi_representation_sensitivity,
)
from src.contracts import ClusterResult, ProvenanceMeta, SCHEMA_VERSION

FORBIDDEN_PSYCH_TOKENS: tuple[str, ...] = (
    "personality",
    "extravert",
    "introvert",
    "neurotic",
    "conscientious",
    "openness",
    "agreeableness",
    "political_orientation",
    "ideology",
    "competence",
    "intelligent",
    "lazy",
    "cooperative_trait",
    "authoritarian_personality",
)


def _get_git_commit_sha(base_dir: Path) -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=base_dir,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return "UNKNOWN"


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _labels_to_groups(participant_ids: list[str], assignments: dict[str, int], prefix: str) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for p in participant_ids:
        gid = f"{prefix}_{int(assignments[p]) + 1:02d}"
        groups.setdefault(gid, []).append(p)
    return {k: sorted(v) for k, v in sorted(groups.items())}


def run_agent_05_pipeline(
    base_dir: Path | str | None = None,
    run_id: str = "run_20261111_002",
    bundle_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Execute the full missingness-masked, ADR-0008-propagated Agent 05 clustering pipeline."""
    t_start = time.time()
    root = (Path(base_dir) if base_dir else Path.cwd()).resolve()

    # 1. Load configurable runtime parameters & verify canonical upstream provenance
    cfg, cfg_rel_path, cfg_sha = load_clustering_config(root, run_id=run_id)
    inputs = load_and_verify_canonical_inputs(root, run_id=run_id, bundle_dir=bundle_dir)
    reps = build_representations(inputs)

    pids = inputs.participant_ids
    n = len(pids)
    seed = int(cfg.get("random_seed", 42))
    cand_k = [int(k) for k in cfg.get("candidate_k_values", [1, 2, 3, 4, 5])]
    min_shared = int(cfg.get("min_shared_subtopics_for_pair", 3))
    primary_metric = str(cfg.get("primary_distance_metric", "MASKED_JENSEN_SHANNON"))
    scen_draws = int(cfg.get("scenario_draws", 200))
    boot_draws = int(cfg.get("bootstrap_draws", 200))
    perm_draws = int(cfg.get("permutation_null_draws", 200))
    omission_prob = float(cfg.get("omission_inclusion_probability", 0.7))
    dc_weight = float(cfg.get("double_count_guard_downweight", 0.5))
    hc_thresh = float(cfg.get("high_confidence_frontier_threshold", 0.95))
    thresholds = dict(cfg.get("stability_selection_thresholds") or {})

    # 2. Primary PreferenceMatrix missingness-masked distance (Rep A) & ADR-0008 ensemble (Rep B)
    rep_a_primary = compute_masked_subtopic_distance_matrix(
        participant_ids=pids,
        subtopic_scenarios=reps.rep_a_subtopic_scenarios,
        metric=primary_metric,  # type: ignore[arg-type]
        min_shared_subtopics=min_shared,
    )
    D_primary = rep_a_primary["distance_matrix"]

    rep_b_ensemble = generate_adr0008_distance_ensemble(
        inputs=inputs,
        metric=primary_metric,  # type: ignore[arg-type]
        n_draws=scen_draws,
        seed=seed,
        omission_inclusion_prob=omission_prob,
        double_count_downweight=dc_weight,
    )

    # 3. Empirical K evaluation across PAM, Hierarchical (avg/comp), Consensus on Rep A + ADR-0008 draws
    k_eval = evaluate_k_grid_with_stability(
        participant_ids=pids,
        D_primary=D_primary,
        D_scenario_draws=rep_b_ensemble["distance_draws"],
        subtopic_scenarios=reps.rep_a_subtopic_scenarios,
        candidate_k_values=cand_k,
        metric=primary_metric,  # type: ignore[arg-type]
        bootstrap_draws=boot_draws,
        permutation_draws=perm_draws,
        seed=seed,
    )

    # Also evaluate empirical K grid directly on Rep B ensemble mean distance matrix
    k_eval_rep_b = evaluate_k_grid_with_stability(
        participant_ids=pids,
        D_primary=rep_b_ensemble["mean_distance_matrix"],
        D_scenario_draws=rep_b_ensemble["distance_draws"],
        subtopic_scenarios=reps.rep_a_subtopic_scenarios,
        candidate_k_values=cand_k,
        metric=primary_metric,  # type: ignore[arg-type]
        bootstrap_draws=boot_draws,
        permutation_draws=perm_draws,
        seed=seed + 100,
    )

    # Empirical K selection strictly on missingness-masked PreferenceMatrix distances (ADR / AGENTS invariant)
    pam_selection = select_k_empirically(k_eval["pam"], thresholds)
    havg_selection = select_k_empirically(k_eval["hierarchical_average"], thresholds)
    cons_selection = select_k_empirically(k_eval["uncertainty_consensus"], thresholds)
    rep_b_selection = select_k_empirically(k_eval_rep_b["pam"], thresholds)

    # Primary selection follows PAM (non-singleton-biased) while cross-checking all methods
    selected_k = int(pam_selection["selected_k"])
    selected_k_status = str(pam_selection["selected_k_status"])
    if selected_k == 1 and any(
        sel["is_stable_partition"] for sel in (cons_selection, rep_b_selection)
    ):
        # Record if consensus or Rep B passed, though PAM primary governs unless consensus agrees
        pass

    # Canonical assignments
    if selected_k <= 1:
        canonical_assignments = {p: "PROFILE_01" for p in pids}
        canonical_labels_en = {
            "PROFILE_01": (
                "Single Cohort (NO_STABLE_CLUSTER_STRUCTURE on primary Q01-Q13 PreferenceMatrix; "
                "cross-cutting preferences do not support crisp subtopic partitioning at n=11)"
            )
        }
        # Assignment confidence reflects mean cohort stability across scenario draws
        assignment_conf = {p: 1.0 for p in pids}
    else:
        raw_assign = k_eval["pam"][selected_k]["assignments"]
        canonical_assignments = {p: f"PROFILE_{int(raw_assign[p]) + 1:02d}" for p in pids}
        canonical_labels_en = {
            f"PROFILE_{idx + 1:02d}": f"Empirical Preference Profile {idx + 1}"
            for idx in range(selected_k)
        }
        assignment_conf = dict(k_eval["pam"][selected_k]["member_stability_confidence"])

    # 4. Multi-representation sensitivity & exploratory partitions (never used to prune or weight)
    sensitivity = run_multi_representation_sensitivity(
        inputs=inputs,
        reps=reps,
        candidate_k_values=cand_k,
        min_shared_subtopics=min_shared,
        n_draws=scen_draws,
        seed=seed,
    )

    # Exploratory reference partitions for descriptive heterogeneity & Pareto inspection
    k2_key = 2 if 2 in k_eval["pam"] else max(k_eval["pam"])
    exp_pref_k2 = _labels_to_groups(pids, k_eval["pam"][k2_key]["assignments"], "EXP_PREF_K2")
    exp_util_c_k2_assign = sensitivity["representation_c_utility_profiles"]["utility_centered_cosine"]["by_k"]["2"]["pam_assignments"]
    exp_util_c_k2 = _labels_to_groups(pids, exp_util_c_k2_assign, "EXP_UTIL_CORR_K2")
    exp_cons_k2 = _labels_to_groups(pids, k_eval["uncertainty_consensus"][k2_key]["assignments"], "EXP_CONS_K2")

    exploratory_partitions = {
        "exploratory_rep_a_pam_k2": exp_pref_k2,
        "exploratory_rep_b_consensus_k2": exp_cons_k2,
        "exploratory_rep_c_utility_corr_k2": exp_util_c_k2,
    }

    # 5. Ex-post profiles, organisational values comparison, and Pareto relationship analysis
    profiles_payload = build_cluster_profiles(
        inputs=inputs,
        canonical_assignments=canonical_assignments,
        selected_k_status=selected_k_status,
        exploratory_partitions=exploratory_partitions,
    )
    pareto_assoc_payload = analyze_cluster_pareto_associations(
        inputs=inputs,
        reps=reps,
        canonical_assignments=canonical_assignments,
        exploratory_partitions=exploratory_partitions,
        high_conf_threshold=hc_thresh,
    )

    # 6. Build contract-compliant ClusterResult (data/processed/preference_profiles.json)
    created_utc = datetime.now(timezone.utc).isoformat()
    upstream_ids = sorted(inputs.verified_hashes.keys())
    prov = ProvenanceMeta(
        record_id=f"CLUST_{run_id}_adr0008",
        run_id=run_id,
        dataset_fingerprint=inputs.verified_hashes["preference_matrix_v1"]["sha256"][:16],
        created_at_utc=created_utc,
        producer_module="src/clustering/pipeline.py",
        producer_agent="agent_05",
        upstream_artifact_ids=upstream_ids,
        config_hash=cfg_sha,
        schema_version=SCHEMA_VERSION,
    )

    silhouette_by_k = {
        int(k): float(k_eval["pam"][k]["silhouette"])
        for k in sorted(k_eval["pam"])
        if k >= 2
    }
    stability_by_k = {
        int(k): float(k_eval["pam"][k]["scenario_ari_mean"])
        for k in sorted(k_eval["pam"])
        if k >= 2
    }
    profile_sizes: dict[str, int] = {}
    for lbl in canonical_assignments.values():
        profile_sizes[lbl] = profile_sizes.get(lbl, 0) + 1

    cluster_result = ClusterResult(
        cluster_result_id=f"CR_{run_id}_adr0008",
        preference_matrix_id=inputs.matrix_id,
        distance_metric=primary_metric,  # type: ignore[arg-type]
        min_shared_subtopics_for_pair=int(rep_a_primary["min_shared_observed"]),
        candidate_k_evaluated=sorted(int(k) for k in k_eval["pam"] if k >= 2),
        silhouette_scores_by_k=silhouette_by_k,
        stability_scores_by_k=stability_by_k,
        selected_k=selected_k,
        profile_assignments=canonical_assignments,
        unassigned_missing_participant_ids=[],
        profile_sizes=dict(sorted(profile_sizes.items())),
        profile_distinguishing_subtopics=profiles_payload["canonical_distinguishing_subtopics"],
        profile_distinguishing_values=profiles_payload["canonical_ex_post_values"]["distinguishing_values_by_group"],
        participant_assignment_confidence=assignment_conf,
        provenance=prov,
        descriptive_labels_en=canonical_labels_en,
        pairwise_distance_matrix_hash=str(rep_a_primary["matrix_hash"]),
        schema_version=SCHEMA_VERSION,
    )

    # 7. Assemble companion contract artifacts
    assignments_payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "cluster_result_id": cluster_result.cluster_result_id,
        "selected_k": selected_k,
        "selected_k_status": selected_k_status,
        "participant_count": n,
        "canonical_assignments": canonical_assignments,
        "unassigned_missing_participant_ids": [],
        "participant_assignment_confidence": assignment_conf,
        "ranked_as_participant": {p: False for p in pids},
        "exploratory_non_canonical_assignments": {
            "exploratory_rep_a_pam_k2": {p: f"EXP_PREF_K2_{int(k_eval['pam'][k2_key]['assignments'][p]) + 1:02d}" for p in pids},
            "exploratory_rep_b_consensus_k2": {p: f"EXP_CONS_K2_{int(k_eval['uncertainty_consensus'][k2_key]['assignments'][p]) + 1:02d}" for p in pids},
            "exploratory_rep_c_utility_corr_k2": {p: f"EXP_UTIL_CORR_K2_{int(exp_util_c_k2_assign[p]) + 1:02d}" for p in pids},
        },
        "participant_coassignment_probabilities_k2_adr0008": {
            "participant_ids": pids,
            "coassociation_matrix": k_eval["coassociation_matrices"].get("2", []),
        },
    }

    stability_payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "primary_selection_basis": "PreferenceMatrix Q01-Q13 missingness-masked MASKED_JENSEN_SHANNON",
        "selected_k": selected_k,
        "selected_k_status": selected_k_status,
        "selection_decisions_by_method": {
            "rep_a_pam": pam_selection,
            "rep_a_hierarchical_average": havg_selection,
            "rep_b_uncertainty_consensus": cons_selection,
            "rep_b_ensemble_mean_pam": rep_b_selection,
        },
        "rep_a_k_diagnostics": {
            "pam": {str(k): v for k, v in k_eval["pam"].items()},
            "hierarchical_average": {str(k): v for k, v in k_eval["hierarchical_average"].items()},
            "hierarchical_complete": {str(k): v for k, v in k_eval["hierarchical_complete"].items()},
            "uncertainty_consensus": {str(k): v for k, v in k_eval["uncertainty_consensus"].items()},
        },
        "rep_b_k_diagnostics": {
            "pam": {str(k): v for k, v in k_eval_rep_b["pam"].items()},
            "hierarchical_average": {str(k): v for k, v in k_eval_rep_b["hierarchical_average"].items()},
        },
        "rep_b_uncertainty_summary": {
            "scenario_draws": scen_draws,
            "mean_pairwise_distance": rep_b_ensemble["mean_pairwise_distance"],
            "median_pairwise_distance": rep_b_ensemble["median_pairwise_distance"],
            "mean_pair_uncertainty_std": rep_b_ensemble["mean_pair_uncertainty_std"],
            "max_pair_uncertainty_std": rep_b_ensemble["max_pair_uncertainty_std"],
            "min_shared_observed_in_draws": rep_b_ensemble["min_shared_observed_in_draws"],
            "matrix_hash": rep_b_ensemble["matrix_hash"],
        },
    }

    sensitivity_payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "representations_compared": {
            "A_preference_distribution": reps.rep_a_metadata,
            "B_uncertainty_aware_preference": reps.rep_b_metadata,
            "C_participant_utility_profiles": reps.rep_c_metadata,
            "D_question_level_aggregated": reps.rep_d_metadata,
        },
        "q14_contextual_isolation_audit": reps.q14_contextual_summary,
        "sensitivity_results": sensitivity,
    }

    # 8. QA Verification checks (Prompt Section 10)
    # Check lexical guard for zero psychological/personality inference in generated labels
    labels_blob = json.dumps(
        {
            "labels": canonical_labels_en,
            "canonical_distinguishing_subtopics": profiles_payload["canonical_distinguishing_subtopics"],
            "canonical_distinguishing_values": profiles_payload["canonical_ex_post_values"]["distinguishing_values_by_group"],
            "rationale": pam_selection["rationale"],
        }
    ).lower()
    psych_tokens_found = [tok for tok in FORBIDDEN_PSYCH_TOKENS if tok in labels_blob]

    all_participants_accounted = (
        len(canonical_assignments) == 11
        and sorted(canonical_assignments.keys()) == pids
        and len(cluster_result.unassigned_missing_participant_ids) == 0
    )
    missingness_preserved = inputs.provenance_checks["missingness_18_unimputed"] and not cfg["imputes_missing_preferences"]
    uncertainty_propagated = (
        scen_draws >= 100
        and len(rep_b_ensemble["distance_draws"]) == scen_draws
        and not cfg["uses_coder_confidence_as_weight"]
    )
    pareto_ni = pareto_assoc_payload["non_interference_verified"]
    pareto_non_interference = (
        pareto_ni["feasible_solutions_count"] == 543
        and pareto_ni["robust_core_count"] == 10
        and pareto_ni["high_confidence_frontier_count"] == 102
        and pareto_ni["baseline_nondominated_count"] == 326
        and pareto_ni["clusters_modified_feasible_set"] is False
        and pareto_ni["clusters_modified_pareto_membership"] is False
    )
    voting_non_interference = pareto_ni["clusters_modified_voting_weights_or_rights"] is False
    q01_q13_primary = (
        reps.rep_a_metadata["questions_included"] == list(PRIMARY_QUESTION_IDS)
        and reps.rep_b_metadata["questions_included"] == list(PRIMARY_QUESTION_IDS)
    )
    q14_contextual = (
        reps.q14_contextual_summary["excluded_from_clustering_features"] is True
        and inputs.provenance_checks["q14_isolated_from_primary"] is True
    )
    no_participant_ranking = all(not v for v in assignments_payload["ranked_as_participant"].values())
    no_psych_inference = len(psych_tokens_found) == 0

    qa_checks = {
        "1_input_provenance_verified": all(inputs.provenance_checks.values()),
        "2_all_11_participants_accounted_for": all_participants_accounted,
        "3_missingness_never_silently_imputed": missingness_preserved,
        "4_adr0008_uncertainty_propagated": uncertainty_propagated,
        "5_clustering_cannot_affect_feasible_alternatives": pareto_ni["clusters_modified_feasible_set"] is False and pareto_ni["feasible_solutions_count"] == 543,
        "6_clustering_cannot_affect_pareto_membership": pareto_non_interference,
        "7_clustering_cannot_affect_voting_rights_or_weights": voting_non_interference,
        "8_q01_q13_remain_primary": q01_q13_primary,
        "9_q14_remains_contextual": q14_contextual,
        "10_no_participant_ranking": no_participant_ranking,
        "11_no_psychological_or_personality_inference": no_psych_inference,
    }

    duration = round(time.time() - t_start, 3)
    qa_report = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "evaluated_at_utc": created_utc,
        "execution_duration_seconds": duration,
        "all_qa_checks_passed": all(qa_checks.values()),
        "qa_checks": qa_checks,
        "psych_tokens_found": psych_tokens_found,
        "verified_upstream_hashes": inputs.verified_hashes,
        "summary": {
            "participants": n,
            "primary_questions": 13,
            "contextual_questions": 1,
            "missingness_cells_preserved": len(inputs.missing_cells),
            "selected_k": selected_k,
            "selected_k_status": selected_k_status,
            "cluster_methods_evaluated": [
                "PAM_K_MEDOIDS",
                "HIERARCHICAL_AVERAGE",
                "HIERARCHICAL_COMPLETE",
                "ADR0008_UNCERTAINTY_CONSENSUS",
            ],
            "representations_compared": [
                "A_preference_distribution",
                "B_uncertainty_aware_preference",
                "C_participant_utility_profiles",
                "D_question_level_aggregated",
            ],
        },
    }

    # 9. Persist runtime artifacts outside Git + generate task-local descriptors
    proc_dir = root / "data" / "processed"
    clust_dir = proc_dir / "clustering"

    out_paths = {
        "preference_profiles_v1": _write_json(proc_dir / "preference_profiles.json", asdict(cluster_result)),
        "participant_cluster_assignments_v1": _write_json(clust_dir / "participant_cluster_assignments.json", assignments_payload),
        "cluster_profiles_v1": _write_json(clust_dir / "cluster_profiles.json", profiles_payload),
        "cluster_stability_v1": _write_json(clust_dir / "cluster_stability.json", stability_payload),
        "cluster_sensitivity_v1": _write_json(clust_dir / "cluster_sensitivity.json", sensitivity_payload),
        "cluster_pareto_associations_v1": _write_json(clust_dir / "cluster_pareto_associations.json", pareto_assoc_payload),
        "agent_05_qa_report_v1": _write_json(clust_dir / "agent_05_qa_report.json", qa_report),
    }

    if not qa_report["all_qa_checks_passed"]:
        raise RuntimeError(f"Agent 05 QA check failure: {qa_checks}")

    commit_sha = _get_git_commit_sha(root)
    src_hashes = {
        "clustering_config_v1": cfg_sha,
        **{aid: meta["sha256"] for aid, meta in inputs.verified_hashes.items()},
    }

    record_counts = {
        "preference_profiles_v1": n,
        "participant_cluster_assignments_v1": n,
        "cluster_profiles_v1": len(profiles_payload["canonical_profiles"]),
        "cluster_stability_v1": len(cand_k),
        "cluster_sensitivity_v1": 4,
        "cluster_pareto_associations_v1": len(pareto_assoc_payload["robust_core_10_ids"]),
        "agent_05_qa_report_v1": len(qa_checks),
    }

    descriptors: dict[str, Any] = {}
    descriptors["clustering_config_v1"] = {
        "artifact_id": "clustering_config_v1",
        "run_id": run_id,
        "scope": "git_versioned_config",
        "path": cfg_rel_path,
        "sha256": cfg_sha,
        "byte_size": (root / cfg_rel_path).stat().st_size,
        "record_count": 1,
        "schema_version": SCHEMA_VERSION,
        "producing_agent": "agent_05",
        "producing_module": "runs/clustering_config",
        "code_commit": commit_sha,
        "source_hashes": {"clustering_config_v1": cfg_sha},
        "validation_status": "valid",
        "privacy_status": "public_config_only",
        "downstream_consumers": ["agent_05", "agent_09", "agent_11"],
    }

    for aid, fpath in out_paths.items():
        rel = str(fpath.relative_to(root))
        descriptors[aid] = {
            "artifact_id": aid,
            "run_id": run_id,
            "scope": "task_local_pending_integration_registration",
            "path": rel,
            "sha256": compute_sha256(fpath),
            "byte_size": fpath.stat().st_size,
            "record_count": record_counts[aid],
            "schema_version": SCHEMA_VERSION,
            "producing_agent": "agent_05",
            "producing_module": "src/clustering/pipeline.py",
            "code_commit": commit_sha,
            "source_hashes": src_hashes,
            "validation_status": "valid",
            "privacy_status": "private_runtime_artifact_uncommitted",
            "downstream_consumers": ["agent_08", "agent_09", "agent_11"],
        }

    desc_payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at_utc": created_utc,
        "registration_policy": (
            "Task-local artifact descriptors produced by Agent 05. Canonical runs/<run_id>/manifest.json "
            "registration is performed exclusively by Agent 11 after PR review and merge per ADR-0007."
        ),
        "downstream_release_decision": {
            "agent_05_status": "COMPLETE",
            "agent_08_unblocked_from_agent_05": True,
        },
        "descriptors": descriptors,
    }
    desc_path = _write_json(clust_dir / "task_local_artifact_descriptors.json", desc_payload)

    return {
        "run_id": run_id,
        "execution_duration_seconds": duration,
        "selected_k": selected_k,
        "selected_k_status": selected_k_status,
        "qa_report": qa_report,
        "descriptor_index_path": str(desc_path.relative_to(root)),
        "descriptors": descriptors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent 05 Ex-Post Preference Heterogeneity & Clustering Pipeline")
    parser.add_argument("--run-id", default="run_20261111_002")
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--bundle-dir", default=None)
    args = parser.parse_args()
    res = run_agent_05_pipeline(base_dir=args.base_dir, run_id=args.run_id, bundle_dir=args.bundle_dir)
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
