import subprocess, os
from anthropic import Anthropic


def check_precommit_installed():
    """Check if pre-commit is installed and configured."""
    try:
        # Check if pre-commit command exists
        result = subprocess.run(
            ["pre-commit", "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.returncode != 0:
            return False

        # Check if .pre-commit-config.yaml exists
        return os.path.exists(".pre-commit-config.yaml")
    except FileNotFoundError:
        return False


def run_precommit_hooks():
    """Run pre-commit hooks on staged files."""
    try:
        print("Running pre-commit hooks...")
        result = subprocess.run(
            ["pre-commit", "run", "--files"] + get_staged_files(),
            text=True,
            encoding="utf-8",
        )

        if result.returncode == 0:
            print("✓ Pre-commit hooks passed")
            return True
        else:
            print("✗ Pre-commit hooks failed")
            print(
                "Please fix the issues and re-stage your files before running git cam again."
            )
            return False

    except Exception as e:
        print(f"Error running pre-commit hooks: {str(e)}")
        return False


def should_run_precommit():
    """Ask user if they want to run pre-commit hooks."""
    if not check_precommit_installed():
        return False

    try:
        response = (
            input("Pre-commit hooks detected. Run them first? (Y/n): ").strip().lower()
        )
        return response in ["", "y", "yes"]
    except KeyboardInterrupt:
        return False


def get_git_config_key():
    """Get Anthropic API key from git config."""
    result = subprocess.run(
        ["git", "config", "--global", "--get", "cam.apikey"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def get_git_config_model():
    """Get Anthropic API Model from git config."""
    result = subprocess.run(
        ["git", "config", "--global", "--get", "cam.model"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def get_git_config_instructions():
    """Get custom instruction from git config."""
    result = subprocess.run(
        ["git", "config", "--global", "--get", "cam.instructions"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def get_git_config_token_limit():
    """Get token limit from git config, default to 1024 if not set."""
    result = subprocess.run(
        ["git", "config", "--global", "--get", "cam.tokenlimit"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    try:
        return int(result.stdout.strip()) if result.stdout.strip() else 1024
    except ValueError:
        print(
            "Error reading value, defaulting to 1024. Update using 'git config --global --set cam.tokenlimit=1234'"
        )
        return 1024


def get_git_config_history_limit():
    """Get history limit from git config, default to 5 if not set."""
    result = subprocess.run(
        ["git", "config", "--global", "--get", "cam.historylimit"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    try:
        return int(result.stdout.strip()) if result.stdout.strip() else 5
    except ValueError:
        return 5


def estimate_tokens(text):
    """Rough estimate of token count (approximates GPT tokenization)."""
    # Rough approximation: 4 characters per token on average
    return len(text) // 4


def show_token_limit():
    """Display token limit from git config."""
    token_limit = get_git_config_token_limit()
    if token_limit:
        print("\nCurrent token limit:")
        print("-" * 40)
        print(token_limit)
        print("-" * 40)
    else:
        print("No token limit configured")


def set_token_limit(limit):
    """Set output token limit in git config (more tokens = longer messages)."""
    try:
        limit = int(limit)
        if limit <= 0:
            print("Token limit must be a positive number")
            return False
        subprocess.run(["git", "config", "--global", "cam.tokenlimit", str(limit)])
        print(f"Token limit set to: {limit}")
        return True
    except ValueError:
        print("Token limit must be a valid number")
        return False


def show_history_limit():
    """Display history limit from git config."""
    history_limit = get_git_config_history_limit()
    print(f"\nCurrent history limit: {history_limit} commits")
    print("-" * 40)


def set_history_limit(limit):
    """Set history limit in git config (number of recent commits to include)."""
    try:
        limit = int(limit)
        if limit < 0:
            print("History limit must be 0 or greater (0 disables history)")
            return False
        if limit > 20:
            print("History limit should be 20 or fewer for performance reasons")
            return False
        subprocess.run(["git", "config", "--global", "cam.historylimit", str(limit)])
        print(f"History limit set to: {limit}")
        return True
    except ValueError:
        print("History limit must be a valid number")
        return False


def get_recent_git_history(limit=5):
    """Get recent git commit history for context."""
    if limit <= 0:
        return ""

    try:
        # Get recent commits with --oneline format
        result = subprocess.run(
            ["git", "log", "--oneline", f"-{limit}", "--no-merges"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        if result.returncode != 0:
            return ""

        history = result.stdout.strip()
        if not history:
            return ""

        # Format the history for better readability
        formatted_history = []
        for line in history.split("\n"):
            if line.strip():
                formatted_history.append(f"  {line}")

        return f"Recent commit history:\n" + "\n".join(formatted_history)

    except Exception:
        return ""


def get_affected_files_history(staged_files, limit=10):
    """Get commit history for files that are being modified."""
    if limit <= 0 or not staged_files:
        return ""

    try:
        history_parts = []

        for file_path in staged_files[
            :5
        ]:  # Limit to first 5 files to avoid too much output
            # Get recent commits that modified this file
            result = subprocess.run(
                ["git", "log", "--oneline", f"-{limit}", "--", file_path],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            if result.returncode == 0 and result.stdout.strip():
                file_history = result.stdout.strip().split("\n")
                if (
                    file_history and file_history[0]
                ):  # Only add if there's actual history
                    history_parts.append(f"\nRecent changes to {file_path}:")
                    for commit_line in file_history[
                        :3
                    ]:  # Limit to 3 most recent commits per file
                        if commit_line.strip():
                            history_parts.append(f"  {commit_line}")

        return "\n".join(history_parts) if history_parts else ""

    except Exception:
        return ""


def get_staged_files():
    """Get list of staged files."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        if result.returncode == 0:
            return [f.strip() for f in result.stdout.split("\n") if f.strip()]
        return []
    except Exception:
        return []


def append_instruction(new_instruction):
    """Append a new instruction to existing instructions in git config."""
    existing = get_git_config_instructions()
    if existing:
        # If existing instructions end with a period, remove it before appending
        if existing.endswith("."):
            existing = existing[:-1]
        # Combine existing and new with proper separation
        combined = f"{existing}. {new_instruction}"
    else:
        combined = new_instruction

    # Ensure the final instruction ends with a period
    if not combined.endswith("."):
        combined += "."

    subprocess.run(["git", "config", "--global", "cam.instructions", combined])
    print("\nUpdated instructions:")
    print("-" * 40)
    print(combined)
    print("-" * 40)


def show_instructions():
    """Display current instructions from git config."""
    instructions = get_git_config_instructions()
    if instructions:
        print("\nCurrent instructions:")
        print("-" * 40)
        print(instructions)
        print("-" * 40)
    else:
        print("No instructions configured")


def set_instructions(new_instructions):
    """Set new instructions in git config, replacing any existing ones."""
    # Ensure the instruction ends with a period
    if new_instructions and not new_instructions.endswith("."):
        new_instructions += "."

    subprocess.run(["git", "config", "--global", "cam.instructions", new_instructions])
    print("\nInstructions updated successfully:")
    print("-" * 40)
    print(new_instructions)
    print("-" * 40)


def setup_api_key():
    """Set up the Anthropic API key in git config with existing values as defaults."""
    # Get existing values
    existing_key = get_git_config_key()
    existing_model = get_git_config_model()
    existing_instructions = get_git_config_instructions()
    existing_history_limit = get_git_config_history_limit()

    # Set default model if none exists
    default_model = existing_model if existing_model else "claude-3-5-haiku-latest"

    # Prompt for API key with existing value as default
    default_prompt = f" [{existing_key}]" if existing_key else ""
    api_key = input(f"Enter your Anthropic API key{default_prompt}: ").strip()
    if not api_key and existing_key:
        api_key = existing_key

    # Save API key if provided
    if api_key:
        subprocess.run(["git", "config", "--global", "cam.apikey", api_key])

    # Prompt for model with default value
    model_prompt = f" [{default_model}]"
    model = input(f"Enter preferred Claude model{model_prompt}: ").strip()
    if not model:
        model = default_model
    subprocess.run(["git", "config", "--global", "cam.model", model])

    # Prompt for instructions with existing value as default
    instructions_prompt = f" [{existing_instructions}]" if existing_instructions else ""
    instructions = input(
        f"Enter additional instructions for Claude{instructions_prompt}: "
    ).strip()
    if not instructions and existing_instructions:
        instructions = existing_instructions
    if instructions:
        subprocess.run(["git", "config", "--global", "cam.instructions", instructions])

    # Prompt for history limit with existing value as default
    history_prompt = f" [{existing_history_limit}]"
    history_limit = input(
        f"Enter number of recent commits to include for context (0-20){history_prompt}: "
    ).strip()
    if not history_limit:
        history_limit = str(existing_history_limit)

    try:
        history_limit_int = int(history_limit)
        if 0 <= history_limit_int <= 20:
            subprocess.run(
                ["git", "config", "--global", "cam.historylimit", history_limit]
            )
        else:
            print("History limit must be between 0-20, using default of 5")
            subprocess.run(["git", "config", "--global", "cam.historylimit", "5"])
    except ValueError:
        print("Invalid history limit, using default of 5")
        subprocess.run(["git", "config", "--global", "cam.historylimit", "5"])

    print("Configuration saved")


def get_filtered_diff():
    """Get staged diff with filtered new/moved/deleted files."""
    # Get list of staged files and their statuses
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout

    # Initialize lists for different file categories
    modified_files = []
    new_files = []
    moved_files = []
    deleted_files = []

    # Parse status output
    for line in status.splitlines():
        if not line.startswith(" "):  # Only look at staged files
            status_code = line[:2]
            file_path = line[3:]

            if status_code.startswith("R"):
                old_path, new_path = file_path.split(" -> ")
                moved_files.append((old_path, new_path))
            elif status_code.startswith("A"):
                new_files.append(file_path)
            elif status_code.startswith("M"):
                modified_files.append(file_path)
            elif status_code.startswith("D"):
                deleted_files.append(file_path)

    # Build the diff output
    diff_parts = []

    if deleted_files:
        diff_parts.append("Deleted files (-):")
        for file in deleted_files:
            diff_parts.append(f"- {file}")
        diff_parts.append("")

    new_file_parts = []
    if new_files:
        diff_parts.append("New files added (+):")
        for file in new_files:
            diff_parts.append(f"+ {file}")

            # Check if file exists and is under 1KB
            try:
                file_size = os.path.getsize(file)
                if file_size < 8192:  # 8KB = 8192 bytes
                    # Get the file content using git show
                    file_content = subprocess.run(
                        ["git", "show", f":{file}"],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                    ).stdout

                    if file_content:
                        new_file_parts.append("\nContent of new file '" + file + "':")
                        new_file_parts.append("[START OF FILE '" + file + "']")
                        new_file_parts.append(file_content.rstrip())
                        new_file_parts.append("[END OF FILE '" + file + "']")
            except (OSError, subprocess.SubprocessError):
                # Skip if there's any error accessing the file
                continue
        diff_parts.append("")

    if new_file_parts:
        diff_parts += new_file_parts

    if moved_files:
        diff_parts.append("Files moved:")
        for old, new in moved_files:
            diff_parts.append(f"↻ {old} -> {new}")
        diff_parts.append("")

    if modified_files:
        diff_parts.append("Modified files (~):")
        for file in modified_files:
            file_diff = subprocess.run(
                ["git", "diff", "--cached", file],
                capture_output=True,
                text=True,
                encoding="utf-8",
            ).stdout
            if file_diff:
                diff_parts.append(f"~ {file}")
                diff_parts.append("[START OF MODIFICATIONS FOR '" + file + "']")
                diff_parts.append(file_diff)
                diff_parts.append("[END OF MODIFICATIONS FOR '" + file + "']")

    if diff_parts:
        return "\n".join(diff_parts)
    elif deleted_files or new_files or moved_files:
        return "\n".join(diff_parts)
    else:
        return ""


def get_contextual_history():
    """Get both general history and file-specific history for better context."""
    history_limit = get_git_config_history_limit()

    if history_limit <= 0:
        return ""

    # Get general recent history
    recent_history = get_recent_git_history(history_limit)

    # Get staged files for file-specific history
    staged_files = get_staged_files()
    file_history = get_affected_files_history(staged_files, min(history_limit, 10))

    # Combine histories
    context_parts = []
    if recent_history:
        context_parts.append(recent_history)
    if file_history:
        context_parts.append(file_history)

    return "\n".join(context_parts) if context_parts else ""


def generate_commit_message(
    diff, review_content, user_context, config_instructions, api_key, api_model
):
    """Generate commit message using Claude with git history context."""
    client = Anthropic(api_key=api_key)

    context_section = (
        f"\nUser provided context:\n{user_context}" if user_context else ""
    )

    # Get git history context
    history_context = get_contextual_history()
    history_section = (
        f"\nGit History Context:\n{history_context}" if history_context else ""
    )

    message = client.messages.create(
        model=api_model,
        max_tokens=get_git_config_token_limit(),
        messages=[
            {
                "role": "user",
                "content": f"""Analyse this git diff and code review to generate a commit message. Use insights from the review, git history context, and any user-provided context to make the commit message more descriptive of the changes' purpose and impact.

Be as concise as possible and avoid exaggerating minor changes to be more impactful than they are. The git history helps you understand the development patterns and context of this repository.

Code Review:
{review_content}

User context [Start]: {context_section} [end user context]

{history_section}

Global system instructions [Start]: {config_instructions} [end system instructions]

Return ONLY a string with a single key "message:" containing the commit message, e.g:
message:First line: Brief summary (max 50 chars)
<blank line>
- Following lines (if needed): Detailed explanation

Here's the diff:

{diff}""",
            }
        ],
    )
    return message.content[0].text.split("message:", 1)[1].strip()


def perform_code_review(diff, api_key, api_model, config_instructions):
    """Perform an AI code review on the changes with git history context."""
    client = Anthropic(api_key=api_key)

    # Get git history context
    history_context = get_contextual_history()
    history_section = (
        f"\nGit History Context:\n{history_context}\n" if history_context else ""
    )

    message = client.messages.create(
        model=api_model,
        max_tokens=get_git_config_token_limit(),
        messages=[
            {
                "role": "user",
                "content": f"""Review this git diff for potential issues. The git history context helps you understand recent development patterns and the evolution of these files. If no significant issues are found, respond with a brief confirmation. If issues are found, provide specific details about:

- What problem does this change solve?
- Critical bugs or errors
- Security concerns
- Significant performance issues
- Major maintainability problems
- Unintentional debug printing to console
- Filename / code location of the found issues
- How this change fits with recent development patterns

If there is a critical issue, add the text "STOP_COMMIT" to your response.

What counts as critical:
- Security vulnerabilities
- Exposed secrets or credentials
- Dangerous configuration changes
- Major data safety issues
- Critical performance problems
- Broken authentication
- Command injection risks

{history_section}Global system instructions [Start]: {config_instructions} [end system instructions]

Return your response in this format:
review:
[Your concise review here - one line if no issues, detailed explanation only if problems found, optional question for user clarification if required]

Here's the diff (remember, lines starting with + have been added, lines starting with - are removed):

{diff}""",
            }
        ],
    )
    return message.content[0].text.split("review:", 1)[1].strip()
