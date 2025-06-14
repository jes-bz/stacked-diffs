from stacked_diffs.utils import git
from stacked_diffs.utils.classes import Graph, PruneArgs
from stacked_diffs.utils.metadata import MetadataManager


def handle_prune(args: PruneArgs) -> None:
    """
    Handle the 'prune' command.

    Cleans up the workspace by removing branches from metadata that no longer
    exist locally in Git. Git is the source of truth - if a branch doesn't
    exist locally, we remove it from our tracking.

    Parameters
    ----------
    args : PruneArgs
        The parsed command-line arguments as a dataclass.

    """
    mm = MetadataManager()
    graph: Graph = mm.load_graph()

    print("Checking for branches to prune...")

    tracked_branches: set[str] = set(graph.branches.keys())
    local_branches: set[str] = git.get_local_branches()

    # Find branches that are tracked in metadata but no longer exist locally
    branches_to_remove: set[str] = tracked_branches - local_branches

    if not branches_to_remove:
        print("✅ No branches to prune.")
        return

    print(f"Found {len(branches_to_remove)} branches to remove from metadata:")
    for branch in branches_to_remove:
        print(f" - '{branch}' (no longer exists locally)")

    # Remove branches from metadata
    for branch in branches_to_remove:
        graph.branches.pop(branch, None)

    # Clean up parent-child relationships
    for parent in graph.branches:
        graph.branches[parent].children = [
            child for child in graph.branches[parent].children if child not in branches_to_remove
        ]

    mm.save_graph(graph)
    print("✅ Prune complete.")
