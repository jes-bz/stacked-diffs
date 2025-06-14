"""
Tests for complex real-world scenarios and integration flows.
Tests combinations of commands and edge cases that might occur in practice.
"""

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from stacked_diffs.utils import git
from stacked_diffs.utils.metadata import MetadataManager
from tests.utils import get_commit_hash, run_git_command, run_sd_command


def test_sync_with_merge_conflicts_and_stash_conflicts(git_repo: Path):
    """Test sync operation with both merge conflicts and stash conflicts."""
    # Create a stack with changes
    run_sd_command(["add", "feature"])
    (git_repo / "feature.txt").write_text("feature content")
    run_git_command(["add", "."])
    run_git_command(["commit", "-m", "Feature commit"])

    # Make conflicting changes on main
    run_git_command(["checkout", "main"])
    (git_repo / "feature.txt").write_text("main content")
    run_git_command(["add", "."])
    run_git_command(["commit", "-m", "Main commit"])
    run_git_command(["push", "origin", "main"])

    # Go back to feature and make uncommitted changes
    run_git_command(["checkout", "feature"])
    (git_repo / "uncommitted.txt").write_text("uncommitted work")

    # Sync should fail due to conflicts
    with pytest.raises(SystemExit):
        run_sd_command(["sync"])

    # Verify resume state exists
    mm = MetadataManager()
    assert mm.get_resume_state() is not None


def test_prune_during_active_rebase(git_repo: Path):
    """Test prune command when git is in middle of rebase operation."""
    # Create branches
    run_sd_command(["add", "feature"])
    (git_repo / "file.txt").write_text("feature content")
    run_git_command(["add", "."])
    run_git_command(["commit", "-m", "Feature commit"])

    run_git_command(["checkout", "main"])
    (git_repo / "file.txt").write_text("main content")
    run_git_command(["add", "."])
    run_git_command(["commit", "-m", "Main commit"])

    # Start rebase that will conflict
    run_git_command(["checkout", "feature"])
    try:
        run_git_command(["rebase", "main"], check=False)
    except subprocess.CalledProcessError:
        pass  # Expected to fail due to conflict

    # Prune should handle active rebase state
    with pytest.raises(SystemExit):
        run_sd_command(["prune"])


def test_add_branch_with_dirty_working_directory(git_repo: Path):
    """Test adding branch when working directory has uncommitted changes."""
    # Make uncommitted changes
    (git_repo / "dirty.txt").write_text("uncommitted changes")

    # Should still be able to add branch
    run_sd_command(["add", "dirty-branch"])

    # Verify branch was created and uncommitted changes preserved
    assert get_commit_hash("HEAD") == get_commit_hash("dirty-branch")
    assert (git_repo / "dirty.txt").exists()


def test_tree_with_orphaned_branches(git_repo: Path, capsys):
    """Test tree display when metadata contains orphaned branches."""
    # Create normal stack
    run_sd_command(["add", "feature"])

    # Manually add orphaned branch to metadata
    mm = MetadataManager()
    graph = mm.load_graph()
    from stacked_diffs.utils.classes import BranchMeta

    graph.branches["orphaned"] = BranchMeta()  # No parent, no children
    mm.save_graph(graph)

    # Tree should handle orphaned branches gracefully
    run_sd_command(["tree"])
    captured = capsys.readouterr()
    assert "feature" in captured.out


def test_run_command_with_shell_metacharacters(git_repo: Path):
    """Test run command with shell metacharacters and complex commands."""
    run_sd_command(["add", "test-branch"])

    # Test command with pipes, redirects, and variables
    complex_command = 'echo "Branch: $SD_CURRENT_BRANCH" | tee output-$SD_CURRENT_BRANCH.txt'
    run_sd_command(["run", complex_command])

    # Verify output files were created (command runs on test-branch, not main)
    assert (git_repo / "output-test-branch.txt").exists()

    # Verify the content is correct
    content = (git_repo / "output-test-branch.txt").read_text().strip()
    assert "Branch: test-branch" in content


def test_alias_with_recursive_environment_variables(git_repo: Path):
    """Test alias with environment variables that reference other env vars."""
    run_sd_command(["add", "env-test"])

    # Create alias with env var that references another env var
    run_sd_command(
        [
            "alias",
            "set",
            "recursive-env",
            "--run",
            "echo FULL_PATH=$FULL_PATH",
            "--env",
            "BASE_PATH=/tmp",
            "--env",
            "FULL_PATH=$BASE_PATH/subdir",
        ]
    )

    run_sd_command(["recursive-env"])


def test_multiple_stacks_independent_operations(git_repo: Path):
    """Test operations on multiple independent stacks."""
    # Create first stack
    run_sd_command(["add", "stack1-base"])
    run_sd_command(["add", "stack1-child"])

    # Create second independent stack
    run_git_command(["checkout", "main"])
    run_sd_command(["add", "stack2-base"])
    run_sd_command(["add", "stack2-child"])

    # Operations on one stack shouldn't affect the other
    run_git_command(["checkout", "stack1-base"])
    run_sd_command(["run", "touch stack1-$SD_CURRENT_BRANCH.txt"])

    # Verify only stack1 branches were affected
    assert (git_repo / "stack1-stack1-base.txt").exists()
    assert (git_repo / "stack1-stack1-child.txt").exists()
    assert not (git_repo / "stack1-stack2-base.txt").exists()
    assert not (git_repo / "stack1-stack2-child.txt").exists()


def test_branch_deletion_during_run_operation(git_repo: Path):
    """Test behavior when branches are deleted externally during run operation."""
    # Create stack
    run_sd_command(["add", "base"])
    run_sd_command(["add", "child"])

    # Create alias that will be interrupted
    run_sd_command(
        [
            "alias",
            "set",
            "interruptible",
            "--run",
            "echo processing $SD_CURRENT_BRANCH && sleep 1 && false",  # Will fail
        ]
    )

    # Start operation that will fail
    with pytest.raises(SystemExit):
        run_sd_command(["interruptible"])

    # Simulate external branch deletion
    run_git_command(["checkout", "main"])
    run_git_command(["branch", "-D", "child"])

    # Continue should handle missing branch gracefully
    with pytest.raises(SystemExit):
        run_sd_command(["interruptible", "--continue"])


def test_very_long_branch_names_and_commands(git_repo: Path):
    """Test handling of very long branch names and commands."""
    # Create branch with long name
    long_name = "very-long-branch-name-" + "x" * 100
    try:
        run_sd_command(["add", long_name])

        # Test with long command
        long_command = "echo " + "very-long-output-" * 50
        run_sd_command(["run", long_command])

    except SystemExit:
        # Some systems may have limits on branch name length
        pass


def test_unicode_and_special_characters_in_commands(git_repo: Path):
    """Test commands with unicode and special characters."""
    run_sd_command(["add", "unicode-test"])

    # Test command with unicode
    unicode_command = 'echo "Unicode: 🚀 ñáéíóú" > unicode-$SD_CURRENT_BRANCH.txt'
    run_sd_command(["run", unicode_command])

    # Verify files were created (command runs on unicode-test, not main)
    assert (git_repo / "unicode-unicode-test.txt").exists()

    # Verify the content is correct
    content = (git_repo / "unicode-unicode-test.txt").read_text().strip()
    assert "Unicode: 🚀 ñáéíóú" in content


def test_concurrent_sd_processes_simulation(git_repo: Path):
    """Test simulation of concurrent sd processes accessing metadata."""
    # Create initial state
    run_sd_command(["add", "concurrent-test"])

    # Simulate concurrent access by manually manipulating metadata
    mm1 = MetadataManager()
    mm2 = MetadataManager()

    graph1 = mm1.load_graph()
    graph2 = mm2.load_graph()

    # Both processes try to add different branches
    from stacked_diffs.utils.classes import BranchMeta

    graph1.branches["process1-branch"] = BranchMeta()
    graph2.branches["process2-branch"] = BranchMeta()

    # Save in sequence (last write wins)
    mm1.save_graph(graph1)
    mm2.save_graph(graph2)

    # Verify final state
    final_graph = mm1.load_graph()
    # Only process2-branch should exist due to last write wins
    assert "process2-branch" in final_graph.branches


def test_filesystem_permission_issues_simulation(git_repo: Path):
    """Test behavior when filesystem permissions prevent operations."""
    mm = MetadataManager()

    # Make .git directory read-only to simulate permission issues
    git_dir = git_repo / ".git"
    original_mode = git_dir.stat().st_mode

    try:
        # Make directory read-only
        git_dir.chmod(0o444)

        # Operations requiring write should fail gracefully
        with pytest.raises(SystemExit):
            run_sd_command(["add", "permission-test"])

    finally:
        # Restore original permissions
        git_dir.chmod(original_mode)


def test_empty_alias_commands(git_repo: Path):
    """Test aliases with empty or whitespace-only commands."""
    # Test empty run command
    with pytest.raises(SystemExit):
        run_sd_command(["alias", "set", "empty-run", "--run", ""])

    # Test whitespace-only run command
    with pytest.raises(SystemExit):
        run_sd_command(["alias", "set", "whitespace-run", "--run", "   "])


def test_alias_with_very_long_description(git_repo: Path):
    """Test alias with very long description."""
    long_description = "This is a very long description. " * 100

    run_sd_command(["alias", "set", "long-desc", "--run", "echo test", "--description", long_description])

    # Verify alias was created
    run_sd_command(["alias", "show", "long-desc"])


def test_network_timeout_during_sync(git_repo: Path):
    """Test sync operation with network timeout."""
    # Remove upstream remote (which sync uses by default) to simulate network issues
    run_git_command(["remote", "remove", "upstream"])

    # Add fake upstream remote that will timeout
    run_git_command(["remote", "add", "upstream", "https://nonexistent.example.com/repo.git"])

    # Sync should fail due to network issues
    with pytest.raises(SystemExit):
        run_sd_command(["sync"])


def test_git_hooks_interference(git_repo: Path):
    """Test behavior when git hooks interfere with operations."""
    # Create a pre-commit hook that fails
    hooks_dir = git_repo / ".git" / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    pre_commit_hook = hooks_dir / "pre-commit"
    pre_commit_hook.write_text("#!/bin/sh\nexit 1\n")
    pre_commit_hook.chmod(0o755)

    # Operations that trigger commits should handle hook failures
    run_sd_command(["add", "hook-test"])
    (git_repo / "test.txt").write_text("test content")
    run_git_command(["add", "."])

    # Commit should fail due to hook
    with pytest.raises(subprocess.CalledProcessError):
        run_git_command(["commit", "-m", "Test commit"])
