# git-cam

An AI-powered Git commit message generator that analyzes your changes and generates meaningful commit messages using Claude. It also performs a quick code review of your changes before committing.

## Features

- AI-powered commit message generation
- Automatic code review before commit
- Supports context from user input
- Handles new, modified, moved, and deleted files

## Installation

1. Install via pip:

Option 1: Install directly from GitHub

```
$ pip install git+https://github.com/AlexanderParker/git-cam.git
```

Option 2: Git clone and install locally

```
$ pip install [path to local folder where you cloned the repo]
```

2. Set up your Anthropic API key, preferred model, and optional instructions:

```
$ git cam --setup

Enter your Anthropic API key [...]:
Enter preferred Claude model [...]:
Enter additional instructions for Claude [...]:
```

- If setup has already run, defaults will be shown in square brackets - just press enter to preserve the existing setting.
- The default model initially is "claude-3-5-haiku-20241022" - I find this provides a balance of cost and quality that suits me.

## Installation Options

### System-wide Installation

To install git-cam for all users (requires admin/root privileges):

```bash
pip install git+https://github.com/AlexanderParker/git-cam.git
```

### User Installation

To install git-cam for your user only:

```bash
pip install --user git+https://github.com/AlexanderParker/git-cam.git
```

When using `--user`, the script is installed to your user's script directory. You'll need to ensure this directory is in your PATH:

#### Windows

The user scripts directory is typically:

```
%APPDATA%\Python\PythonVVV\Scripts [VVV is your Python version number, i.e. 311]
```

To add to PATH:

1. Press Win + R
2. Type `systempropertiesadvanced` and press Enter
3. Click "Environment Variables"
4. Under "User variables", edit "Path"
5. Add the Scripts path above
6. Click OK and restart your terminal

#### macOS/Linux

The user scripts directory is typically:

```bash
# macOS
~/Library/Python/x.x/bin [x.x is your Python version number, i.e. 3.11]

# Linux
~/.local/bin
```

Add to PATH by adding this to your `~/.bashrc`, `~/.zshrc`, or equivalent:

```bash
# macOS
export PATH="$HOME/Library/Python/3.x/bin:$PATH"

# Linux
export PATH="$HOME/.local/bin:$PATH"
```

Then reload your shell:

```bash
source ~/.bashrc  # or ~/.zshrc
```

### Verifying Installation

After installation and PATH setup, verify the command is available:

```bash
git cam --version
```

### First-time Setup

Once installed, configure your API key and preferences:

```bash
git cam --setup
```

## Usage

Instead of `git commit`, use `git cam` to commit your staged changes:

1. Stage your desired changes (using `git add`, or tool of your choice)
2. Run `git cam`
3. Claude will review your changes and show you the results.
4. You can type in additional context if requested, or if necessary (i.e. adding a Jira ticket number)
5. Claude will generate a commit message, which you can choose to accept, regenerate, or cancel.

### Commands

- `help`: Show help message
- `recheck`: Check your entire repository for improvement suggestions (experimental feature).

### Options

- `--setup`: Configure cam's settings
- `--version`: Show version information
- `--set-instructions`: Set new instructions (replaces existing ones)
- `--add-instruction`: Append a new instruction to global commit guidelines
- `--show-instructions`: Display current instructions
- `--set-token-limit`: Set maximum token limit for diff output (default: 1024)
- `--show-token-limit`: Show the current token limit

### Behaviour Switches

- `-a`, `--all`: Stage all modified files and commit (skips verification)
- `-v`, `--verbose`: Shows verbose output, including the diff being sent to Claude

Note: The Token limit refers to the model's output; a higher number means longer replies from the model. Models like Claude's 3.5 Haiku support an input context window of 200k tokens which this project assumes is more than enough for regular use-cases.

## Custom instructions

You can update your custom instructions (used for every run). For example if you prefer British over American english:

```
$ git cam --set-instructions "Always use British English"
Instructions updated successfully:

----------------------------------------
Always use British English.
----------------------------------------
```

Also, you can add new instructions to the existing list as follows:

```
$ git cam --add-instruction "Don't use emojis"

Updated instructions:
----------------------------------------
Always use British English. Don't use emojis.
----------------------------------------
```

Finally, you can show your current instructions at any time:

```
PS C:\tools\git-cam-dev> git cam --show-instructions

Current instructions:
----------------------------------------
Always use British English. Don't use emojis.
----------------------------------------
```

## Repository Analysis

The `recheck` command performs a comprehensive analysis of your repository to suggest improvements:

```bash
git cam recheck
```

This command:

- Scans all text files in your repository (up to 4KB per file)
- Processes files in batches of 50KB
- Analyzes code structure, organization, and best practices
- Provides prioritized recommendations for improvements

The analysis covers:

- Project structure and organization
- File naming conventions
- Documentation completeness
- Development workflow
- Package configuration
- Dependencies management
- Installation processes
- Testing opportunities

Binary files, build artifacts, and common temporary files are automatically excluded from the analysis.

## Git Global Configuration

The tool stores its settings in Git's global config, so you can use the commands provided or directly adjust the following git configuration settings:

```
$ git config --global cam.apikey YOUR_API_KEY
$ git config --global cam.model claude-3-5-haiku-latest
$ git config --global cam.instructions "your custom instructions (can be blank)"
$ git config --global cam.tokenlimit 1024

## Requirements

- Python 3.6+
- Git
- Anthropic API key

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
```
