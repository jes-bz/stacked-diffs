from pathlib import Path

from stacked_diffs.utils.metadata import MetadataManager
from tests.utils import (
    get_commit_hash,
    run_git_command,
    run_sd_command,
)


def test_prune_removes_dangling_metadata(git_repo: Path):
    """Verify `sd prune` removes branches from metadata if deleted locally."""
    run_sd_command(["add", "feature-dangling"])
    mm_before = MetadataManager()
    graph_before = mm_before.load_graph()
    assert "feature-dangling" in graph_before.branches

    run_git_command(["checkout", "main"])  # Ensure not on the branch to be deleted
    run_git_command(["branch", "-D", "feature-dangling"])
    assert "feature-dangling" not in run_git_command(["branch"]).stdout

    run_sd_command(["prune"])
    mm_after = MetadataManager()
    graph_after = mm_after.load_graph()
    assert "feature-dangling" not in graph_after.branches


def test_prune_keeps_existing_branches(git_repo: Path):
    """Verify `sd prune` keeps branches that still exist locally, even if merged."""
    run_sd_command(["add", "completed-feature"])
    run_git_command(["checkout", "main"])
    run_git_command(["merge", "--no-ff", "completed-feature", "-m", "Merge feature"])
    run_git_command(["push", "origin", "main"])

    run_sd_command(["prune"])
    mm = MetadataManager()
    graph_after = mm.load_graph()
    # Branch still exists locally, so it should remain in metadata
    assert "completed-feature" in graph_after.branches
    local_branches_raw = run_git_command(["branch"]).stdout
    assert "completed-feature" in local_branches_raw


def test_prune_no_branches_to_prune(git_repo: Path):
    """Verify `sd prune` does nothing when all tracked branches exist locally."""
    run_sd_command(["add", "feature-unmerged"])
    run_git_command(["checkout", "feature-unmerged"])
    (git_repo / "unmerged_file.txt").write_text("unmerged content")
    run_git_command(["add", "."])
    run_git_command(["commit", "-m", "Commit on feature-unmerged"])

    initial_branch_commit_hash = get_commit_hash("HEAD")
    mm_before = MetadataManager()
    graph_before = mm_before.load_graph()

    run_sd_command(["prune"])

    mm_after = MetadataManager()
    graph_after = mm_after.load_graph()

    assert graph_before == graph_after, "Metadata graph should not have changed."
    local_branches_raw = run_git_command(["branch"]).stdout
    assert "feature-unmerged" in local_branches_raw
    assert get_commit_hash("HEAD") == initial_branch_commit_hash, "Should be back on the initial branch."


def test_prune_updates_parent_child_relationships(git_repo: Path):
    """Verify `sd prune` cleans up parent-child relationships when removing dangling metadata."""
    # Setup a stack: main -> p1 -> c1
    run_sd_command(["add", "p1"])
    run_git_command(["checkout", "p1"])
    run_sd_command(["add", "c1"])

    # Verify the relationship exists
    mm_before = MetadataManager()
    graph_before = mm_before.load_graph()
    assert "c1" in graph_before.branches["p1"].children

    # Delete c1 locally but keep p1
    run_git_command(["checkout", "main"])
    run_git_command(["branch", "-D", "c1"])

    run_sd_command(["prune"])

    mm_after = MetadataManager()
    graph_after = mm_after.load_graph()

    # c1 should be removed from metadata
    assert "c1" not in graph_after.branches
    # p1 should still exist but with no children
    assert "p1" in graph_after.branches
    assert "c1" not in graph_after.branches["p1"].children
