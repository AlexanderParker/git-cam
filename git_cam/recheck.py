import os
from typing import List, Dict, Tuple
from anthropic import Anthropic
from git_cam.classes import CLIFormatter
import subprocess
from git_cam.utils import get_git_config_token_limit
from pathlib import Path
import pathspec  # New import for handling gitignore patterns


def get_gitignore_spec(repo_root: str) -> pathspec.PathSpec:
    """Load and parse .gitignore patterns."""
    gitignore_path = os.path.join(repo_root, ".gitignore")
    patterns = []

    # Add default patterns
    patterns.extend(
        [
            "__pycache__/*",
            ".git/*",
            ".env",
            ".venv/*",
            "venv/*",
            "node_modules/*",
            "dist/*",
            "build/*",
            ".DS_Store",
            "Thumbs.db",
            "*.log",
            "*.tmp",
            "*.temp",
            "*.swp",
            "*.swo",
            "*~",
            ".pytest_cache/*",
            ".coverage",
            "coverage.xml",
            ".tox/*",
            ".idea/*",
            ".vscode/*",
            ".vs/*",
            "*.code-workspace",
        ]
    )

    # Add patterns from .gitignore if it exists
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r") as f:
            patterns.extend(
                line.strip() for line in f if line.strip() and not line.startswith("#")
            )

    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def is_binary(filepath: str) -> bool:
    """
    Determine if a file is binary by:
    1. Checking file extension
    2. Examining content for binary data if extension check is inconclusive
    """
    # Common binary file extensions
    binary_extensions = {
        # Compiled Code
        ".pyc",
        ".pyo",
        ".pyd",
        ".obj",
        ".o",
        ".so",
        ".dll",
        ".dylib",
        ".class",
        ".jar",
        ".war",
        ".exe",
        ".app",
        ".out",
        # Media
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".ico",
        ".tiff",
        ".webp",
        ".mp3",
        ".wav",
        ".ogg",
        ".flac",
        ".m4a",
        ".wma",
        ".mp4",
        ".avi",
        ".mov",
        ".wmv",
        ".flv",
        ".mkv",
        ".webm",
        # Archives
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".7z",
        ".rar",
        ".iso",
        # Documents
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        # Database
        ".db",
        ".sqlite",
        ".sqlite3",
        ".mdb",
        # Other
        ".bin",
        ".dat",
        ".pak",
        ".ttf",
        ".otf",
        ".woff",
        ".woff2",
    }

    # Check extension first
    ext = os.path.splitext(filepath)[1].lower()
    if ext in binary_extensions:
        return True

    # If extension check is inconclusive, check content
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(8192)
            try:
                chunk.decode("utf-8")
                return False
            except UnicodeDecodeError:
                return True
        return False
    except (IOError, OSError):
        return True


def should_ignore_file(filepath: str, gitignore_spec: pathspec.PathSpec) -> bool:
    """Check if file should be ignored based on gitignore patterns and binary detection."""
    # Check against gitignore patterns
    if gitignore_spec.match_file(filepath):
        return True

    # Check if it's a binary file
    if is_binary(filepath):
        return True

    return False


def get_file_hierarchy(repo_root: str, files: List[Tuple[str, int]]) -> str:
    """Generate a hierarchical representation of the repository structure."""

    def create_tree_dict() -> Dict:
        tree = {}
        for filepath, _ in files:
            current = tree
            parts = filepath.split(os.sep)
            for part in parts[:-1]:
                current = current.setdefault(part, {})
            current[parts[-1]] = None
        return tree

    def format_tree(tree: Dict, prefix: str = "") -> List[str]:
        lines = []
        items = sorted(tree.items())
        for i, (name, subtree) in enumerate(items):
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{name}")
            if subtree is not None:
                extension = "    " if is_last else "│   "
                lines.extend(format_tree(subtree, prefix + extension))
        return lines

    tree_dict = create_tree_dict()
    tree_lines = format_tree(tree_dict)
    return "\n".join(tree_lines)


def get_file_batch(files: List[Tuple[str, int]], batch_size: int = 50000) -> List[Dict]:
    """Group files into batches based on size limit."""
    batches = []
    current_batch = []
    current_size = 0

    for filepath, size in files:
        if size > 16384 or size > batch_size or size == 0:
            continue

        if current_size + size > batch_size:
            if current_batch:
                batches.append(current_batch)
            current_batch = []
            current_size = 0

        current_batch.append({"path": filepath, "size": size, "content": None})
        current_size += size

    if current_batch:
        batches.append(current_batch)

    return batches


def load_batch_contents(batch: List[Dict]) -> List[Dict]:
    """Load contents for a batch of files."""
    for file_info in batch:
        try:
            with open(file_info["path"], "r", encoding="utf-8") as f:
                file_info["content"] = f.read()
        except Exception as e:
            file_info["content"] = f"Error reading file: {str(e)}"
    return batch


def analyze_repository(api_key: str, api_model: str, config_instructions: str, question: str = None) -> str:
    """Analyze entire repository for improvements."""
    client = Anthropic(api_key=api_key)

    # Get repository root
    repo_root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
        encoding='utf-8'
    ).stdout.strip()

    # Load gitignore patterns
    gitignore_spec = get_gitignore_spec(repo_root)

    print(CLIFormatter.header("Repository Analysis..."))
    if question:
        print(CLIFormatter.input_prompt(f"Analysis focus: {question}\n"))

    # Limit the generated response.
    token_limit = get_git_config_token_limit()

    # Collect files
    all_files = []
    skipped_files = 0
    for root, _, files in os.walk(repo_root):
        for file in files:
            filepath = os.path.join(root, file)
            rel_path = os.path.relpath(filepath, repo_root)

            if should_ignore_file(rel_path, gitignore_spec):
                skipped_files += 1
                continue

            try:
                size = os.path.getsize(filepath)
                all_files.append((rel_path, size))
            except OSError:
                continue

    # Generate file hierarchy
    file_hierarchy = get_file_hierarchy(repo_root, all_files)

    # Group files into batches
    batches = get_file_batch(all_files)
    total_batches = len(batches)

    if not batches:
        print(CLIFormatter.error("No suitable files found for analysis"))
        return

    print(
        CLIFormatter.success(
            f"Found {len(all_files)} files for analysis "
            f"({skipped_files} ignored files skipped)"
        )
    )
    print(CLIFormatter.success(f"Split into {total_batches} batches"))

    # Check number of API calls and get confirmation
    num_api_calls = len(batches) + 1  # batches + final summary
    if num_api_calls > 10:
        if not confirm_analysis(num_api_calls):
            print(CLIFormatter.input_prompt("Analysis cancelled by user"))
            return

    # Analyze each batch
    all_recommendations = []
    accumulated_insights = ""  # Store insights from previous batches
    for batch_num, batch in enumerate(batches, 1):
        print(
            CLIFormatter.input_prompt(
                f"Analyzing batch {batch_num}/{total_batches} ({len(batch)} files)..."
            )
        )

        batch = load_batch_contents(batch)

        if not batch:
            continue

        # Prepare batch summary for Claude
        batch_summary = []


        
        for file_info in batch:
            batch_summary.append(f"\nFile: {file_info['path']}\n")
            batch_summary.append("[START OF FILE '" + file_info["path"] + "']")
            batch_summary.append(file_info["content"])
            batch_summary.append("[END OF FILE '" + file_info["path"] + "']")
        try:

            # Build context-aware prompt
            context_section = ""
            if accumulated_insights:
                context_section = f"""Consider these previous findings while analyzing the next batch of files:
{accumulated_insights}
Use the above findings to reinforce, or revise these insights based on the new files.
"""

            # Customize prompt based on whether there's a question
            if question:
                prompt = f"""Analyze these files from a Git repository specifically focusing on this question/topic: {question}

{context_section}

Provide relevant insights and recommendations related to this focus area.
If certain files aren't relevant to the question, you can skip them.
Keep recommendations clear and actionable.

Files to analyze:

{"".join(batch_summary)}"""
            else:
                prompt = f"""Analyze these files from a Git repository and provide recommendations for improvements. Consider:

1. Project structure and organization
2. File naming and code conventions
3. Documentation completeness
4. Development workflow optimization
5. Package configuration
6. Dependencies management
7. Installation process
8. Testing setup

{context_section}

Only mention actionable improvements - no need to comment on things that are already well done.
Use bullet points for recommendations.

Files to analyze:

{"".join(batch_summary)}"""

            message = client.messages.create(
                model=api_model,
                max_tokens=token_limit,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            batch_recommendations = message.content[0].text.strip()
            if batch_recommendations:
                all_recommendations.append(batch_recommendations)
                # Create a summary of key insights for the next batch
                try:
                    summary_prompt = f"""Extract the key insights and patterns from this analysis that would be most relevant for analyzing more files:

{batch_recommendations}

Return a concise bullet-point summary of the most important findings that could inform further analysis."""

                    summary_message = client.messages.create(
                        model=api_model,
                        max_tokens=1024,
                        messages=[{
                            "role": "user",
                            "content": summary_prompt
                        }]
                    )
                    
                    # Update accumulated insights, keeping only the most recent context
                    new_insights = summary_message.content[0].text.strip()
                    # Keep context focused by limiting to most recent 2-3 batches
                    accumulated_insights = "\n\n".join(
                        [accumulated_insights, new_insights]
                    ).split("\n\n")[-3:]  # Keep last 3 batch summaries
                    accumulated_insights = "\n\n".join(accumulated_insights).strip()
                    
                except Exception as e:
                    print(CLIFormatter.warning(f"Note: Could not summarize batch insights: {str(e)}"))
        except Exception as e:
            print(CLIFormatter.error(f"Error analyzing batch {batch_num}: {str(e)}"))
            continue

    # Generate final summary with file hierarchy context
    try:
        if all_recommendations:
            print(CLIFormatter.input_prompt("Generating final summary..."))

            context_for_summary = f"""
Analysis was performed in {len(all_recommendations)} batches.
Key patterns and insights discovered during analysis:
{accumulated_insights}
"""

            if question:
                final_prompt = f"""Review and consolidate these analysis results, specifically addressing this question/topic:

{question}

{context_for_summary}

Provide a clear, organized summary that directly answers the question and provides relevant recommendations.

Analysis results:

{chr(10).join(all_recommendations)}"""
            else:
                final_prompt = f"""Review and consolidate these analysis results into a prioritized set of recommendations for improving the Python package repository. Group similar suggestions and focus on the most impactful improvements.

{context_for_summary}

Consider how patterns and issues evolved across different parts of the codebase.

Analysis results:

{chr(10).join(all_recommendations)}"""

            message = client.messages.create(
                model=api_model,
                max_tokens=token_limit,
                messages=[
                    {
                        "role": "user",
                        "content": final_prompt,
                    }
                ],
            )

            final_summary = message.content[0].text.strip()

            print(CLIFormatter.header(
                "Repository Analysis Results" if not question else f"Analysis Results: {question}"
            ))            
            if not question:
                print(CLIFormatter.success("\nRepository Structure:"))
                print(file_hierarchy)
                print("\n" + CLIFormatter.success("Recommendations:"))                
            print(CLIFormatter.separator())
            print(final_summary)

            return final_summary

    except Exception as e:
        print(CLIFormatter.error(f"Error generating final summary: {str(e)}"))
        if all_recommendations:
            final_summary = "\n\n".join(all_recommendations)
            print(CLIFormatter.header("Individual Batch Results"))
            print(CLIFormatter.success("\nRepository Structure:"))
            print(file_hierarchy)
            print("\n" + CLIFormatter.success("Analysis Results:"))
            print(final_summary)
            print(CLIFormatter.separator())
            return final_summary

    return None
