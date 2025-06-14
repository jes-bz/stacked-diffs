from pathlib import Path

import pytest

from stacked_diffs.utils.metadata import MetadataManager
from tests.utils import (
    get_commit_hash,
    get_parent_hash,
    run_git_command,
    run_sd_command,
)


def test_update_alias(git_repo: Path):
    """Verify the built-in `sd update` alias correctly rebases descendant branches."""
    run_sd_command(["add", "base"])
    (git_repo / "base.txt").write_text("base")
    run_git_command(["add", "."])
    run_git_command(["commit", "-m", "Commit on base"])
    run_sd_command(["add", "child"])
    (git_repo / "child.txt").write_text("child")
    run_git_command(["add", "."])
    run_git_command(["commit", "-m", "Commit on child"])
    original_child_parent_hash = get_parent_hash("child")

    run_git_command(["checkout", "base"])
    (git_repo / "new_file.txt").write_text("change")
    run_git_command(["add", "."])
    run_git_command(["commit", "--amend", "--no-edit"])
    new_base_hash = get_commit_hash("base")
    run_sd_command(["update"])
    new_child_parent_hash = get_parent_hash("child")
    assert new_child_parent_hash != original_child_parent_hash
    assert new_child_parent_hash == new_base_hash


def test_sync_alias_with_stash(git_repo: Path):
    """Verify the built-in `sd sync` alias rebases the whole stack and handles stashing."""
    run_sd_command(["add", "base"])
    (git_repo / "base.txt").write_text("base")
    run_git_command(["add", "."])
    run_git_command(["commit", "-m", "Commit for base"])
    original_base_parent_hash = get_parent_hash("base")

    run_sd_command(["add", "child"])
    (git_repo / "child.txt").write_text("child")
    run_git_command(["add", "."])
    run_git_command(["commit", "-m", "Commit on child"])

    run_git_command(["checkout", "main"])
    (git_repo / "upstream.txt").write_text("upstream change")
    run_git_command(["add", "."])
    run_git_command(["commit", "-m", "New work on main"])
    run_git_command(["push", "--force", "origin", "main"])
    new_main_hash = get_commit_hash("main")

    run_git_command(["checkout", "child"])
    (git_repo / "wip.txt").write_text("work in progress")
    run_sd_command(["sync"])

    assert get_commit_hash("HEAD") == get_commit_hash("child")
    assert (git_repo / "wip.txt").exists()

    new_base_parent_hash = get_parent_hash("base")
    assert new_base_parent_hash != original_base_parent_hash
    assert new_base_parent_hash == new_main_hash


def test_run_simple_command(git_repo: Path):
    """Verify `sd run` executes a command on the current branch and its descendants."""
    run_sd_command(["add", "base"])
    run_sd_command(["add", "service"])
    run_git_command(["checkout", "base"])
    run_sd_command(["run", "touch test-file-$SD_CURRENT_BRANCH"])

    assert not (git_repo / "test-file-main").exists()
    assert (git_repo / "test-file-base").exists()
    assert (git_repo / "test-file-service").exists()


def test_update_with_conflict_and_continue(git_repo: Path):
    """Verify the --continue flag works for an alias after a rebase conflict."""
    run_sd_command(["add", "base"])
    (git_repo / "file.txt").write_text("original base content")
    run_git_command(["add", "."])
    run_git_command(["commit", "-m", "Commit on base with file.txt"])
    run_sd_command(["add", "child"])
    (git_repo / "file.txt").write_text("child makes a change")
    run_git_command(["add", "."])
    run_git_command(["commit", "-m", "Child modifies file.txt"])

    run_git_command(["checkout", "base"])
    (git_repo / "file.txt").write_text("base amended content")
    run_git_command(["add", "."])
    run_git_command(["commit", "--amend", "--no-edit"])
    with pytest.raises(SystemExit) as e:
        run_sd_command(["update"])
    assert e.value.code != 0

    mm = MetadataManager()
    resume_state = mm.get_resume_state()
    assert resume_state is not None
    assert resume_state.alias_name == "update"

    # Resolve the first conflict by setting the file to the content
    # that the *next* commit to be applied by `git rebase --continue` expects.
    (git_repo / "file.txt").write_text("original base content")
    run_git_command(["add", "file.txt"])

    run_sd_command(["update", "--continue"])

    assert mm.get_resume_state() is None
    assert get_commit_hash("HEAD") == get_commit_hash("base")


def test_update_with_conflict_and_abort(git_repo: Path):
    """Verify the --abort flag works for an alias after a rebase conflict."""
    run_sd_command(["add", "base-abort"])
    (git_repo / "file.txt").write_text("original base content for abort")
    run_git_command(["add", "."])
    run_git_command(["commit", "-m", "Commit on base-abort"])
    base_abort_commit_hash = get_commit_hash("base-abort")

    run_sd_command(["add", "child-abort"])
    (git_repo / "file.txt").write_text("child-abort makes a change")
    run_git_command(["add", "."])
    run_git_command(["commit", "-m", "Child-abort modifies file.txt"])
    child_abort_original_commit_hash = get_commit_hash("child-abort")

    run_git_command(["checkout", "base-abort"])
    (git_repo / "file.txt").write_text("base-abort amended content")
    run_git_command(["add", "."])
    run_git_command(["commit", "--amend", "--no-edit"])
    base_abort_new_commit_hash = get_commit_hash("base-abort")

    with pytest.raises(SystemExit) as e:
        run_sd_command(["update"])  # This is run while on base-abort
    assert e.value.code != 0

    mm = MetadataManager()
    resume_state = mm.get_resume_state()
    assert resume_state is not None
    assert resume_state.alias_name == "update"

    run_sd_command(["update", "--abort"])

    assert mm.get_resume_state() is None
    assert get_commit_hash("HEAD") == get_commit_hash("base-abort")  # Should return to start_branch of 'update'
    assert get_commit_hash("base-abort") == base_abort_new_commit_hash  # base-abort remains amended

    # child-abort should be reset to its original state before the rebase attempt
    run_git_command(["checkout", "child-abort"])
    assert get_commit_hash("HEAD") == child_abort_original_commit_hash
    assert (git_repo / "file.txt").read_text() == "child-abort makes a change"
    assert get_parent_hash("child-abort") == base_abort_commit_hash  # Parent is original base


def test_run_with_pre_post_flight(git_repo: Path):
    """Verify `sd run` with --pre-flight and --post-flight arguments."""
    run_sd_command(["add", "feature-run"])
    run_git_command(["checkout", "main"])  # Start from main

    run_sd_command(
        [
            "run",
            "--pre-flight",
            "touch pre-flight-hook.txt",
            "--post-flight",
            "touch post-flight-hook.txt",
            "touch run-file-$SD_CURRENT_BRANCH.txt",
        ]
    )

    assert (git_repo / "pre-flight-hook.txt").exists()
    assert (git_repo / "run-file-main.txt").exists()
    assert (git_repo / "run-file-feature-run.txt").exists()
    assert (git_repo / "post-flight-hook.txt").exists()
    assert get_commit_hash("HEAD") == get_commit_hash("main")  # Should return to start branch


def test_run_with_custom_env_var(git_repo: Path):
    """Verify an alias using `sd run` correctly uses custom environment variables."""
    run_sd_command(["add", "env-test-base"])
    run_sd_command(["add", "env-test-child"])
    run_git_command(["checkout", "env-test-base"])

    # Create a temporary alias that uses the environment variable
    run_sd_command(["alias", "set", "test-env-alias", "--run", "echo $FILE_CONTENT > file-$SD_CURRENT_BRANCH.txt"])

    # Run the alias with a custom environment variable
    run_sd_command(["test-env-alias", "FILE_CONTENT=hello_world"])

    assert (git_repo / "file-env-test-base.txt").read_text().strip() == "hello_world"
    assert (git_repo / "file-env-test-child.txt").read_text().strip() == "hello_world"

    # Clean up the temporary alias
    run_sd_command(["alias", "rm", "test-env-alias"])


def test_sync_alias_with_custom_remote_env(git_repo: Path):
    """Verify `sd sync` alias correctly uses a custom REMOTE environment variable."""
    # Setup a stack
    run_sd_command(["add", "sync-env-base"])
    (git_repo / "sync-env-base.txt").write_text("base content")
    run_git_command(["add", "."])
    run_git_command(["commit", "-m", "Commit on sync-env-base"])

    run_sd_command(["add", "sync-env-child"])
    (git_repo / "sync-env-child.txt").write_text("child content")
    run_git_command(["add", "."])
    run_git_command(["commit", "-m", "Commit on sync-env-child"])

    # Make a change on main in the remote repo (which is also 'another_remote')
    run_git_command(["checkout", "main"])
    (git_repo / "remote_change.txt").write_text("change from remote")
    run_git_command(["add", "."])
    run_git_command(["commit", "-m", "Remote change on main"])
    run_git_command(["push", "--force", "another_remote", "main"])

    # Checkout child and run sync using the custom remote
    run_git_command(["checkout", "sync-env-child"])
    run_sd_command(["sync", "REMOTE=another_remote"])

    # Verify the stack was rebased onto the new main from 'another_remote'
    new_main_hash = get_commit_hash("main")
    new_base_parent_hash = get_parent_hash("sync-env-base")
    assert new_base_parent_hash == new_main_hash
    assert get_commit_hash("HEAD") == get_commit_hash("sync-env-child")  # Should return to start branch
