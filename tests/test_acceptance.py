"""
Acceptance Test — Stateless Agent Bootstrap Verification.

Demonstrates that an agent with NO conversational history can read:
1. AGENTS.md
2. Its generated context pack (docs/AGENT_CONTEXT/agent_XX_context.md)

and correctly determine:
- what it owns;
- what it must not edit;
- authoritative upstream artifacts;
- required interfaces;
- tests to run;
- expected handoff.
"""

import re
from pathlib import Path
import pytest


class StatelessAgentBootstrapSimulator:
    """Simulates an autonomous agent booting with zero prior conversational history."""

    def __init__(self, agent_id: str, repo_root: Path):
        self.agent_id = agent_id.lower()
        self.repo_root = repo_root
        self.agents_md_path = repo_root / "AGENTS.md"
        self.context_pack_path = repo_root / "docs" / "AGENT_CONTEXT" / f"{self.agent_id}_context.md"

        assert self.agents_md_path.is_file(), f"AGENTS.md must exist at {self.agents_md_path}"
        assert self.context_pack_path.is_file(), f"Context pack must exist at {self.context_pack_path}"

        self.agents_content = self.agents_md_path.read_text(encoding="utf-8")
        self.context_content = self.context_pack_path.read_text(encoding="utf-8")

    def determine_ownership(self) -> dict:
        """Extract owned files and notebook."""
        owned_section = re.search(
            r"### Files You Own \(Authorized to Create & Modify\)\n(.*?)\n###",
            self.context_content,
            re.DOTALL,
        )
        assert owned_section is not None, "Context pack must contain 'Files You Own' section"

        lines = [line.strip().lstrip("- `").rstrip("`") for line in owned_section.group(1).splitlines() if line.strip()]
        owned_notebooks = [l for l in lines if l.endswith(".ipynb")]
        owned_paths = [l for l in lines if not l.endswith(".ipynb")]

        return {
            "owned_paths": owned_paths,
            "owned_notebook": owned_notebooks[0] if owned_notebooks else None,
        }

    def determine_forbidden_files(self) -> list[str]:
        """Extract forbidden files that the agent must NOT edit."""
        forbidden_section = re.search(
            r"### Files You Must NOT Edit \(Ownership Violations\)\n(.*?)\n---",
            self.context_content,
            re.DOTALL,
        )
        assert forbidden_section is not None, "Context pack must contain 'Files You Must NOT Edit' section"

        forbidden = []
        for line in forbidden_section.group(1).splitlines():
            line = line.strip()
            if line.startswith("- ❌ `"):
                clean = line.replace("- ❌ `", "").split("`")[0]
                forbidden.append(clean)
        return forbidden

    def determine_upstream_artifacts(self) -> list[str]:
        """Extract authoritative upstream artifacts."""
        upstream_section = re.search(
            r"### Upstream Dependencies\n(.*?)\n###",
            self.context_content,
            re.DOTALL,
        )
        assert upstream_section is not None, "Context pack must contain 'Upstream Dependencies' section"

        lines = [line.strip().lstrip("- `").rstrip("`") for line in upstream_section.group(1).splitlines() if line.strip()]
        return lines

    def determine_required_interfaces(self) -> dict:
        """Extract input and output interfaces."""
        in_match = re.search(r"### Input Interfaces \(Upstream Contracts\)\n(.*?)\n###", self.context_content, re.DOTALL)
        out_match = re.search(r"### Output Interfaces \(Deliverables\)\n(.*?)\n---", self.context_content, re.DOTALL)

        assert in_match is not None, "Context pack must specify Input Interfaces"
        assert out_match is not None, "Context pack must specify Output Interfaces"

        in_interfaces = [l.strip().lstrip("- `").rstrip("`") for l in in_match.group(1).splitlines() if l.strip()]
        out_interfaces = [l.strip().lstrip("- `").rstrip("`") for l in out_match.group(1).splitlines() if l.strip()]

        return {"inputs": in_interfaces, "outputs": out_interfaces}

    def determine_tests_to_run(self) -> list[str]:
        """Extract test commands required for this agent."""
        test_match = re.search(r"### Test Commands to Run\n```bash\n(.*?)\n```", self.context_content, re.DOTALL)
        assert test_match is not None, "Context pack must specify Test Commands to Run"

        commands = [cmd.strip() for cmd in test_match.group(1).splitlines() if cmd.strip() and not cmd.startswith("source")]
        return commands

    def determine_expected_handoff(self) -> str:
        """Extract expected handoff path."""
        handoff_match = re.search(r"`(docs/AGENT_HANDOFFS/agent_\d{2}_handoff\.md)`", self.context_content)
        assert handoff_match is not None, "Context pack must specify target handoff path"
        return handoff_match.group(1)


@pytest.mark.parametrize("agent_id,expected_module,expected_notebook,expected_contract", [
    ("agent_00", "src/architecture/", "notebooks/00_architecture_exploration.ipynb", "ARCHITECTURE.md"),
    ("agent_01", "src/ingest/", "notebooks/01_ingest_exploration.ipynb", "survey_raw_v1"),
    ("agent_04", "src/preference/", "notebooks/04_preference_utility_pareto.ipynb", "candidate_options_v1"),
    ("agent_09", "src/review/", "notebooks/09_integration_review.ipynb", "manifest.json"),
    ("agent_10", "src/artifact_registry.py", "notebooks/10_memory_and_registry.ipynb", "manifest.json"),
    ("agent_11", "src/pipeline/", "notebooks/11_orchestration_qa.ipynb", "PIPELINE.md"),
])
def test_stateless_agent_bootstrap_acceptance(agent_id, expected_module, expected_notebook, expected_contract):
    """
    Acceptance test verifying any stateless agent can independently discern:
    1. what it owns
    2. what it must not edit
    3. authoritative upstream artifacts
    4. required interfaces
    5. tests to run
    6. expected handoff
    """
    repo_root = Path(__file__).resolve().parent.parent
    agent = StatelessAgentBootstrapSimulator(agent_id, repo_root)

    # 1. Determine what it owns
    ownership = agent.determine_ownership()
    assert any(expected_module in path for path in ownership["owned_paths"]), f"Failed to identify ownership of {expected_module}"
    assert ownership["owned_notebook"] == expected_notebook, f"Failed to identify notebook {expected_notebook}"

    # 2. Determine what it must not edit
    forbidden = agent.determine_forbidden_files()
    assert len(forbidden) > 0, "Failed to identify forbidden files"
    if agent_id != "agent_01":
        assert any("src/ingest/" in f or "data/raw/" in f for f in forbidden)

    # 3. Determine authoritative upstream artifacts
    upstream = agent.determine_upstream_artifacts()
    # Agent 00 and 07 have empty upstream artifacts as roots, others have dependencies
    if agent_id not in ["agent_00", "agent_07"]:
        assert len(upstream) > 0, "Failed to identify upstream artifacts"

    # 4. Determine required interfaces
    interfaces = agent.determine_required_interfaces()
    assert any(expected_contract in str(inp) for inp in interfaces["inputs"] + upstream + interfaces["outputs"])
    assert len(interfaces["outputs"]) > 0

    # 5. Determine tests to run
    tests = agent.determine_tests_to_run()
    assert len(tests) > 0
    assert any("pytest" in t for t in tests)

    # 6. Determine expected handoff
    handoff_path = agent.determine_expected_handoff()
    assert handoff_path == f"docs/AGENT_HANDOFFS/{agent_id}_handoff.md"
