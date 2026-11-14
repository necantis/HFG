"""Agent 04: Preference Matrix, Feasibility Space, Utilities & Robust Pareto Analysis.

Owned by: Agent 04 — Preference, Utility & Pareto
Aligned with: Architecture v1.1.0, ADR-0005, ADR-0007, and ADR-0008.
"""

from src.preference.preference_matrix import (
    PreferenceMatrixBuilder,
    load_pareto_mc_config,
    load_preference_matrix,
)
from src.preference.solution_space import (
    SolutionSpaceBuilder,
    SolutionSpaceSummary,
)
from src.preference.utilities import (
    ParticipantUtilityEngine,
    UtilityEnsembleSummary,
)
from src.preference.pareto import (
    ParetoAnalyzer,
    nondominated_mask_skyline,
)
from src.preference.robust_pareto import (
    RobustParetoEngine,
)

__all__ = [
    "PreferenceMatrixBuilder",
    "load_pareto_mc_config",
    "load_preference_matrix",
    "SolutionSpaceBuilder",
    "SolutionSpaceSummary",
    "ParticipantUtilityEngine",
    "UtilityEnsembleSummary",
    "ParetoAnalyzer",
    "nondominated_mask_skyline",
    "RobustParetoEngine",
]
