import argparse
import sys

from stacked_diffs.commands.add import handle_add
from stacked_diffs.commands.alias import handle_alias
from stacked_diffs.commands.prune import handle_prune
from stacked_diffs.commands.run import handle_run
from stacked_diffs.commands.tree import handle_tree
from stacked_diffs.utils.classes import (
    AddArgs,
    Alias,
    AliasArgs,
    PruneArgs,
    RunArgs,
    TreeArgs,
)
from stacked_diffs.utils.default_aliases import DEFAULT_ALIASES
from stacked_diffs.utils.git import check_git_repo, check_git_state
from stacked_diffs.utils.metadata import MetadataManager

BUILT_IN_COMMANDS: list[str] = ["add", "run", "tree", "prune", "alias", "help"]


def _generate_aliases_help_string() -> str:
    """Generates a formatted string listing available aliases for help text."""
    if check_git_repo():
        mm = MetadataManager()
        user_aliases: dict[str, Alias] = mm.load_user_aliases()
    else:
        user_aliases = {}

    lines = []
    has_any_alias = False

    if DEFAULT_ALIASES:
        if not lines:
            lines.append("Available Aliases (run with 'sd <alias_name>'):")
        lines.append("  --- Built-in ---")
        for name, a_def in sorted(DEFAULT_ALIASES.items()):
            desc = a_def.description
            if not desc:
                desc = f"Runs: sd run {a_def.command.run or '...'}"
            lines.append(f"    {name:<18} {desc}")
        has_any_alias = True

    if user_aliases:
        if not lines:
            lines.append("Available Aliases (run with 'sd <alias_name>'):")
        lines.append("  --- User-defined (from .sd_aliases.json) ---")
        for name, alias_def in sorted(user_aliases.items()):
            desc = alias_def.description
            if not desc:
                desc = f"User alias: sd run {alias_def.command.run or '[No "run" command defined]'}"
            lines.append(f"    {name:<18} {desc}")
        has_any_alias = True

    return "\n" + "\n".join(lines) if has_any_alias else ""


def build_parser() -> argparse.ArgumentParser:
    """Builds and returns the main argument parser."""
    aliases_help_epilog = _generate_aliases_help_string()
    parser = argparse.ArgumentParser(
        prog="sd",
        description="A tool for managing stacked diffs.",
        epilog=aliases_help_epilog,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Sub-command help")

    parser_add = subparsers.add_parser("add", help="Create a new branch stacked on top of the current branch.")
    parser_add.add_argument("branch_name", help="The name of the new branch to create.")
    parser_add.set_defaults(func=handle_add, args_class=AddArgs)

    parser_run = subparsers.add_parser("run", help="Execute a shell command on the current branch and all descendants.")
    parser_run.add_argument("command_string", nargs="?", default=None, metavar="COMMAND")
    parser_run.add_argument(
        "--pre-flight",
        dest="pre_flight_cmd",
        help="A command to run before the plan starts.",
    )
    parser_run.add_argument(
        "--post-flight",
        dest="post_flight_cmd",
        help="A command to run after the plan completes.",
    )
    continue_group = parser_run.add_argument_group("continue/abort options")
    continue_group.add_argument(
        "--continue",
        nargs="?",
        const=True,
        dest="continue_run",
        help="Continue a paused run. Optionally provide a remediation command.",
    )
    continue_group.add_argument("--abort", nargs="?", const=True, dest="abort_run", help="Abort a paused run.")
    parser_run.set_defaults(func=handle_run, args_class=RunArgs)

    parser_tree = subparsers.add_parser("tree", help="Show all tracked branches in a tree structure.")
    parser_tree.set_defaults(func=handle_tree, args_class=TreeArgs)

    parser_prune = subparsers.add_parser("prune", help="Clean up fully merged branches from metadata and local repo.")
    parser_prune.set_defaults(func=handle_prune, args_class=PruneArgs)

    parser_alias = subparsers.add_parser(
        "alias",
        help="Manage command aliases (use 'sd alias -h' for more options).",
        add_help=False,  # Let handle_alias manage its own help
    )
    parser_alias.set_defaults(func=handle_alias, args_class=AliasArgs)

    return parser


def main() -> None:
    """The main entry point for the 'sd' CLI."""
    parser = build_parser()

    if not check_git_repo():
        print("Please run sd from a git repository.\n\n")
        parser.print_help(sys.stderr)
        sys.exit(1)

    # Check if git is in a clean state (no active rebase, merge, etc.)
    # But allow continue/abort operations during active git operations
    is_continue_abort = len(sys.argv) > 2 and (sys.argv[2] == "--continue" or sys.argv[2] == "--abort")
    if not is_continue_abort:
        check_git_state()

    mm = MetadataManager()
    all_aliases: dict[str, Alias] = mm.get_all_aliases()

    # --- Dynamic Alias Dispatch ---
    # Check for aliases, but protect built-in commands from being overridden
    if len(sys.argv) > 1 and sys.argv[1] not in BUILT_IN_COMMANDS and sys.argv[1] not in ["-h", "--help"]:
        command_name: str = sys.argv[1]
        if command_name in all_aliases:
            alias_def = all_aliases[command_name]

            cli_env_vars: dict[str, str] = {}
            is_continue_abort_flow = False
            raw_alias_args = sys.argv[2:]  # Arguments after the alias name

            # Determine if this is a continue/abort flow for the alias.
            # If so, CLI KEY=VALUE pairs are ignored; env vars come from saved state.
            for arg_check in raw_alias_args:
                if arg_check == "--continue" or arg_check == "--abort":
                    is_continue_abort_flow = True
                    break

            if not is_continue_abort_flow:
                for arg_val in raw_alias_args:
                    # Parse KEY=VALUE pairs, avoid flags like --option=value
                    if "=" in arg_val and not arg_val.startswith("--"):
                        key, value = arg_val.split("=", 1)
                        # Validate KEY=VALUE format
                        if not key.strip():
                            print(
                                f"Error: Invalid environment variable format '{arg_val}': key cannot be empty",
                                file=sys.stderr,
                            )
                            sys.exit(1)
                        if not value.strip():
                            print(
                                f"Error: Invalid environment variable format '{arg_val}': value cannot be empty",
                                file=sys.stderr,
                            )
                            sys.exit(1)
                        if not key.replace("_", "").replace("-", "").isalnum():
                            print(
                                f"Error: Invalid environment variable name '{key}': must contain only alphanumeric characters, underscores, and hyphens",
                                file=sys.stderr,
                            )
                            sys.exit(1)
                        cli_env_vars[key] = value
                    elif not arg_val.startswith("--") and not "=" in arg_val:
                        # Non-flag argument without = is invalid for aliases
                        print(
                            f"Error: Invalid argument '{arg_val}': alias arguments must be in KEY=VALUE format or start with --",
                            file=sys.stderr,
                        )
                        sys.exit(1)

            # Construct arguments for the 'run' sub-parser
            run_parser_feed_args = ["run"]
            cmd_config = alias_def.command

            # Add the main command string from alias def if not a continue/abort flow
            if cmd_config.run and not is_continue_abort_flow:
                run_parser_feed_args.append(cmd_config.run)

            # Add pre_flight and post_flight from alias_def
            if cmd_config.pre_flight:
                run_parser_feed_args.extend(["--pre-flight", cmd_config.pre_flight])
            if cmd_config.post_flight:
                run_parser_feed_args.extend(["--post-flight", cmd_config.post_flight])

            # Add --continue or --abort flags and their user-supplied optional values
            # These are passed from `sd alias_name [KEY=VAL...] --continue [remedy_cmd]`
            idx = 0
            while idx < len(raw_alias_args):
                arg = raw_alias_args[idx]
                if arg == "--continue" or arg == "--abort":
                    run_parser_feed_args.append(arg)
                    # Check for an optional value for --continue or --abort
                    if (
                        idx + 1 < len(raw_alias_args)
                        and not raw_alias_args[idx + 1].startswith("--")
                        and "=" not in raw_alias_args[idx + 1]
                    ):
                        run_parser_feed_args.append(raw_alias_args[idx + 1])
                        idx += 1  # Consume the value
                idx += 1

            args = parser.parse_args(run_parser_feed_args)

            run_args = RunArgs(
                command_string=args.command_string,
                pre_flight_cmd=args.pre_flight_cmd,
                post_flight_cmd=args.post_flight_cmd,
                continue_run=args.continue_run,
                abort_run=args.abort_run,
                cli_env_vars=cli_env_vars if not is_continue_abort_flow else None,
                command_name=command_name,
            )

            handle_run(run_args, alias_def=alias_def)
            return

    # --- Standard Command Parsing ---
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    # Handle help flags explicitly - but let argparse handle it naturally
    # The explicit handling was interfering with normal argparse behavior

    args, _ = parser.parse_known_args()

    if not hasattr(args, "func"):
        parser.error(f"unrecognized command: '{sys.argv[1]}'")

    if args.command == "run":
        if (args.continue_run or args.abort_run) and args.command_string:
            parser.error("Cannot provide a COMMAND when using --continue or --abort.")
        if not (args.continue_run or args.abort_run) and not args.command_string:
            parser.error("A COMMAND is required for a new run operation.")

    # Create dataclass instance based on the command
    args_class = getattr(args, "args_class", None)
    if args_class:
        # Handle the special case for alias command parsing
        if args.command == "alias":
            # handle_alias will parse its own arguments into the correct AliasArgs subclass
            # We just need to call it with the raw args for now.
            args.func(args)
        else:
            # Create dataclass instance, excluding 'func', 'command', and 'args_class'
            arg_dict = vars(args)
            # Remove keys that are not part of the dataclass
            dataclass_args_dict = {k: v for k, v in arg_dict.items() if k in args_class.__annotations__}

            # For RunArgs, add the command name
            if args_class == RunArgs:
                dataclass_args_dict["command_name"] = args.command

            args_instance = args_class(**dataclass_args_dict)

            # Pass the dataclass instance to the handler function
            args.func(args_instance)
    else:
        args.func(args)


if __name__ == "__main__":
    main()
