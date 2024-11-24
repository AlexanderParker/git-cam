# git-cam

An AI-powered Git commit message generator that analyzes your changes and generates meaningful commit messages using Claude. It also performs a quick code review of your changes before committing.

## Features

- AI-powered commit message generation
- Automatic code review before commit
- Supports context from user input
- Handles new, modified, moved, and deleted files

## Installation

1. Install via pip:

```
$ pip install git-cam
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

## Usage

Instead of `git commit`, use `git cam` to commit your staged changes:

1. Stage your desired changes (using `git add`, or tool of your choice)
2. Run `git cam`
3. Claude will review your changes and show you the results.
4. You can type in additional context if requested, or if necessary (i.e. adding a Jira ticket number)
5. Claude  will generate a commit message, which you can choose to accept, regenerate, or cancel.

### Commands

- `help`: Show help message

### Options

- `--setup`: Configure cam's settings
- `--version`: Show version information
- `--set-instructions`: Set new instructions (replaces existing ones)
- `--add-instruction`: Append a new instruction to global commit guidelines
- `--show-instructions`: Display current instructions
- `--set-token-limit`: Set maximum token limit for diff output (default: 1024)
- `--show-token-limit`: Show the current token limit

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
