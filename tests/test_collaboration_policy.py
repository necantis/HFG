"""
Tests for Git Collaboration, Shared-File Ownership, Artifact Handoff, and Notebook Inventory.
"""

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_agents_md_collaboration_and_shared_file_policy():
    agents_md = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    # Parallel agent Git rules
    for phrase in [
        "work in isolated Git worktrees, clones, or remote workspaces",
        "use a dedicated task branch",
        "never switch branches in a filesystem shared with another active agent",
        "never push directly to `main`",
        "never force-push",
        "never commit credentials, identity mappings, raw participant data, model weights, caches, or large runtime artifacts",
        "agent/01-ingestion-refinement",
        "agent/02-qualitative-refinement",
        "agent/07-runtime",
        "agent/10-collaboration-policy",
        "integration/wave-2a",
        "Do not bypass branch protection",
    ]:
        assert phrase in agents_md, f"Missing policy phrase in AGENTS.md: {phrase}"

    # Shared-file non-concurrent edit list & change request protocol
    for shared_ref in [
        "runs/<run_id>/manifest.json",
        "docs/PROJECT_STATE.md",
        "src/context_pack.py",
        "docs/AGENT_CONTEXT/agent_XX_context.md",
        "src/contracts.py",
        "pyproject.toml",
        "docs/AGENT_HANDOFFS/agent_XX_handoff.md",
        "Do not create a second incompatible contract to avoid coordination.",
    ]:
        assert shared_ref in agents_md, f"Missing shared-file rule in AGENTS.md: {shared_ref}"

    # Artifact handoff & evidentiary distinctions
    for distinction in [
        "Only the integration process publishes canonical production artifact registrations",
        "A **planned artifact** is not a **completed artifact**.",
        "A **CPU-only runtime test** is not a **validated GPU benchmark**.",
        "A **passing fixture test** is not a **completed survey analysis**.",
    ]:
        assert distinction in agents_md, f"Missing artifact handoff rule in AGENTS.md: {distinction}"


def test_adr_0007_exists_and_approved():
    adr_path = REPO_ROOT / "docs" / "DECISIONS" / "ADR-0007-git-collaboration-shared-file-ownership-and-artifact-handoff.md"
    assert adr_path.is_file(), "ADR-0007 collaboration ADR must exist"
    content = adr_path.read_text(encoding="utf-8")
    assert "- **Decision ID**: `ADR-0007`" in content
    assert "- **Status**: `APPROVED`" in content


def test_notebook_index_matches_tracked_ipynb_files():
    index_path = REPO_ROOT / "docs" / "NOTEBOOK_INDEX.md"
    assert index_path.is_file(), "docs/NOTEBOOK_INDEX.md must exist"
    content = index_path.read_text(encoding="utf-8")

    # Verify actual tracked .ipynb files in Git match what NOTEBOOK_INDEX reports
    res = subprocess.run(
        ["git", "ls-files", "*.ipynb"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    tracked_notebooks = [line.strip() for line in res.stdout.splitlines() if line.strip()]
    if not tracked_notebooks:
        assert "0` tracked `.ipynb` files" in content
    else:
        for nb in tracked_notebooks:
            assert nb in content

    assert "Flagged Duplicate / Ambiguous Production Entry Points for Agent 11 to Resolve" in content
    for col in ["Owner", "Purpose", "Status", "GPU Required", "Prerequisites"]:
        assert col in content


def test_generated_context_packs_include_collaboration_section():
    for i in range(12):
        pack_path = REPO_ROOT / "docs" / "AGENT_CONTEXT" / f"agent_{i:02d}_context.md"
        assert pack_path.is_file()
        content = pack_path.read_text(encoding="utf-8")
        assert "ADR-0007" in content
        assert "## 9. Git Collaboration, Shared-File Ownership & Artifact Handoff" in content
