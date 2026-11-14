"""Agent 05 — Missingness-Masked Clustering & Preference Heterogeneity Package.

Owned by: Agent 05
Schema Version: 1.0.0 (Aligned with ADR-0005, ADR-0007, and ADR-0008)
"""

from src.clustering.distances import (
    compute_masked_subtopic_distance_matrix,
    compute_question_aggregated_distance_matrix,
    compute_utility_distance_matrices,
    cosine_distance,
    jensen_shannon_distance,
    set_to_set_expected_distance,
    weighted_l1_distance,
)
from src.clustering.features import (
    PRIMARY_QUESTION_IDS,
    RepresentationBundle,
    VerifiedCanonicalInputs,
    build_representations,
    load_and_verify_canonical_inputs,
    load_clustering_config,
)
from src.clustering.methods import (
    compute_leave_one_out_stability,
    compute_partition_geometry,
    compute_permutation_null_silhouette,
    consensus_clustering_from_coassociation,
    hierarchical_clustering,
    pam_clustering,
    select_k_empirically,
)
from src.clustering.pipeline import run_agent_05_pipeline

__all__ = [
    "PRIMARY_QUESTION_IDS",
    "RepresentationBundle",
    "VerifiedCanonicalInputs",
    "build_representations",
    "compute_leave_one_out_stability",
    "compute_masked_subtopic_distance_matrix",
    "compute_partition_geometry",
    "compute_permutation_null_silhouette",
    "compute_question_aggregated_distance_matrix",
    "compute_utility_distance_matrices",
    "consensus_clustering_from_coassociation",
    "cosine_distance",
    "hierarchical_clustering",
    "jensen_shannon_distance",
    "load_and_verify_canonical_inputs",
    "load_clustering_config",
    "pam_clustering",
    "run_agent_05_pipeline",
    "select_k_empirically",
    "set_to_set_expected_distance",
    "weighted_l1_distance",
]
