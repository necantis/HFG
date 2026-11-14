"""Unit and Integration Tests for Agent 05 — Missingness-Masked Clustering & Preference Heterogeneity.

Owned by: Agent 05
Tests invariants from ADR-0005, ADR-0007, ADR-0008, and AGENTS.md:
1. Non-imputation & missingness-masked distance invariants;
2. Zero coder_confidence weighting and zero fixed-K overfitting;
3. ADR-0008 uncertainty propagation (crosswalk disjointness, single-coder omission, dual-coder sets);
4. Empirical K-selection rejecting unstable noise partitions at small n;
5. Ex-post non-interference with feasible alternatives, Pareto frontier, and voting weights;
6. Staged run_20261111_002 runtime artifact audit when present locally.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from src.clustering.distances import (
    compute_masked_subtopic_distance_matrix,
    compute_question_aggregated_distance_matrix,
    compute_utility_distance_matrices,
    cosine_distance,
    jensen_shannon_distance,
    set_to_set_expected_distance,
    weighted_l1_distance,
)
from src.clustering.features import compute_sha256, load_clustering_config
from src.clustering.methods import (
    compute_leave_one_out_stability,
    compute_partition_geometry,
    consensus_clustering_from_coassociation,
    hierarchical_clustering,
    pam_clustering,
    select_k_empirically,
)
from src.clustering.pipeline import FORBIDDEN_PSYCH_TOKENS
from src.clustering.uncertainty import _sample_cell_distribution
from src.contracts import ClusterResult, ProvenanceMeta

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_clustering_config_non_interference_and_dynamic_k() -> None:
    cfg, rel_path, sha = load_clustering_config(REPO_ROOT, run_id="run_20261111_002")
    assert rel_path == "runs/run_20261111_002/clustering_config.json"
    assert len(sha) == 64
    assert cfg["uses_coder_confidence_as_weight"] is False
    assert cfg["imputes_missing_preferences"] is False
    assert cfg["modifies_feasible_set_or_pareto"] is False
    assert cfg["modifies_voting_weights_or_rights"] is False
    assert cfg["primary_question_ids"] == [f"Q{i:02d}" for i in range(1, 14)]
    assert cfg["contextual_question_ids"] == ["Q14"]
    assert 1 in cfg["candidate_k_values"] and len(cfg["candidate_k_values"]) >= 4


def test_missingness_masked_distances_never_impute() -> None:
    pids = ["P1", "P2", "P3"]
    base_map = {
        "P1": {
            "S1": [{"A": 1.0, "B": 0.0}],
            "S2": [{"X": 0.5, "Y": 0.5}],
        },
        "P2": {
            "S1": [{"A": 1.0, "B": 0.0}],
            "S2": [{"X": 0.5, "Y": 0.5}],
        },
        "P3": {
            "S1": [{"A": 0.0, "B": 1.0}],
        },
    }
    for metric in ("MASKED_JENSEN_SHANNON", "MASKED_COSINE", "MASKED_WEIGHTED_L1"):
        res1 = compute_masked_subtopic_distance_matrix(pids, base_map, metric=metric, min_shared_subtopics=1)
        D1 = res1["distance_matrix"]
        assert D1.shape == (3, 3)
        assert np.allclose(D1, D1.T)
        assert np.allclose(np.diag(D1), 0.0)
        assert pytest.approx(D1[0, 1], abs=1e-9) == 0.0
        assert D1[0, 2] > 0.9

        # Adding a non-shared subtopic to P3 must NOT change d(P1, P2) or d(P1, P3) (no zero imputation)
        extended = {
            **base_map,
            "P3": {**base_map["P3"], "S_ONLY_P3": [{"Z": 1.0}]},
        }
        res2 = compute_masked_subtopic_distance_matrix(pids, extended, metric=metric, min_shared_subtopics=1)
        assert np.allclose(D1, res2["distance_matrix"])

    # Verify distribution metrics stay bounded in [0, 1] and handle scenario sets without averaging
    d_set = set_to_set_expected_distance(
        [{"A": 1.0, "B": 0.0}, {"A": 0.0, "B": 1.0}],
        [{"A": 1.0, "B": 0.0}],
        jensen_shannon_distance,
    )
    assert pytest.approx(d_set, abs=1e-9) == 0.5
    assert 0.0 <= cosine_distance({"A": 0.7, "B": 0.3}, {"A": 0.2, "B": 0.8}) <= 1.0
    assert 0.0 <= weighted_l1_distance({"A": 0.7, "B": 0.3}, {"A": 0.2, "B": 0.8}) <= 1.0


def test_question_aggregated_and_utility_distances() -> None:
    pids = ["P1", "P2"]
    qmap = {
        "P1": {
            "Q01": {"S1": [{"A": 1.0}], "S2": [{"A": 1.0}], "S3": [{"A": 1.0}]},
            "Q02": {"S4": [{"X": 1.0, "Y": 0.0}]},
        },
        "P2": {
            "Q01": {"S1": [{"A": 1.0}], "S2": [{"A": 1.0}], "S3": [{"A": 1.0}]},
            "Q02": {"S4": [{"X": 0.0, "Y": 1.0}]},
        },
    }
    # Subtopic-weighted average = (0+0+0+1)/4 = 0.25; Question-aggregated = (0 + 1)/2 = 0.50
    sub_res = compute_masked_subtopic_distance_matrix(
        pids,
        {p: {s: v for qs in qm.values() for s, v in qs.items()} for p, qm in qmap.items()},
        metric="MASKED_WEIGHTED_L1",
        min_shared_subtopics=1,
    )
    q_res = compute_question_aggregated_distance_matrix(pids, qmap, metric="MASKED_WEIGHTED_L1")
    assert pytest.approx(sub_res["distance_matrix"][0, 1], abs=1e-9) == 0.25
    assert pytest.approx(q_res["distance_matrix"][0, 1], abs=1e-9) == 0.50

    u_mat = np.array(
        [
            [0.8, 0.7, 0.2, 0.1],
            [0.9, 0.8, 0.3, 0.2],
            [0.1, 0.2, 0.8, 0.9],
        ]
    )
    ud = compute_utility_distance_matrices(u_mat)
    assert ud["utility_centered_cosine"][0, 1] < 0.05
    assert ud["utility_centered_cosine"][0, 2] > 0.90
    assert ud["utility_spearman"][0, 1] == pytest.approx(0.0, abs=1e-9)
    assert ud["utility_rms_l2"][0, 1] < ud["utility_rms_l2"][0, 2]


def test_adr0008_sampling_zero_confidence_weight_and_disjoint_crosswalk() -> None:
    rng_a = np.random.default_rng(123)
    rng_b = np.random.default_rng(123)
    cell_low_conf = {
        "uncertainty_class": "DUAL_CODER_DISTRIBUTION_SET",
        "coder_confidence_a": 0.01,
        "coder_confidence_b": 0.99,
        "canonical_alternative_crosswalk": {"crosswalk_status": "EXACT_KEY_MATCH"},
        "preference_uncertainty_set": {
            "discrete_scenarios": [{"A": 0.8, "B": 0.2}, {"A": 0.2, "B": 0.8}],
            "interpretation_variants": ["explicit_mixed_preference"],
        },
    }
    cell_high_conf = {**cell_low_conf, "coder_confidence_a": 0.99, "coder_confidence_b": 0.01}

    # Changing coder_confidence must have ZERO effect on sampled distribution or weight
    s1 = _sample_cell_distribution(cell_low_conf, "coder_a", rng_a, 0.7, 0.5)
    s2 = _sample_cell_distribution(cell_high_conf, "coder_a", rng_b, 0.7, 0.5)
    assert s1 == s2

    # Disjoint crosswalk cell preserves separate coder axes
    cell_disjoint = {
        "uncertainty_class": "CROSSWALK_PARTIAL_OR_UNALIGNED",
        "canonical_alternative_crosswalk": {"crosswalk_status": "NO_VALID_CROSSWALK"},
        "preference_uncertainty_set": {
            "discrete_scenarios": [],
            "disjoint_coder_hypotheses": {"coder_a": {"opt1": 1.0}, "coder_b": {"opt2": 1.0}},
            "interpretation_variants": ["explicit_mixed_preference"],
        },
    }
    dist_a, w_a = _sample_cell_distribution(cell_disjoint, "coder_a", np.random.default_rng(1), 0.7, 0.5)
    dist_b, w_b = _sample_cell_distribution(cell_disjoint, "coder_b", np.random.default_rng(1), 0.7, 0.5)
    assert dist_a == {"coder_a:opt1": 1.0} and w_a == 1.0
    assert dist_b == {"coder_b:opt2": 1.0} and w_b == 1.0


def test_empirical_k_selection_separates_real_clusters_and_rejects_noise() -> None:
    # Construct 8-node crisp 2-block matrix
    D_crisp = np.full((8, 8), 0.85, dtype=np.float64)
    D_crisp[:4, :4] = 0.05
    D_crisp[4:, 4:] = 0.05
    np.fill_diagonal(D_crisp, 0.0)

    k_two = 2
    lbl_pam, meds, _ = pam_clustering(D_crisp, k_two)
    lbl_hier = hierarchical_clustering(D_crisp, k_two, "average")
    assert set(lbl_pam[:4]) != set(lbl_pam[4:])
    assert len(set(lbl_pam[:4])) == 1 and len(set(lbl_pam[4:])) == 1
    assert set(lbl_hier[:4]) != set(lbl_hier[4:])
    assert len(meds) == 2

    geom = compute_partition_geometry(D_crisp, lbl_pam)
    assert geom["silhouette"] > 0.85
    loo = compute_leave_one_out_stability(D_crisp, k_two, lambda D, k: pam_clustering(D, k)[0])
    assert loo["loo_ari_mean"] == pytest.approx(1.0, abs=1e-9)

    thresholds = {
        "min_silhouette": 0.25,
        "min_scenario_ari": 0.65,
        "min_bootstrap_ari": 0.65,
        "min_loo_ari": 0.65,
        "min_cluster_size": 2,
        "min_permutation_p_margin": 0.05,
    }
    passing_diag = {
        2: {
            "silhouette": 0.88,
            "scenario_ari_mean": 0.95,
            "bootstrap_ari_mean": 0.92,
            "loo_ari_mean": 1.0,
            "min_cluster_size": 4,
            "permutation_p_value": 0.005,
        }
    }
    sel_pass = select_k_empirically(passing_diag, thresholds)
    assert sel_pass["selected_k"] == 2
    assert sel_pass["is_stable_partition"] is True
    assert sel_pass["selected_k_status"] == "SELECTED_K_2"

    # Low silhouette + unstable scenario ARI -> must reject K>=2 and report NO_STABLE_CLUSTER_STRUCTURE
    weak_diag = {
        2: {
            "silhouette": 0.14,
            "scenario_ari_mean": 0.35,
            "bootstrap_ari_mean": 0.40,
            "loo_ari_mean": 0.85,
            "min_cluster_size": 5,
            "permutation_p_value": 0.25,
        }
    }
    sel_weak = select_k_empirically(weak_diag, thresholds)
    assert sel_weak["selected_k"] == 1
    assert sel_weak["is_stable_partition"] is False
    assert sel_weak["selected_k_status"] == "NO_STABLE_CLUSTER_STRUCTURE"

    # Consensus clustering check
    coassoc = np.zeros((8, 8), dtype=np.float64)
    coassoc[:4, :4] = 0.95
    coassoc[4:, 4:] = 0.95
    np.fill_diagonal(coassoc, 1.0)
    lbl_cons, _ = consensus_clustering_from_coassociation(coassoc, k_two)
    assert set(lbl_cons[:4]) != set(lbl_cons[4:])


def test_staged_production_run_20261111_002_outputs_if_present() -> None:
    prof_path = REPO_ROOT / "data" / "processed" / "preference_profiles.json"
    clust_dir = REPO_ROOT / "data" / "processed" / "clustering"
    desc_path = clust_dir / "task_local_artifact_descriptors.json"
    if not prof_path.is_file() or not desc_path.is_file():
        pytest.skip("Staged Agent 05 runtime outputs not present in clean CI clone.")

    raw_cr = json.loads(prof_path.read_text(encoding="utf-8"))
    prov = ProvenanceMeta(**raw_cr.pop("provenance"))
    cr = ClusterResult(**raw_cr, provenance=prov)

    assert len(cr.profile_assignments) == 11
    assert len(cr.unassigned_missing_participant_ids) == 0
    assert sum(cr.profile_sizes.values()) == 11
    assert cr.distance_metric in ("MASKED_JENSEN_SHANNON", "MASKED_COSINE", "MASKED_WEIGHTED_L1")
    assert all(k in cr.silhouette_scores_by_k or str(k) in cr.silhouette_scores_by_k for k in cr.candidate_k_evaluated)

    qa = json.loads((clust_dir / "agent_05_qa_report.json").read_text(encoding="utf-8"))
    assert qa["all_qa_checks_passed"] is True
    assert qa["summary"]["participants"] == 11
    assert qa["summary"]["primary_questions"] == 13
    assert qa["summary"]["contextual_questions"] == 1
    assert qa["summary"]["missingness_cells_preserved"] == 18

    pareto_assoc = json.loads((clust_dir / "cluster_pareto_associations.json").read_text(encoding="utf-8"))
    ni = pareto_assoc["non_interference_verified"]
    assert ni["feasible_solutions_count"] == 543
    assert ni["robust_core_count"] == 10
    assert ni["high_confidence_frontier_count"] == 102
    assert ni["clusters_modified_feasible_set"] is False
    assert ni["clusters_modified_pareto_membership"] is False
    assert ni["clusters_modified_voting_weights_or_rights"] is False

    # Verify zero forbidden psychological tokens in output descriptive labels
    labels_text = json.dumps(cr.descriptive_labels_en).lower()
    for tok in FORBIDDEN_PSYCH_TOKENS:
        assert tok not in labels_text

    # Verify descriptor SHA-256 parity
    desc_idx = json.loads(desc_path.read_text(encoding="utf-8"))
    for aid, meta in desc_idx["descriptors"].items():
        fpath = REPO_ROOT / meta["path"]
        assert fpath.is_file(), f"Descriptor artifact missing: {meta['path']}"
        assert compute_sha256(fpath) == meta["sha256"], f"SHA-256 mismatch for {aid}"
