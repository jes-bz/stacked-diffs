from stacked_diffs.utils.classes import Graph, TreeArgs
from stacked_diffs.utils.metadata import MetadataManager


def handle_tree(args: TreeArgs) -> None:
    """
    Handle the 'tree' command.

    Displays all tracked branches and their relationships in a clear,
    hierarchical tree structure, starting from the trunk.

    Parameters
    ----------
    args : TreeArgs
        The parsed command-line arguments as a dataclass.

    """
    mm = MetadataManager()
    graph: Graph = mm.load_graph()
    trunk: str = graph.trunk
    all_branches: set[str] = set(graph.branches.keys())
    all_children: set[str] = set()

    for branch_meta in graph.branches.values():
        for child in branch_meta.children:
            all_children.add(child)

    root_branches: list[str] = sorted(list(all_branches - all_children))

    if not root_branches:
        print(f"No stacks found to display. Your trunk branch is '{trunk}'.")
        return

    print(f"'{trunk}' (Trunk)")
    root_count: int = len(root_branches)
    for i, root in enumerate(root_branches):
        is_root_last: bool = i == root_count - 1
        print_branch_tree(branch=root, graph=graph, prefix="", is_last=is_root_last)


def print_branch_tree(
    *,
    branch: str,
    graph: Graph,
    prefix: str = "",
    is_last: bool = True,
) -> None:
    """Recursively print a branch and its descendants in a tree structure."""
    connector: str = "└── " if is_last else "├── "
    print(f"{prefix}{connector}{branch}")
    child_prefix: str = prefix + ("    " if is_last else "│   ")
    children: list[str] = graph.branches.get(branch, {}).children
    for i, child in enumerate(children):
        print_branch_tree(
            branch=child,
            graph=graph,
            prefix=child_prefix,
            is_last=(i == len(children) - 1),
        )
