from stacked_diffs.utils import git
from stacked_diffs.utils.classes import AddArgs, BranchMeta, Graph
from stacked_diffs.utils.metadata import MetadataManager


def handle_add(args: AddArgs) -> None:
    """
    Handle the 'add' command.

    Creates a new branch and stacks it on top of the currently checked-out
    branch by adding it as a child in the metadata graph.

    Parameters
    ----------
    args : AddArgs
        The parsed command-line arguments as a dataclass.
        Contains the `branch_name` attribute.

    """
    mm = MetadataManager()
    graph: Graph = mm.load_graph()
    parent_branch: str = git.get_current_branch()
    print(f"Current branch is '{parent_branch}'.")

    print(f"Creating new branch '{args.branch_name}' based on '{parent_branch}'...")
    git.create_branch(args.branch_name, base_branch=parent_branch)
    print("Branch created successfully.")

    if parent_branch != graph.trunk:
        if parent_branch not in graph.branches:
            graph.branches[parent_branch] = BranchMeta()
        graph.branches[parent_branch].children.append(args.branch_name)

    graph.branches[args.branch_name] = BranchMeta()

    mm.save_graph(graph)
    print(f"✅ Success! Stacked '{args.branch_name}' on top of '{parent_branch}'.")
