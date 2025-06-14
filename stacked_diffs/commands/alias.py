# --- Alias Management Logic ---------------------------------------------------


import argparse
import sys
from dataclasses import asdict

from stacked_diffs.utils.classes import (
    Alias,
    AliasArgs,
    AliasListArgs,
    AliasRmArgs,
    AliasSetArgs,
    AliasShowArgs,
    CommandConfig,
)
from stacked_diffs.utils.default_aliases import DEFAULT_ALIASES
from stacked_diffs.utils.metadata import MetadataManager


def handle_alias_set(args: AliasSetArgs) -> None:
    """Handle the 'alias set' sub-command."""
    mm = MetadataManager()
    # User aliases are stored in the same structured format as DEFAULT_ALIASES
    aliases: dict[str, Alias] = mm.load_user_aliases()

    # Validate that at least a run command is provided
    if not args.run or not args.run.strip():
        print("Error: --run command is required when setting an alias.", file=sys.stderr)
        sys.exit(1)

    # Build the command configuration using the dataclass
    command_config = CommandConfig(
        run=args.run,
        pre_flight=args.pre_flight,
        post_flight=args.post_flight,
        descendants_only=args.descendants_only,
        start_from_root=args.start_from_root,
    )

    # Handle environment variables
    env_vars = {}
    if args.env:
        for env_pair in args.env:
            if "=" not in env_pair:
                print(f"Error: Environment variable '{env_pair}' must be in KEY=VALUE format.", file=sys.stderr)
                sys.exit(1)
            key, value = env_pair.split("=", 1)
            env_vars[key] = value

    # Create the alias using the dataclass
    alias = Alias(
        description=args.description or f"User alias for: {args.run}",
        command=command_config,
        continue_cmd=args.continue_cmd,
        abort_cmd=args.abort_cmd,
        env=env_vars,
    )

    aliases[args.alias_name] = asdict(alias)
    mm.save_user_aliases(aliases)

    # Print confirmation using the alias object
    print(f"✅ User alias '{args.alias_name}' created successfully!")
    print(f"   Run command: {alias.command.run}")
    if alias.description:
        print(f"   Description: {alias.description}")
    if alias.command.pre_flight:
        print(f"   Pre-flight: {alias.command.pre_flight}")
    if alias.command.post_flight:
        print(f"   Post-flight: {alias.command.post_flight}")
    if alias.command.descendants_only:
        print("   Descendants only: Yes")
    if alias.command.start_from_root:
        print("   Start from root: Yes")
    if alias.continue_cmd:
        print(f"   Continue command: {alias.continue_cmd}")
    if alias.abort_cmd:
        print(f"   Abort command: {alias.abort_cmd}")
    if alias.env:
        print(f"   Environment variables: {', '.join(f'{k}={v}' for k, v in alias.env.items())}")


def handle_alias_list(args: AliasListArgs) -> None:
    """Handle the 'alias list' sub-command."""
    mm = MetadataManager()
    user_aliases: dict[str, Alias] = mm.load_user_aliases()

    def print_alias_details(name: str, alias_def: Alias, indent: str = "  ") -> None:
        """Print detailed information about an alias."""
        print(f"{indent}{name}: {alias_def.description}")
        if args.verbose:
            if alias_def.command.run:
                print(f"{indent}  Run: {alias_def.command.run}")
            if alias_def.command.pre_flight:
                print(f"{indent}  Pre-flight: {alias_def.command.pre_flight}")
            if alias_def.command.post_flight:
                print(f"{indent}  Post-flight: {alias_def.command.post_flight}")
            if alias_def.command.descendants_only:
                print(f"{indent}  Descendants only: Yes")
            if alias_def.command.start_from_root:
                print(f"{indent}  Start from root: Yes")
            if alias_def.continue_cmd:
                print(f"{indent}  Continue command: {alias_def.continue_cmd}")
            if alias_def.abort_cmd:
                print(f"{indent}  Abort command: {alias_def.abort_cmd}")
            if alias_def.env:
                env_vars = ", ".join(f"{k}={v}" for k, v in alias_def.env.items())
                print(f"{indent}  Environment: {env_vars}")

    print("--- Built-in Aliases ---")
    for name, a_def in sorted(DEFAULT_ALIASES.items()):
        print_alias_details(name, a_def)

    if user_aliases:
        print("\n--- User-defined Aliases (.sd_aliases.json) ---")
        for name, alias_def in sorted(user_aliases.items()):
            print_alias_details(name, alias_def)


def handle_alias_show(args: AliasShowArgs) -> None:
    """Handle the 'alias show' sub-command."""
    mm = MetadataManager()
    all_aliases: dict[str, Alias] = mm.get_all_aliases()

    if args.alias_name not in all_aliases:
        print(f"Error: Alias '{args.alias_name}' not found.", file=sys.stderr)
        sys.exit(1)

    alias_def = all_aliases[args.alias_name]
    is_builtin = args.alias_name in DEFAULT_ALIASES

    print(f"Alias: {args.alias_name} {'(built-in)' if is_builtin else '(user-defined)'}")
    print(f"Description: {alias_def.description}")

    if alias_def.command.run:
        print(f"Run command: {alias_def.command.run}")
    if alias_def.command.pre_flight:
        print(f"Pre-flight command: {alias_def.command.pre_flight}")
    if alias_def.command.post_flight:
        print(f"Post-flight command: {alias_def.command.post_flight}")
    if alias_def.command.descendants_only:
        print("Descendants only: Yes")
    if alias_def.command.start_from_root:
        print("Start from root: Yes")
    if alias_def.continue_cmd:
        print(f"Continue command: {alias_def.continue_cmd}")
    if alias_def.abort_cmd:
        print(f"Abort command: {alias_def.abort_cmd}")
    if alias_def.env:
        print("Environment variables:")
        for key, value in alias_def.env.items():
            print(f"  {key}={value}")


def handle_alias_rm(args: AliasRmArgs) -> None:
    """Handle the 'alias rm' sub-command."""
    mm = MetadataManager()
    aliases: dict[str, Alias] = mm.load_user_aliases()

    if args.alias_name not in aliases:
        print(f"Error: User alias '{args.alias_name}' not found.", file=sys.stderr)
        sys.exit(1)

    del aliases[args.alias_name]
    mm.save_user_aliases(aliases)
    print(f"✅ User alias '{args.alias_name}' removed.")


def handle_alias(args: AliasArgs) -> None:
    """Dispatch 'alias' sub-commands."""
    alias_parser = argparse.ArgumentParser(prog="sd alias", description="Manage command aliases.")
    alias_subparsers = alias_parser.add_subparsers(dest="alias_command", required=True)

    parser_set = alias_subparsers.add_parser("set", help="Set a new user alias with full configuration options.")
    parser_set.add_argument("alias_name", help="Name of the alias")

    # Command configuration
    parser_set.add_argument("--run", required=True, help="Main command to run")
    parser_set.add_argument("--pre-flight", dest="pre_flight", help="Command to run before the main command")
    parser_set.add_argument("--post-flight", dest="post_flight", help="Command to run after the main command")
    parser_set.add_argument(
        "--descendants-only", dest="descendants_only", action="store_true", help="Only run on descendant branches"
    )
    parser_set.add_argument(
        "--start-from-root",
        dest="start_from_root",
        action="store_true",
        help="Start execution from the root of the stack",
    )

    # Alias metadata
    parser_set.add_argument("--description", help="Description of what the alias does")
    parser_set.add_argument("--continue-cmd", dest="continue_cmd", help="Command to run when continuing")
    parser_set.add_argument("--abort-cmd", dest="abort_cmd", help="Command to run when aborting")
    parser_set.add_argument(
        "--env", action="append", help="Environment variables in KEY=VALUE format (can be used multiple times)"
    )

    parser_list = alias_subparsers.add_parser("list", aliases=["ls"], help="List all built-in and user aliases.")
    parser_list.add_argument("-v", "--verbose", action="store_true", help="Show detailed information about each alias")

    parser_show = alias_subparsers.add_parser("show", help="Show detailed information about a specific alias.")
    parser_show.add_argument("alias_name", help="Name of the alias to show")

    parser_rm = alias_subparsers.add_parser("rm", help="Remove a user alias from .sd_aliases.json.")
    parser_rm.add_argument("alias_name")

    alias_args = alias_parser.parse_args(sys.argv[2:])

    # Create appropriate dataclass instance based on subcommand
    if alias_args.alias_command == "set":
        typed_args = AliasSetArgs(
            alias_command=alias_args.alias_command,
            alias_name=alias_args.alias_name,
            run=alias_args.run,
            pre_flight=getattr(alias_args, "pre_flight", None),
            post_flight=getattr(alias_args, "post_flight", None),
            descendants_only=getattr(alias_args, "descendants_only", False),
            start_from_root=getattr(alias_args, "start_from_root", False),
            description=getattr(alias_args, "description", None),
            continue_cmd=getattr(alias_args, "continue_cmd", None),
            abort_cmd=getattr(alias_args, "abort_cmd", None),
            env=getattr(alias_args, "env", None),
        )
        handle_alias_set(typed_args)
    elif alias_args.alias_command == "list":
        typed_args = AliasListArgs(
            alias_command=alias_args.alias_command,
            verbose=getattr(alias_args, "verbose", False),
        )
        handle_alias_list(typed_args)
    elif alias_args.alias_command == "show":
        typed_args = AliasShowArgs(
            alias_command=alias_args.alias_command,
            alias_name=alias_args.alias_name,
        )
        handle_alias_show(typed_args)
    elif alias_args.alias_command == "rm":
        typed_args = AliasRmArgs(
            alias_command=alias_args.alias_command,
            alias_name=alias_args.alias_name,
        )
        handle_alias_rm(typed_args)
