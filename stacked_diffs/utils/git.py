import os
import subprocess
import sys
from pathlib import Path

from stacked_diffs.utils.classes import Graph
from stacked_diffs.utils.util import run_command

GIT_EXECUTABLE = os.environ.get("SD_GIT_EXECUTABLE", "git")


def get_git_root() -> Path:
    """Finds the root of the git repository."""
    path = run_command([GIT_EXECUTABLE, "rev-parse", "--show-toplevel"])
    return Path(path)


def get_current_branch() -> str:
    """Gets the current active branch name."""
    return run_command([GIT_EXECUTABLE, "rev-parse", "--abbrev-ref", "HEAD"])


def create_branch(branch_name: str, base_branch: str) -> None:
    """Creates a new branch based on a base branch."""
    run_command([GIT_EXECUTABLE, "checkout", "-b", branch_name, base_branch])


def find_parent(branch_name: str, graph: Graph) -> str | None:
    """Finds the parent of a given branch in the metadata graph."""
    for parent, meta in graph.branches.items():
        if branch_name in meta.children:
            return parent
    return None


def get_local_branches() -> set[str]:
    """Returns a set of all local branch names."""
    output = run_command([GIT_EXECUTABLE, "branch"])
    return {line.strip().replace("* ", "") for line in output.splitlines()}


def get_merged_branches(trunk_branch: str) -> set[str]:
    """Returns a set of all local branches that are merged into the trunk."""
    # Ensure our remote refs are up to date
    run_command([GIT_EXECUTABLE, "fetch", "origin"])
    # Ensure our local trunk is up to date
    run_command([GIT_EXECUTABLE, "checkout", trunk_branch])
    run_command([GIT_EXECUTABLE, "reset", "--hard", f"origin/{trunk_branch}"])

    output = run_command([GIT_EXECUTABLE, "branch", "--merged", trunk_branch])
    return {line.strip().replace("* ", "") for line in output.splitlines()}


def delete_local_branches(branches: list[str]) -> None:
    """
    Safely deletes a list of local Git branches.

    Uses 'git branch -d' which fails if a branch is not fully merged
    or if it's the current branch.
    """
    if not branches:
        return

    current_branch = get_current_branch()
    deleted_branches = []
    skipped_branches = []

    for branch_to_delete in branches:
        if branch_to_delete == current_branch:
            print(f"Skipping deletion of current branch: '{branch_to_delete}'.")
            skipped_branches.append(branch_to_delete)
            continue
        try:
            run_command([GIT_EXECUTABLE, "branch", "-d", branch_to_delete])
            deleted_branches.append(branch_to_delete)
        except subprocess.CalledProcessError as e:
            print(
                f"Failed to delete branch '{branch_to_delete}': {e.stderr.strip()}",
                file=sys.stderr,
            )
            skipped_branches.append(branch_to_delete)

    if deleted_branches:
        print(f"Deleted local branches: {', '.join(deleted_branches)}")
    if skipped_branches:
        print(f"Skipped or failed to delete: {', '.join(skipped_branches)}")


def find_stack_root(branch_name: str, graph: Graph) -> str:
    """
    Finds the root of the stack for the given branch.
    The root is the branch in the stack that is parented by the trunk,
    or the branch itself if it has no parent in the graph or is the trunk.
    """
    trunk = graph.trunk
    if branch_name == trunk or branch_name not in graph.branches:
        return branch_name

    current_branch_in_stack = branch_name
    while True:
        parent = find_parent(current_branch_in_stack, graph)
        if parent is None or parent == trunk:
            return current_branch_in_stack
        # Parent is another stacked branch, continue traversing up
        current_branch_in_stack = parent


def check_git_repo() -> bool:
    """Checks if the current directory is a Git repository.
    Raises a RuntimeError if not in a Git repository.
    """
    try:
        subprocess.run(
            [GIT_EXECUTABLE, "rev-parse", "--is-inside-work-tree"],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def check_git_state() -> None:
    """Check if git is in a clean state (no active rebase, merge, etc.).
    Raises SystemExit if git is in an unclean state.
    """
    git_dir = get_git_root() / ".git"

    # Check for active rebase
    if (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists():
        print("Error: Git is currently in the middle of a rebase operation.", file=sys.stderr)
        print("Please complete or abort the rebase before running sd commands.", file=sys.stderr)
        sys.exit(1)

    # Check for active merge
    if (git_dir / "MERGE_HEAD").exists():
        print("Error: Git is currently in the middle of a merge operation.", file=sys.stderr)
        print("Please complete or abort the merge before running sd commands.", file=sys.stderr)
        sys.exit(1)

    # Check for active cherry-pick
    if (git_dir / "CHERRY_PICK_HEAD").exists():
        print("Error: Git is currently in the middle of a cherry-pick operation.", file=sys.stderr)
        print("Please complete or abort the cherry-pick before running sd commands.", file=sys.stderr)
        sys.exit(1)

    # Check for active revert
    if (git_dir / "REVERT_HEAD").exists():
        print("Error: Git is currently in the middle of a revert operation.", file=sys.stderr)
        print("Please complete or abort the revert before running sd commands.", file=sys.stderr)
        sys.exit(1)
