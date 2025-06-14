from pathlib import Path

from stacked_diffs.utils import git
from stacked_diffs.utils.metadata import MetadataManager
from tests.utils import (
    get_commit_hash,
    run_git_command,
    run_sd_command,
)


def test_add_single_branch(git_repo: Path):
    """Verify that `sd add` creates a new branch and the correct metadata."""
    run_sd_command(["add", "feature-a"])
    assert get_commit_hash("HEAD") == get_commit_hash("feature-a")
    mm = MetadataManager()
    graph = mm.load_graph()
    assert "main" not in graph.branches
    assert "feature-a" in graph.branches
    assert git.find_parent("feature-a", graph) is None


def test_add_stack(git_repo: Path):
    """Verify that `sd add` correctly creates a linear stack of branches."""
    run_sd_command(["add", "feat-base"])
    run_sd_command(["add", "feat-service"])
    run_sd_command(["add", "feat-ui"])
    assert get_commit_hash("HEAD") == get_commit_hash("feat-ui")
    mm = MetadataManager()
    graph = mm.load_graph()
    assert graph.branches["feat-base"].children == ["feat-service"]
    assert graph.branches["feat-service"].children == ["feat-ui"]


def test_add_branch_from_mid_stack(git_repo: Path):
    """
    Verify 'sd add' when branching from a mid-stack branch.
    Initial stack: main -> A -> B
    Then checkout A and add C.
    Expected: main -> A, with A having children B and C.
    """
    # 1. Setup initial stack: main -> A -> B
    # A is created from main (current HEAD)
    run_sd_command(["add", "A"])
    # B is created from A (current HEAD)
    run_sd_command(["add", "B"])

    commit_hash_A = get_commit_hash("A")

    # 2. Checkout branch A
    run_git_command(["checkout", "A"])
    assert get_commit_hash("HEAD") == commit_hash_A

    # 3. Add new branch C from A
    run_sd_command(["add", "C"])

    # 4. Assertions
    # 4.1. HEAD is on C
    assert get_commit_hash("HEAD") == get_commit_hash("C")

    # 4.2. C is branched off A's commit
    assert get_commit_hash("C") == commit_hash_A

    # 4.3. Metadata verification
    mm = MetadataManager()
    graph = mm.load_graph()

    assert "A" in graph.branches
    assert "B" in graph.branches
    assert "C" in graph.branches
    assert set(graph.branches["A"].children) == {"B", "C"}
    assert git.find_parent("A", graph) is None
    assert git.find_parent("B", graph) == "A"
    assert git.find_parent("C", graph) == "A"
    assert not graph.branches["B"].children
    assert not graph.branches["C"].children
