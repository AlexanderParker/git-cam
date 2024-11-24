#!/usr/bin/env python
import sys
import argparse
import subprocess

from lib.utils import (
    get_git_config_key,
    setup_api_key,
    get_git_config_model,
    get_filtered_diff,
    get_git_config_instructions,
    get_git_config_token_limit,
    perform_code_review,
    generate_commit_message,
    append_instruction,
    set_instructions,
    show_instructions,
    set_token_limit,
    show_token_limit,
    estimate_tokens
)


def create_parser():
    parser = argparse.ArgumentParser(
        description="AI-powered Git commit message generator using Claude",
        add_help=False,  # Disable default help since we're handling it ourselves
    )

    # Add subcommands
    subparsers = parser.add_subparsers(dest="command")

    # Add 'help' as a command
    subparsers.add_parser("help", help="Show help information")

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
        help="Append a new instruction to existing commit message guidelines"
    )
    parser.add_argument(
        "--set-instructions",
        type=str,
        metavar="INSTRUCTIONS",
        help="Set new instructions, replacing existing ones"
    )
    parser.add_argument(
        "--show-instructions",
        action="store_true",
        help="Display current instructions"
    )
    parser.add_argument(
        "--set-token-limit",
        type=str,
        metavar="LIMIT",
        help="Set maximum token limit for diff output (default: 1024)"
    )
    parser.add_argument(
        "--show-token-limit",
        action="store_true",
        help="Show the current token limit."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Shows verbose output, including the diff being sent to Claude"
    )
    return parser


def show_help():
    print(
        """
Usage: git cam [command] [options]

Commands:
    help                    * Show this help message

Options:
    --setup                 * Configure your Anthropic API key, model, and (optional) instructions
    --version               * Show version information    
    --set-instructions      * Set new instructions (replaces existing ones)
    --add-instruction       * Append a new instruction to existing commit guidelines
    --show-instructions     * Display current instructions
    --set-token-limit       * Set maximum token limit for diff output (default: 1024)
    --show-token-limit      * Show the current token limit

Example workflow:
    git add .
    git cam

Configuration (initial setup):
    git cam --setup         * Configure API key, model and instructions

View the readme on GitHub for more help: https://github.com/AlexanderParker/git-cam
"""
    )


def main():
    try:
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

        # Get the API key
        api_key = get_git_config_key()
        if not api_key:
            print(
                "API key not found. Run 'git cam --setup' first ('git cam help' for more info)"
            )
            sys.exit(1)

        # Get the API model
        api_model = get_git_config_model()
        if not api_model:
            print("API model not found. Run 'git cam setup' first")
            sys.exit(1)

        # Get the API model
        config_instructions = get_git_config_instructions()

        # Get the staged diff
        diff = get_filtered_diff()
        if not diff:
            print("No changes staged for commit")
            sys.exit(1)

        # Show diff in verbose mode
        if args.verbose:
            print("\nDiff being sent to Claude:")
            print("=" * 80)
            print(diff)
            print("=" * 80)
            token_count = estimate_tokens(diff)
            print(f"\nEstimated tokens: {token_count} (NOTE: Just a rough guess!)")
            print("\nPress Enter to continue or Ctrl+C to cancel...")
            input()

        # First, perform the code review
        print("\nReviewing changes...", end="", flush=True)
        try:
            review = perform_code_review(diff, api_key, api_model, config_instructions)
            print("\r", end="")  # Clear the "Analyzing changes..." message

            if (
                len(review.strip().split("\n")) > 1
                or "issue" in review.lower()
                or "concern" in review.lower()
            ):
                # If review has multiple lines or mentions issues/concerns, print with emphasis
                print("\nReview result:")
                print("-" * 40)
                print(review)
                print("-" * 40)
            else:
                # For simple "all good" reviews, print inline
                print(f"\n✓ {review}")

            print(
                "Enter optional clarifications (then ENTER). Entering 'n' or 'q' will cancel the commit: "
            )
            print("> ", end="", flush=True)
            user_input = input().strip()

            if user_input.lower() == "n" or user_input.lower() == "q":
                print("Commit cancelled")
                sys.exit(0)

            user_context = (
                user_input if user_input and user_input.lower() != "y" else ""
            )

        except Exception as e:
            print(f"\nError during code review: {str(e)}")
            sys.exit(1)

        # Generate and handle commit message
        while True:
            try:
                message = generate_commit_message(
                    diff, review, user_context, config_instructions, api_key, api_model
                )
                print("\nGenerated message (" + api_model + "):\n")
                print(message)
                print("\n(A)ccept, (c)ancel, or (r)egenerate? ")

                choice = input().lower()
                if choice == "a" or choice == "":
                    subprocess.run(["git", "commit", "-m", message])
                    break
                elif choice == "c":
                    break
                elif choice == "r":
                    continue

            except Exception as e:
                print(f"Error: {str(e)}")
                sys.exit(1)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
