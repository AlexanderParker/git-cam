#!/usr/bin/env python
import sys
import os
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
    check_git_hooks,
    should_run_hooks,
    run_precommit_hooks,
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
    """
    Create and configure the argument parser for git-cam.

    Returns:
        argparse.ArgumentParser: Configured parser with all commands and options
    """
    parser = argparse.ArgumentParser(
        description="AI-powered Git commit message generator using Claude",
        add_help=False,  # Disable default help since we're handling it ourselves
    )

    # Add subcommands
    subparsers = parser.add_subparsers(dest="command")

    # Add 'help' as a command
    subparsers.add_parser("help", help="Show help information")

    # Add 'recheck' as a command with question option
    recheck_parser = subparsers.add_parser("recheck", help="Analyse repository for improvements")
    recheck_parser.add_argument("-q", "--query", type=str, help="Specific question or focus for the analysis")

    # Add optional arguments
    parser.add_argument(
        "--skip-pre-commit",
        action="store_true",
        help="Skip running pre-commit hooks even if they're configured",
    )
    parser.add_argument(
        "--pre-commit",
        action="store_true",
        help="Force running pre-commit hooks (don't ask)",
    )
    parser.add_argument(
        "--force-commit",
        action="store_true",
        help="Commit even if pre-commit hooks fail",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Configure your Anthropic API key, model, and other preferences",
    )
    parser.add_argument("--version", action="version", version="git-cam version 0.2.3")
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
    parser.add_argument("--show-instructions", action="store_true", help="Display current instructions")
    parser.add_argument(
        "--set-token-limit",
        type=str,
        metavar="LIMIT",
        help="Set maximum token limit for diff output (default: 1024)",
    )
    parser.add_argument("--show-token-limit", action="store_true", help="Show the current token limit.")
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
    """Display comprehensive help information for git-cam usage."""
    print(
        """
git cam by Alex Parker - see GitHub for details: https://github.com/AlexanderParker/git-cam

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
    --pre-commit            | Force running pre-commit hooks (don't ask)
    --skip-pre-commit       | Skip running pre-commit hooks even if they're configured
    --force-commit          | Commit even if pre-commit hooks fail

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
    """Stage all modified files using 'git add -A'."""
    subprocess.run(["git", "add", "-A"])


def has_critical_issues(review: str) -> bool:
    """
    Check if the code review contains critical issues that should block commits.

    Args:
        review: The review text from the AI code review

    Returns:
        bool: True if critical issues are found (review ends with STOP_COMMIT)
    """
    # Only consider it a critical issue if the review ENDS with STOP_COMMIT
    # This prevents false positives when STOP_COMMIT is mentioned in context
    return review.strip().endswith("STOP_COMMIT")


def handle_critical_issues_in_auto_mode(review: str) -> tuple[bool, str]:
    """
    Handle critical issues found during auto-commit mode.

    Args:
        review: The review text containing critical issues

    Returns:
        tuple: (should_continue, user_context)
               should_continue: True if user wants to proceed despite issues
               user_context: Additional context provided by user
    """
    print(CLIFormatter.error("\nCritical issues found in auto-commit mode that require attention:"))
    print("\n")
    # Remove STOP_COMMIT marker and display the review
    clean_review = review.replace("STOP_COMMIT", "").strip()
    print(CLIFormatter.error(clean_review))
    print("\n")

    print(CLIFormatter.warning("Auto-commit mode detected potential safety concerns."))
    print(
        CLIFormatter.input_prompt("Do you want to proceed with the commit anyway? (y/N): "),
        end="",
    )

    try:
        proceed_choice = input().strip().lower()
        if proceed_choice not in ["y", "yes"]:
            print(CLIFormatter.warning("Auto-commit cancelled for safety."))
            print(
                CLIFormatter.warning(
                    "To bypass these checks in future, use regular 'git cam' without -a flag to review and confirm changes."
                )
            )
            return False, ""

        # User wants to proceed - get context
        print(
            CLIFormatter.input_prompt(
                "Please provide context for why you're proceeding despite these issues (optional): "
            ),
            end="",
        )
        user_context = input().strip()

        print(CLIFormatter.warning("Proceeding with auto-commit despite critical issues..."))
        return True, user_context

    except KeyboardInterrupt:
        print("\n" + CLIFormatter.warning("Auto-commit cancelled"))
        return False, ""


def run_precommit_with_auto_restage(is_auto_mode: bool = False) -> bool:
    """
    Run pre-commit hooks, and in auto mode, automatically restage and retry if they fail.
    
    Args:
        is_auto_mode: Whether we're in auto-commit mode (-a flag)
        
    Returns:
        bool: True if hooks passed (eventually), False if they failed
    """
    hooks_passed = run_precommit_hooks()
    
    if not hooks_passed and is_auto_mode:
        print(CLIFormatter.warning("Pre-commit hooks failed. Auto-fixing and re-staging changes..."))
        
        # Re-stage all files to capture any auto-fixes
        stage_all_files()
        
        # Run hooks again to see if auto-fixes resolved the issues
        print(CLIFormatter.input_prompt("Running pre-commit hooks again after auto-fixes..."))
        hooks_passed_second = run_precommit_hooks()
        
        if hooks_passed_second:
            print(CLIFormatter.success("Pre-commit hooks passed after auto-fixes!"))
            return True
        else:
            print(CLIFormatter.warning("Pre-commit hooks still failing after auto-fixes."))
            return False
    
    return hooks_passed


def main():
    try:
        parser = create_parser()
        args = parser.parse_args(sys.argv[1:])

        # Skip git repository validation for help and version commands
        if len(sys.argv) > 1 and sys.argv[1] in ["--help", "--version", "help"]:
            pass
        else:
            if not is_git_repo():
                print(CLIFormatter.error("Could not access a git repository here (or any parent up to mount point /)"))
                print(CLIFormatter.error("Check your folder and permissions (running 'git status' may yield clues)"))
                print(CLIFormatter.error("Stopping at filesystem boundary (GIT_DISCOVERY_ACROSS_FILESYSTEM not set)"))
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

        # Get API configuration
        api_key = get_git_config_key()
        if not api_key:
            print(CLIFormatter.error("API key not found. Run 'git cam --setup' first ('git cam help' for more info)"))
            sys.exit(1)

        api_model = get_git_config_model()
        if not api_model:
            print(CLIFormatter.error("API model not found. Run 'git cam --setup' first"))
            sys.exit(1)

        config_instructions = get_git_config_instructions()

        # Handle recheck command
        if args.command == "recheck":
            query = getattr(args, "query", None)
            analyze_repository(api_key, api_model, config_instructions, query)
            return

        # Stage all files if --all flag is used
        if args.all:
            print(CLIFormatter.input_prompt("Staging all modified files..."))
            stage_all_files()

        # Get staged changes for review and commit message generation
        diff = get_filtered_diff()
        if not diff:
            print(CLIFormatter.error("No changes staged for commit"))
            sys.exit(1)

        # Run pre-commit hooks if configured and not skipped
        skip_git_hooks = False  # Only set to True if we actually need to bypass hooks
        hook_bypass_reason = ""  # Track reason for bypassing hooks

        if not args.skip_pre_commit:
            # Use the new unified hook detection system
            if args.pre_commit:
                # Force running pre-commit hooks
                hook_decision = {
                    "run_precommit": True,
                    "bypass_native": True,
                    "reason": "Manual pre-commit check (--pre-commit flag)",
                }
            elif args.all:
                # Auto-commit mode - check what hooks exist and handle automatically
                hook_info = check_git_hooks()
                if hook_info["has_precommit"] and hook_info["precommit_available"]:
                    hook_decision = {
                        "run_precommit": True,
                        "bypass_native": True,
                        "reason": "Auto-commit mode with pre-commit",
                    }
                elif hook_info["has_native_hooks"]:
                    hook_decision = {
                        "run_precommit": False,
                        "bypass_native": False,
                        "reason": "Auto-commit mode with native hooks",
                    }
                else:
                    hook_decision = {
                        "run_precommit": False,
                        "bypass_native": False,
                        "reason": "Auto-commit mode, no hooks",
                    }
            else:
                # Interactive mode - ask user
                try:
                    hook_decision = should_run_hooks()
                except KeyboardInterrupt:
                    print("\n" + CLIFormatter.warning("Operation cancelled by user"))
                    os._exit(0)

            skip_git_hooks = hook_decision["bypass_native"]
            hook_bypass_reason = hook_decision["reason"]

            # Run pre-commit if requested
            if hook_decision["run_precommit"]:
                # Use the new function that handles auto-restaging in auto mode
                hooks_passed = run_precommit_with_auto_restage(is_auto_mode=args.all)
                
                if not hooks_passed:
                    if args.force_commit:
                        # Force commit flag used
                        print(
                            CLIFormatter.warning("Pre-commit hooks failed, but proceeding due to --force-commit flag.")
                        )
                        hook_bypass_reason = "Used --force-commit flag"
                    elif args.all:
                        # Auto-commit mode - automatically proceed
                        print(CLIFormatter.warning("Pre-commit hooks failed in auto-commit mode. Proceeding anyway..."))
                        hook_bypass_reason = "Auto-commit mode with hook failures"
                    else:
                        # Interactive mode - ask user
                        print(CLIFormatter.error("Pre-commit hooks failed. Please fix issues and try again."))
                        print(
                            CLIFormatter.warning("Alternatively, use --force-commit to commit despite hook failures.")
                        )

                        # Prompt user for choice to proceed despite failures
                        print(
                            CLIFormatter.input_prompt("Do you want to commit anyway? (y/N): "),
                            end="",
                        )
                        try:
                            force_choice = input().strip().lower()
                            if force_choice not in ["y", "yes"]:
                                print(CLIFormatter.warning("Commit cancelled"))
                                sys.exit(1)
                            else:
                                print(CLIFormatter.warning("Proceeding with commit despite hook failures..."))
                                # Ask for reason when bypassing hooks
                                print(
                                    CLIFormatter.input_prompt(
                                        "Please provide a reason for bypassing pre-commit hooks (optional): "
                                    ),
                                    end="",
                                )
                                hook_bypass_reason = input().strip()
                        except KeyboardInterrupt:
                            print("\n" + CLIFormatter.warning("Commit cancelled"))
                            os._exit(1)
                else:
                    # Hooks passed
                    if args.all:
                        hook_bypass_reason = "Auto-commit mode (hooks passed)"
                    else:
                        hook_bypass_reason = "Manual pre-commit check passed"

                # Update staged diff after running pre-commit hooks (important for auto-fixes)
                updated_diff = get_filtered_diff()
                if not updated_diff:
                    print(CLIFormatter.error("No changes staged after pre-commit hooks"))
                    sys.exit(1)
                diff = updated_diff

        # Display diff preview in verbose mode
        if args.verbose:
            print(CLIFormatter.header("Diff Preview"))
            print(CLIFormatter.diff_header())
            print(diff)
            print(CLIFormatter.separator())
            token_count = estimate_tokens(diff)
            print(f"\nEstimated tokens: {token_count} (NOTE: Just a rough guess!)")
            print(CLIFormatter.input_prompt("Press Enter to continue or Ctrl+C to cancel..."))
            input()

        # Perform AI code review of changes
        print("\nReviewing changes...", end="", flush=True)
        try:
            review = perform_code_review(diff, api_key, api_model, config_instructions)

            # Handle auto-commit mode (--all flag)
            if args.all:
                has_critical = has_critical_issues(review)

                if has_critical:
                    # Handle critical issues in auto-commit mode with user interaction
                    should_continue, user_context = handle_critical_issues_in_auto_mode(review)
                    if not should_continue:
                        sys.exit(1)
                    # If we reach here, user wants to continue with the provided context
                elif review.strip().endswith("NOTICE"):
                    # Show notice and ask user to confirm in auto-commit mode
                    print(CLIFormatter.warning("\nCode review found issues that need attention:"))
                    clean_review = review.replace("NOTICE", "").strip()
                    print(CLIFormatter.warning(clean_review))
                    print("\n")
                    print(
                        CLIFormatter.input_prompt(
                            "Auto-commit mode detected issues. Do you want to proceed anyway? (y/N): "
                        ),
                        end="",
                    )

                    try:
                        proceed_choice = input().strip().lower()
                        if proceed_choice not in ["y", "yes"]:
                            print(CLIFormatter.warning("Auto-commit cancelled."))
                            print(
                                CLIFormatter.warning(
                                    "Please address the issues above or use regular 'git cam' to review them interactively."
                                )
                            )
                            sys.exit(1)

                        # User wants to proceed - get optional context
                        print(
                            CLIFormatter.input_prompt(
                                "Please provide context for why you're proceeding despite these issues (optional): "
                            ),
                            end="",
                        )
                        user_context = input().strip()

                        print(CLIFormatter.warning("Proceeding with auto-commit despite issues..."))

                    except KeyboardInterrupt:
                        print("\n" + CLIFormatter.warning("Auto-commit cancelled"))
                        sys.exit(1)
                else:
                    user_context = ""  # OK case - no user context in auto mode when no issues
            else:
                # Handle interactive mode - show review and get user input
                print(CLIFormatter.header("Code Review"))
                print(CLIFormatter.review_header())

                # Format review with red STOP_COMMIT highlighting if present
                formatted_review = review
                if "STOP_COMMIT" in review:
                    formatted_review = review.replace("STOP_COMMIT", CLIFormatter.error("STOP_COMMIT"))

                # Determine review status based on ending, not content
                if review.strip().endswith("STOP_COMMIT"):
                    # Critical issues - red
                    print(CLIFormatter.error(formatted_review))
                elif review.strip().endswith("NOTICE"):
                    # Minor issues/suggestions - yellow
                    print(CLIFormatter.warning(formatted_review))
                elif review.strip().endswith("OK"):
                    # All good - green
                    print(CLIFormatter.success(formatted_review))
                else:
                    # Fallback for unexpected responses - yellow
                    print(CLIFormatter.warning(formatted_review))

                print(CLIFormatter.separator())

                # Different prompts based on review result
                if review.strip().endswith("STOP_COMMIT"):
                    # Critical issues - default to cancel
                    print(
                        CLIFormatter.input_prompt(
                            "Critical issues detected. Do you want to proceed anyway?\n"
                            "(Type 'y' or 'yes' to continue, Enter or 'n' to cancel)"
                        )
                    )
                    user_input = input().strip()

                    if user_input.lower() not in ["y", "yes"]:
                        print(CLIFormatter.warning("Commit cancelled due to critical issues"))
                        sys.exit(0)

                    # User wants to proceed despite critical issues
                    print(
                        CLIFormatter.input_prompt(
                            "Please provide context for why you're proceeding despite these critical issues: "
                        ),
                        end="",
                    )
                    user_context = input().strip()
                else:
                    # Normal flow - default to continue
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

                    user_context = user_input if user_input and user_input.lower() != "y" else ""

        except Exception as e:
            print(CLIFormatter.error(f"\nError during code review: {str(e)}"))
            sys.exit(1)

        # Generate commit message and handle user interaction
        while True:
            try:
                message = generate_commit_message(
                    diff,
                    review,
                    user_context,
                    config_instructions,
                    api_key,
                    api_model,
                    skip_git_hooks,
                    hook_bypass_reason,
                )
                if not args.all:  # Interactive mode - show message preview and get user choice
                    print(CLIFormatter.header("Generated Commit Message"))
                    print(CLIFormatter.message_header())
                    print(f"\n{message}\n")
                    print(CLIFormatter.separator())
                    print(CLIFormatter.input_prompt("(A)ccept, (c)ancel, or (r)egenerate? (ENTER accepts by default)"))

                    choice = input().lower()
                    if choice == "a" or choice == "":
                        # Use --no-verify if we already handled failed hooks
                        commit_cmd = ["git", "commit", "-m", message]
                        if skip_git_hooks:
                            commit_cmd.append("--no-verify")

                        result = subprocess.run(commit_cmd, capture_output=True, text=True)
                        if result.returncode == 0:
                            print(CLIFormatter.success("Commit created successfully!"))
                            break
                        else:
                            print(CLIFormatter.error(f"Git commit failed: {result.stderr.strip()}"))
                            sys.exit(1)
                    elif choice == "c":
                        print(CLIFormatter.warning("Commit cancelled"))
                        break
                    elif choice == "r":
                        print(CLIFormatter.input_prompt("Regenerating commit message..."))
                        continue
                else:  # Auto-commit mode - commit immediately without prompting
                    # Use --no-verify if we already handled failed hooks
                    commit_cmd = ["git", "commit", "-m", message]
                    if skip_git_hooks:
                        commit_cmd.append("--no-verify")

                    result = subprocess.run(commit_cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        print(CLIFormatter.success("Changes committed successfully!"))
                        print(CLIFormatter.message_header())
                        print(f"\n{message}\n")
                        break
                    else:
                        print(CLIFormatter.error(f"Git commit failed: {result.stderr.strip()}"))
                        sys.exit(1)
            except Exception as e:
                print(CLIFormatter.error(f"Error: {str(e)}"))
                sys.exit(1)

    except KeyboardInterrupt:
        print("\n" + CLIFormatter.warning("Operation cancelled by user"))
        os._exit(0)


if __name__ == "__main__":
    main()