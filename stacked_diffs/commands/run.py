import subprocess
import sys
from collections import deque

from stacked_diffs.utils import git
from stacked_diffs.utils.classes import Alias, Graph, PlanAction, ResumeState, RunArgs
from stacked_diffs.utils.metadata import MetadataManager
from stacked_diffs.utils.util import run_command, run_shell_command


def handle_run(
    args: RunArgs,
    alias_def: Alias | None = None,
) -> None:
    """
    Handle the 'run' command and its stateful execution.

    This is the single, core execution engine for all complex operations.
    It can be invoked directly or via an alias.

    Parameters
    ----------
    args : RunArgs
        The parsed command-line arguments as a dataclass.
    alias_def : Alias, optional
        The structured alias definition if the command was invoked
        as an alias.

    """
    mm = MetadataManager()
    graph: Graph = mm.load_graph()
    resume_state: ResumeState | None = mm.get_resume_state()

    # Determine environment variables
    # Get CLI-provided env vars from args if present (set in main.py for aliases)
    cli_env_vars = args.cli_env_vars
    # Start with alias defaults, then override with CLI-provided ones.
    env_vars: dict[str, str] = {}
    if alias_def and alias_def.env:
        env_vars.update(alias_def.env)
    if cli_env_vars:  # These are only for new runs, not continue/abort
        env_vars.update(cli_env_vars)

    cmd_config = alias_def.command if alias_def else vars(args)
    user_command = cmd_config.run if alias_def else args.command_string
    pre_flight_cmd = cmd_config.pre_flight if alias_def else args.pre_flight_cmd
    post_flight_cmd = cmd_config.post_flight if alias_def else args.post_flight_cmd

    # --- Continue/Abort Logic ---
    if args.continue_run or args.abort_run:
        # Validate that env vars are not provided with continue/abort
        if cli_env_vars:
            print("Error: Environment variables cannot be provided with --continue or --abort.", file=sys.stderr)
            sys.exit(1)

        if not resume_state:
            print("Error: No operation found to resume or abort.", file=sys.stderr)
            sys.exit(1)
        _handle_continue_abort(args=args, mm=mm, graph=graph, resume_state=resume_state)
    # --- Start New Run ---
    else:
        if resume_state:
            print(
                f"Error: A previous '{resume_state.alias_name}' operation was interrupted. Use --continue or --abort.",
                file=sys.stderr,
            )
            sys.exit(1)
        _handle_new_run(
            args=args,
            alias_def=alias_def,
            mm=mm,
            graph=graph,
            env_vars=env_vars,
            user_command=user_command,
            pre_flight_cmd=pre_flight_cmd,
            post_flight_cmd=post_flight_cmd,
        )


def _handle_continue_abort(
    *,
    args: RunArgs,
    mm: MetadataManager,
    graph: Graph,
    resume_state: ResumeState,
) -> None:
    """Handle the continue or abort logic for a paused operation."""
    original_alias_name = resume_state.alias_name
    original_alias_def = mm.get_all_aliases().get(original_alias_name)

    # Load saved environment variables for the resumed operation
    saved_env_vars = resume_state.env_vars

    remediation_cmd: str
    if args.continue_run:
        action_str = "Continuing"
        if isinstance(args.continue_run, str):  # User provided remediation command
            remediation_cmd = args.continue_run
        else:  # Use alias default or "true"
            remediation_cmd = (
                original_alias_def.continue_cmd if original_alias_def and original_alias_def.continue_cmd else "true"
            )
    else:  # args.abort_run
        action_str = "Aborting"
        if isinstance(args.abort_run, str):  # User provided remediation command
            remediation_cmd = args.abort_run
        else:  # Use alias default or "true"
            remediation_cmd = (
                original_alias_def.abort_cmd if original_alias_def and original_alias_def.abort_cmd else "true"
            )

    print(f"{action_str} '{original_alias_name or 'run'}' operation...")

    remediation_shell_env = {"SD_CURRENT_BRANCH": git.get_current_branch()}
    remediation_shell_env.update(saved_env_vars)  # Make $REMOTE etc. available
    remediation_success = run_shell_command(remediation_cmd, env_vars=remediation_shell_env)

    if args.continue_run:
        if not remediation_success:
            print(
                f"Remediation command ('{remediation_cmd}') failed. Operation remains paused.",
                file=sys.stderr,
            )
            # Re-save state just in case, though it shouldn't have changed
            mm.save_resume_state(resume_state)
            sys.exit(1)
        start_branch = resume_state.start_branch
        _process_plan(
            plan=resume_state.plan,
            user_command=resume_state.user_command,
            mm=mm,
            graph=graph,
            start_branch=start_branch,
            alias_name=original_alias_name,
            custom_env_vars=saved_env_vars,  # Pass saved env vars
            post_flight_cmd=resume_state.post_flight_cmd,
        )

    # Post-flight for continue/abort
    resumed_post_flight_cmd = resume_state.post_flight_cmd
    original_operation_name_for_msg = original_alias_name or "run"

    if resumed_post_flight_cmd:
        _run_post_flight(
            start_branch=resume_state.start_branch,
            post_flight_cmd=resumed_post_flight_cmd,
            trunk=graph.trunk,
            env_vars=saved_env_vars,  # Pass env vars for post_flight
        )
    _perform_cleanup(
        start_branch=resume_state.start_branch,
        mm=mm,
        operation_name=original_operation_name_for_msg,
        action_str=action_str,
    )


def _handle_new_run(
    *,
    args: RunArgs,
    alias_def: Alias | None,
    mm: MetadataManager,
    graph: Graph,
    env_vars: dict[str, str],
    user_command: str,
    pre_flight_cmd: str | None,
    post_flight_cmd: str | None,
) -> None:
    """Handle the logic for starting a new run operation."""
    start_branch = git.get_current_branch()

    if pre_flight_cmd:
        _run_pre_flight(
            pre_flight_cmd=pre_flight_cmd,
            trunk=graph.trunk,
            start_branch=start_branch,
            env_vars=env_vars,
        )

    print(f"Starting '{args.command_name or 'run'}' on '{start_branch}'...")

    cmd_config = alias_def.command if alias_def else vars(args)
    descendants_only = cmd_config.descendants_only if alias_def else False
    start_from_root = cmd_config.start_from_root if alias_def else False

    plan_start_branch = start_branch
    if start_from_root:
        plan_start_branch = git.find_stack_root(start_branch, graph) if start_branch in graph.branches else start_branch
        print(f"Stack root identified as '{plan_start_branch}'. Building plan...")

    plan = _build_traversal_plan(
        start_branch=plan_start_branch,
        graph=graph,
        descendants_only=descendants_only,
    )

    if not plan:
        print("✅ No branches to process.")
        if post_flight_cmd:
            _run_post_flight(
                start_branch=start_branch,
                post_flight_cmd=post_flight_cmd,
                trunk=graph.trunk,
                env_vars=env_vars,
            )
            _perform_cleanup(start_branch=start_branch, mm=mm, operation_name=args.command_name.capitalize())
        # No specific cleanup needed here if no plan and no post_flight, as no state was set.
        return

    mm.save_graph(graph)

    _process_plan(
        plan=plan,
        user_command=user_command,
        mm=mm,
        graph=graph,
        start_branch=start_branch,
        alias_name=args.command_name,
        custom_env_vars=env_vars,
        post_flight_cmd=post_flight_cmd,
    )

    if post_flight_cmd:
        _run_post_flight(
            start_branch=start_branch,
            post_flight_cmd=post_flight_cmd,
            trunk=graph.trunk,
            env_vars=env_vars,
        )
    _perform_cleanup(start_branch=start_branch, mm=mm, operation_name=args.command_name.capitalize())


def _process_plan(
    *,
    plan: list[PlanAction],
    user_command: str,
    mm: MetadataManager,
    graph: Graph,
    start_branch: str,
    alias_name: str = "run",
    custom_env_vars: dict[str, str] | None = None,
    post_flight_cmd: str | None = None,
) -> None:
    """Executes a plan of commands, handling interruptions."""
    action_queue: deque[PlanAction] = deque(plan)
    custom_env_vars = custom_env_vars or {}

    while action_queue:
        action: PlanAction = action_queue.popleft()

        resume_state = ResumeState(
            operation="run",
            start_branch=start_branch,
            user_command=user_command,
            plan=list(action_queue),
            alias_name=alias_name,
            env_vars=custom_env_vars,
            post_flight_cmd=post_flight_cmd,
        )

        env_vars: dict[str, str] = {
            "SD_CURRENT_BRANCH": action.branch,
            "SD_PARENT_BRANCH": action.parent,
            "SD_TRUNK_BRANCH": graph.trunk,
        }
        env_vars.update(custom_env_vars)

        run_command([git.GIT_EXECUTABLE, "checkout", action.branch])

        success: bool = run_shell_command(user_command, env_vars=env_vars)

        if not success:
            message: str = f"Command failed on branch '{action.branch}'."
            print(f"\n✋ {message}", file=sys.stderr)
            mm.save_resume_state(resume_state)
            print("\nFix the issue and then run:", file=sys.stderr)
            print(f"\n  sd {alias_name} --continue\n", file=sys.stderr)
            print("To abort the run entirely, run:", file=sys.stderr)
            print(f"\n  sd {alias_name} --abort\n", file=sys.stderr)
            sys.exit(1)


def _run_pre_flight(
    *,
    pre_flight_cmd: str,
    trunk: str,
    start_branch: str,
    env_vars: dict[str, str] | None = None,
) -> None:
    """Execute a pre-flight command."""
    print("--- Running Pre-flight Command ---")
    shell_env = {
        "SD_TRUNK_BRANCH": trunk,
        "SD_START_BRANCH": start_branch,
    }
    if env_vars:
        shell_env.update(env_vars)
    success = run_shell_command(pre_flight_cmd, env_vars=shell_env, fail_on_error=False)
    print("---------------------------------")
    if not success:
        print("Error: Pre-flight command failed. Aborting operation.", file=sys.stderr)
        sys.exit(1)


def _run_post_flight(
    *,
    post_flight_cmd: str,
    trunk: str,
    start_branch: str,
    env_vars: dict[str, str] | None = None,
) -> None:
    """Execute a post-flight command."""
    print("--- Running Post-flight Command ---")
    shell_env = {
        "SD_TRUNK_BRANCH": trunk,
        "SD_START_BRANCH": start_branch,
    }
    if env_vars:
        shell_env.update(env_vars)
    success = run_shell_command(post_flight_cmd, env_vars=shell_env, fail_on_error=False)
    print("----------------------------------")
    if not success:
        print("Error: Post-flight command failed. Operation completed but cleanup may be incomplete.", file=sys.stderr)
        sys.exit(1)


def _perform_cleanup(
    *,
    start_branch: str,
    mm: MetadataManager,
    operation_name: str,
    action_str: str = "Operation",
) -> None:
    """Perform standard cleanup after a stateful operation."""
    try:
        if git.get_current_branch() != start_branch:
            print(f"Returning to '{start_branch}'...")
            run_command([git.GIT_EXECUTABLE, "checkout", start_branch])
    except subprocess.SubprocessError as e:
        print(
            f"Warning: Could not check out starting branch '{start_branch}': {e}",
            file=sys.stderr,
        )

    mm.clear_resume_state()  # Clears resume_state from file
    # Load fresh graph to remove markers
    graph_after_clear = mm.load_graph()
    mm.save_graph(graph_after_clear)
    print(f"✅ Success! {action_str} complete for '{operation_name}'.")


def _get_children_for_traversal(branch_name: str, graph: Graph) -> list[str]:
    """Helper to get children for traversal, handling trunk."""
    if branch_name == graph.trunk:
        # Children of trunk are the roots of all stacks
        return [b_name for b_name in graph.branches if git.find_parent(b_name, graph) is None]
    elif branch_name in graph.branches:
        return graph.branches[branch_name].children
    return []


def _build_traversal_plan(
    *,
    start_branch: str,
    graph: Graph,
    descendants_only: bool = False,
) -> list[PlanAction]:
    """Build a flat list of actions for a traversal."""
    plan: list[PlanAction] = []
    queue: deque[PlanAction] = deque()
    visited: set[str] = set()
    trunk = graph.trunk

    if not descendants_only:
        parent_of_start = git.find_parent(start_branch, graph) or trunk
        queue.append(PlanAction(branch=start_branch, parent=parent_of_start))
    else:  # descendants_only is True
        # This mode is for operations like 'update' where the start_branch itself is skipped.
        # We need to add its direct children to the queue.
        for child in _get_children_for_traversal(branch_name=start_branch, graph=graph):
            queue.append(PlanAction(branch=child, parent=start_branch))

    while queue:
        current_action = queue.popleft()
        current_branch_name = current_action.branch

        if current_branch_name in visited:
            continue
        visited.add(current_branch_name)
        plan.append(current_action)

        # Determine children for the next level of traversal
        children_to_visit = _get_children_for_traversal(branch_name=current_branch_name, graph=graph)

        for child_name in children_to_visit:
            if child_name not in visited:
                queue.append(PlanAction(branch=child_name, parent=current_branch_name))
    return plan
