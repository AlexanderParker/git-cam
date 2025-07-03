#!/usr/bin/env python
import sys
import argparse
import subprocess
from git_cam.utils import (
    get_git_config_key,
    setup_api_key,
    get_git_config_model,
    get_filtered_diff,
    get_git_config_instructions,
    perform_code_review,
    generate_commit_message,
    append_instruction,
    set_instructions,
    show_instructions,
    set_token_limit,
    show_token_limit,
    set_history_limit,
    show_history_limit,
    estimate_tokens,
)
from git_cam.recheck import analyze_repository
from git_cam.classes import CLIFormatter


def is_git_repo() -> bool:
    """Check if current directory is inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            check=False,  # Don't raise on error
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except Exception:
        return False


def create_parser():
    parser = argparse.ArgumentParser(
        description="AI-powered Git commit message generator using Claude",
        add_help=False,  # Disable default help since we're handling it ourselves
    )

    # Add subcommands
    subparsers = parser.add_subparsers(dest="command")

    # Add 'help' as a command
    subparsers.add_parser("help", help="Show help information")

    # Add 'recheck' as a command with question option
    recheck_parser = subparsers.add_parser(
        "recheck", help="Analyse repository for improvements"
    )
    recheck_parser.add_argument(
        "-q", "--query", type=str, help="Specific question or focus for the analysis"
    )

    # Add optional arguments
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Configure your Anthropic API key, model, and other preferences",
    )
    parser.add_argument("--version", action="version", version="git-cam version 0.1.0")
    parser.add_argument(
        "--add-instruction",
        type=str,
        metavar="INSTRUCTION",
        help="Append a new instruction to existing commit message guidelines",
    )
    parser.add_argument(
        "--set-instructions",
        type=str,
        metavar="INSTRUCTIONS",
        help="Set new instructions, replacing existing ones",
    )
    parser.add_argument(
        "--show-instructions", action="store_true", help="Display current instructions"
    )
    parser.add_argument(
        "--set-token-limit",
        type=str,
        metavar="LIMIT",
        help="Set maximum token limit for diff output (default: 1024)",
    )
    parser.add_argument(
        "--show-token-limit", action="store_true", help="Show the current token limit."
    )
    parser.add_argument(
        "--set-history-limit",
        type=str,
        metavar="LIMIT",
        help="Set number of recent commits to include for context (0-20, default: 5)",
    )
    parser.add_argument(
        "--show-history-limit",
        action="store_true",
        help="Show the current history limit.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Shows verbose output, including the diff being sent to Claude",
    )
    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Stage all modified files and commit (skips verification)",
    )

    return parser


def show_help():
    print(
        """
git cam by Alex Parker - see GitHub for details: https://github.com/alexparker/git-cam

Usage: git cam [command] [options]

Commands:
    help                    | Show this help message
    recheck                 | Check your entire repository for improvement suggestions (experimental feature)
    
Options:
    --setup                 | Configure your Anthropic API key, model, and (optional) instructions
    --version               | Show version information    
    --set-instructions      | Set new instructions (replaces existing ones)
    --add-instruction       | Append a new instruction to existing commit guidelines
    --show-instructions     | Display current instructions
    --set-token-limit       | Set maximum token limit for diff output (default: 1024)
    --show-token-limit      | Show the current token limit
    --set-history-limit     | Set number of recent commits to include for context (0-20, default: 5)
    --show-history-limit    | Show the current history limit

Behaviour Switches
    -a, --all               | Stage all modified files and commit (skips verification)
    -v, --verbose           | Shows verbose output, including the diff being sent to Claude
    
Example workflow:
    git add .
    git cam

Configuration (initial setup):
    git cam --setup         | Configure API key, model, instructions, and history settings

History Context:
    Git-cam now includes recent commit history to provide better context for reviews and commit messages.
    You can control how many recent commits to include (0-20) using --set-history-limit.
    Set to 0 to disable history context entirely.

"""
    )


def stage_all_files():
    """Stage all modified files."""
    subprocess.run(["git", "add", "-A"])


def has_critical_issues(review: str) -> bool:
    """
    Check if the review contains a STOP_COMMIT string.
    Returns (has_critical_issues, formatted_message)
    """
    if review.find("STOP_COMMIT") > -1:
        return True

    return False


def main():
    try:
        parser = create_parser()
        args = parser.parse_args(sys.argv[1:])

        # Add git repo check right after argument parsing
        if len(sys.argv) > 1 and sys.argv[1] in ["--help", "--version", "help"]:
            # Skip git repo check for help and version
            pass
        else:
            if not is_git_repo():
                print(
                    CLIFormatter.error(
                        "Could not access a git repository here (or any parent up to mount point /)"
                    )
                )
                print(
                    CLIFormatter.error(
                        "Check your folder and permissions (running 'git status' may yield clues)"
                    )
                )
                print(
                    CLIFormatter.error(
                        "Stopping at filesystem boundary (GIT_DISCOVERY_ACROSS_FILESYSTEM not set)"
                    )
                )
                sys.exit(1)

        parser = create_parser()
        args = parser.parse_args(sys.argv[1:])

        # Handle commands
        if args.command == "help":
            show_help()
            return

        if args.setup:
            setup_api_key()
            return

        if args.add_instruction:
            append_instruction(args.add_instruction)
            return

        if args.set_instructions:
            set_instructions(args.set_instructions)
            return

        if args.show_instructions:
            show_instructions()
            return

        if args.set_token_limit:
            set_token_limit(args.set_token_limit)
            return

        if args.show_token_limit:
            show_token_limit()
            return

        if args.set_history_limit:
            set_history_limit(args.set_history_limit)
            return

        if args.show_history_limit:
            show_history_limit()
            return

        # Get the API key
        api_key = get_git_config_key()
        if not api_key:
            print(
                CLIFormatter.error(
                    "API key not found. Run 'git cam --setup' first ('git cam help' for more info)"
                )
            )
            sys.exit(1)

        # Get the API model
        api_model = get_git_config_model()
        if not api_model:
            print(
                CLIFormatter.error("API model not found. Run 'git cam --setup' first")
            )
            sys.exit(1)

        # Get the API model
        config_instructions = get_git_config_instructions()

        if args.command == "recheck":
            query = getattr(args, "query", None)
            analyze_repository(api_key, api_model, config_instructions, query)
            return

        # Stage all files if -a flag is used
        if args.all:
            print(CLIFormatter.input_prompt("Staging all modified files..."))
            stage_all_files()

        # Get the staged diff
        diff = get_filtered_diff()
        if not diff:
            print(CLIFormatter.error("No changes staged for commit"))
            sys.exit(1)

        # Show diff in verbose mode
        if args.verbose:
            print(CLIFormatter.header("Diff Preview"))
            print(CLIFormatter.diff_header())
            print(diff)
            print(CLIFormatter.separator())
            token_count = estimate_tokens(diff)
            print(f"\nEstimated tokens: {token_count} (NOTE: Just a rough guess!)")
            print(
                CLIFormatter.input_prompt(
                    "Press Enter to continue or Ctrl+C to cancel..."
                )
            )
            input()

        # First, perform the code review
        print("\nReviewing changes...", end="", flush=True)
        try:
            review = perform_code_review(diff, api_key, api_model, config_instructions)

            if args.all:
                has_critical = has_critical_issues(review)

                if has_critical:
                    print(
                        CLIFormatter.error(
                            "\nCritical issues found that require attention:"
                        )
                    )
                    print("\n")
                    print(CLIFormatter.error(review.replace("STOP_COMMIT", "").strip()))
                    print("\n")
                    print(
                        CLIFormatter.warning(
                            "Auto-commit cancelled for safety. Please review these issues carefully."
                        )
                    )
                    print(
                        CLIFormatter.warning(
                            "To bypass this check, use regular 'git cam' without -a flag to review and confirm if these changes are intended."
                        )
                    )
                    sys.exit(1)
                else:
                    user_context = ""  # No user context in auto mode
            else:
                has_issues = (
                    len(review.strip().split("\n")) > 1
                    or "issue" in review.lower()
                    or "concern" in review.lower()
                )

                print(CLIFormatter.header("Code Review"))
                print(CLIFormatter.review_header())

                if has_issues:
                    print(CLIFormatter.warning(review))
                else:
                    print(CLIFormatter.success(review))

                print(CLIFormatter.separator())
                print(
                    CLIFormatter.input_prompt(
                        "Would you like to proceed with generating a commit message?\n"
                        "(Enter additional context, or press Enter to continue, or 'n' to cancel)"
                    )
                )
                user_input = input().strip()

                if user_input.lower() == "n":
                    print(CLIFormatter.warning("Commit cancelled"))
                    sys.exit(0)

                user_context = (
                    user_input if user_input and user_input.lower() != "y" else ""
                )

        except Exception as e:
            print(CLIFormatter.error(f"\nError during code review: {str(e)}"))
            sys.exit(1)

        # Generate and handle commit message
        while True:
            try:
                message = generate_commit_message(
                    diff, review, user_context, config_instructions, api_key, api_model
                )
                if not args.all:  # Show message preview in normal mode
                    print(CLIFormatter.header("Generated Commit Message"))
                    print(CLIFormatter.message_header())
                    print(f"\n{message}\n")
                    print(CLIFormatter.separator())
                    print(
                        CLIFormatter.input_prompt(
                            "(A)ccept, (c)ancel, or (r)egenerate? (ENTER accepts by default)"
                        )
                    )

                    choice = input().lower()
                    if choice == "a" or choice == "":
                        subprocess.run(["git", "commit", "-m", message])
                        print(CLIFormatter.success("Commit created successfully!"))
                        break
                    elif choice == "c":
                        print(CLIFormatter.warning("Commit cancelled"))
                        break
                    elif choice == "r":
                        print(
                            CLIFormatter.input_prompt("Regenerating commit message...")
                        )
                        continue
                else:  # Auto mode - commit immediately
                    subprocess.run(["git", "commit", "-m", message])
                    print(CLIFormatter.success("Changes committed successfully!"))
                    print(CLIFormatter.message_header())
                    print(f"\n{message}\n")
                    break
            except Exception as e:
                print(CLIFormatter.error(f"Error: {str(e)}"))
                sys.exit(1)

    except KeyboardInterrupt:
        print("\n" + CLIFormatter.warning("Operation cancelled by user"))
        sys.exit(0)


if __name__ == "__main__":
    main()
