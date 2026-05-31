# PYTHON_ARGCOMPLETE_OK
import argparse
import sys

import argcomplete

from inf_hub.commands import (
    VALID_ROLES,
    cmd_create_project,
    cmd_history,
    cmd_init_folder,
    cmd_list_identities,
    cmd_list_orgs,
    cmd_list_projects,
    cmd_pull,
    cmd_push,
    cmd_register_token,
    cmd_rollback,
    cmd_set,
    cmd_unset,
    cmd_unregister_token,
)
from inf_hub.config import DEFAULT_TYPES
from inf_hub.errors import ConfigError, InfHubError, InteractiveAbort, ValidationError
from inf_hub.ui import print_line


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ih", description="inf-hub CLI")
    sub = parser.add_subparsers(dest="command")

    p_register = sub.add_parser("register", help="Register resources")
    register_sub = p_register.add_subparsers(dest="register_object")
    p_register_token = register_sub.add_parser("token", help="Register API token")
    p_register_token.add_argument("--token", help="Infisical API token")
    p_register_token.add_argument("--token-id", help="Unique token name")
    p_register_token.add_argument("--yes", "-y", action="store_true", help="Non-interactive")
    p_register_token.add_argument("--skip-checks", action="store_true", help="Reserved for compatibility")

    p_unregister = sub.add_parser("unregister", help="Unregister resources")
    unregister_sub = p_unregister.add_subparsers(dest="unregister_object")
    p_unregister_token = unregister_sub.add_parser("token", help="Unregister API token")
    p_unregister_token.add_argument("--token-id", help="Unique token name")
    p_unregister_token.add_argument("--yes", "-y", action="store_true", help="Non-interactive")

    p_init = sub.add_parser("init", help="Initialize ih")
    init_sub = p_init.add_subparsers(dest="init_command")
    p_init_folder = init_sub.add_parser("folder", help="Initialize local .inf context")
    p_init_folder.add_argument("--token-id", help="Token ID")
    p_init_folder.add_argument("--project-id", help="Project ID")
    p_init_folder.add_argument("--environment", "-e", help="Environment slug (default: dev)")
    p_init_folder.add_argument("--yes", "-y", action="store_true", help="Non-interactive")

    p_create = sub.add_parser("create", help="Create resources")
    create_sub = p_create.add_subparsers(dest="create_object")
    p_create_project = create_sub.add_parser("project", help="Create project")
    p_create_project.add_argument("--name", help="Project name")
    p_create_project.add_argument("--slug", help="Project slug")
    p_create_project.add_argument("--token-id", help="Token ID")
    p_create_project.add_argument("--identity-id", help="Machine identity ID")
    p_create_project.add_argument("--role", choices=VALID_ROLES, help="Identity role")
    p_create_project.add_argument("--yes", "-y", action="store_true", help="Non-interactive")

    p_list = sub.add_parser("list", help="List resources")
    list_sub = p_list.add_subparsers(dest="list_object")
    p_lo = list_sub.add_parser("orgs", help="List registered tokens")
    p_lo.add_argument("--yes", "-y", action="store_true", help="Non-interactive")
    p_lp = list_sub.add_parser("projects", help="List projects")
    p_lp.add_argument("--token-id", help="Token ID")
    p_lp.add_argument("--yes", "-y", action="store_true", help="Non-interactive")
    p_li = list_sub.add_parser("identities", help="List identities")
    p_li.add_argument("--token-id", help="Token ID")
    p_li.add_argument("--yes", "-y", action="store_true", help="Non-interactive")

    p_set = sub.add_parser("set", help="Set context value")
    p_set.add_argument("type", choices=DEFAULT_TYPES, help="Value type")
    p_set.add_argument("--value", help="Value")
    p_set.add_argument("--token-id", help="Token ID for interactive context")

    p_unset = sub.add_parser("unset", help="Unset context value")
    p_unset.add_argument("type", choices=DEFAULT_TYPES, help="Value type")

    p_pull = sub.add_parser("pull", help="Pull env from remote")
    p_pull.add_argument("--token-id", help="Token ID")
    p_pull.add_argument("--project-id", help="Project ID")
    p_pull.add_argument("--environment", "-e", help="Environment")
    p_pull.add_argument("-f", "--file", help="Output file path")
    p_pull.add_argument("-p", action="store_true", help="Print to stdout")
    p_pull.add_argument("--yes", "-y", action="store_true", help="Non-interactive")

    p_push = sub.add_parser("push", help="Push env to remote")
    p_push.add_argument("--token-id", help="Token ID")
    p_push.add_argument("--project-id", help="Project ID")
    p_push.add_argument("--environment", "-e", help="Environment")
    p_push.add_argument("-f", "--file", help="Input file path")
    p_push.add_argument("-k", action="append", help="Secret key (repeatable)")
    p_push.add_argument("-v", action="append", help="Secret value (repeatable)")
    p_push.add_argument("--yes", "-y", action="store_true", help="Non-interactive")

    p_hist = sub.add_parser("history", help="Show secret history")
    p_hist.add_argument("--token-id", help="Token ID")
    p_hist.add_argument("--project-id", help="Project ID")
    p_hist.add_argument("--environment", "-e", help="Environment")
    p_hist.add_argument("--name", help="Secret name")
    p_hist.add_argument("--yes", "-y", action="store_true", help="Non-interactive")

    p_rb = sub.add_parser("rollback", help="Rollback secret and sync local file")
    p_rb.add_argument("--token-id", help="Token ID")
    p_rb.add_argument("--project-id", help="Project ID")
    p_rb.add_argument("--environment", "-e", help="Environment")
    p_rb.add_argument("--name", help="Secret name")
    p_rb.add_argument("--version", help="Version to rollback to")
    p_rb.add_argument("-f", "--file", help="Local file to sync (default: .env)")
    p_rb.add_argument("--yes", "-y", action="store_true", help="Non-interactive")

    return parser


def dispatch(args: argparse.Namespace) -> None:
    if args.command == "register":
        if args.register_object != "token":
            raise ValidationError("missing register object. Use: ih register token")
        cmd_register_token(args)
        return
    if args.command == "unregister":
        if args.unregister_object != "token":
            raise ValidationError("missing unregister object. Use: ih unregister token")
        cmd_unregister_token(args)
        return
    if args.command == "init":
        if getattr(args, "init_command", None) != "folder":
            raise ValidationError("missing init object. Use: ih init folder")
        cmd_init_folder(args)
        return
    if args.command == "create":
        if args.create_object != "project":
            raise ValidationError("missing create object. Use: ih create project")
        cmd_create_project(args)
        return
    if args.command == "list":
        if args.list_object == "orgs":
            cmd_list_orgs(args)
        elif args.list_object == "projects":
            cmd_list_projects(args)
        elif args.list_object == "identities":
            cmd_list_identities(args)
        else:
            raise ValidationError("missing list object. Use: ih list orgs|projects|identities")
        return
    if args.command == "set":
        cmd_set(args)
        return
    if args.command == "unset":
        cmd_unset(args)
        return
    if args.command == "pull":
        if args.p and args.file:
            raise ValidationError("use either -p or -f, not both")
        cmd_pull(args)
        return
    if args.command == "push":
        cmd_push(args)
        return
    if args.command == "history":
        cmd_history(args)
        return
    if args.command == "rollback":
        cmd_rollback(args)
        return


def main() -> None:
    parser = build_parser()
    argcomplete.autocomplete(parser, default_completer=None)
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        dispatch(args)
    except InteractiveAbort:
        sys.exit(130)
    except KeyboardInterrupt:
        sys.exit(130)
    except (ValidationError, ConfigError) as exc:
        print_line(f"Error: {exc}")
        sys.exit(1)
    except InfHubError as exc:
        print_line(f"Error: {exc}")
        sys.exit(1)
    except SystemExit:
        raise
    except Exception as exc:
        msg = str(exc)
        if "API error" in msg:
            print_line(f"Error: {msg}")
        elif "unauthorized" in msg.lower() or "401" in msg:
            print_line("Error: Unauthorized. Check your API token.")
            print_line("Run 'ih register token --token-id YOUR_TOKEN_NAME --token YOUR_TOKEN' to update.")
        elif "forbidden" in msg.lower() or "403" in msg:
            print_line("Error: Forbidden. You don't have permission for this operation.")
        else:
            print_line(f"Error: {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
