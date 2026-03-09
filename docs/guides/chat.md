# Chat

Interactive terminal chat that lets you converse with an LLM about your codebase while it invokes skene tools to gather information.

## Prerequisites

- An API key configured (see [Configuration](configuration.md)) or a local LLM running
- A codebase to analyze

## Basic usage

```bash
# Chat about the current directory
uvx skene chat

# Chat about a specific codebase
uvx skene chat /path/to/project

# Using the shorthand (defaults to chat)
uvx skene
```

Running `skene` without a subcommand defaults to the `chat` command, providing a convenient shorthand for interactive sessions.

## Flags

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--api-key` | | API key for LLM provider | `SKENE_API_KEY` env var |
| `--provider` | `-p` | LLM provider | Config or `openai` |
| `--model` | `-m` | LLM model name | Provider default |
| `--base-url` | | Base URL for OpenAI-compatible API endpoint. Required when provider is `generic`. | `SKENE_BASE_URL` env var |
| `--max-steps` | | Maximum tool calls per user request | `4` |
| `--tool-output-limit` | | Max tool output characters kept in context | `4000` |
| `--debug` | | Log all LLM input/output to `.skene/debug/` | Off |

## How it works

The chat command starts an interactive terminal session where:

1. You type a question or request about your codebase
2. The LLM decides which skene tools to call (analyze, search, read files, etc.)
3. Tool results are fed back to the LLM within the context window
4. The LLM synthesizes a response based on the tool outputs

The `--max-steps` flag controls how many tool calls the LLM can make per request. Increase this for complex queries that require multiple analysis passes. The `--tool-output-limit` flag controls how much of each tool's output is kept in context to avoid exceeding token limits.

## Tips for effective use

- **Be specific** — "What growth features does this codebase have?" works better than "Tell me about this code"
- **Increase max-steps for deep analysis** — Use `--max-steps 8` when you want the LLM to do thorough multi-step analysis
- **Use debug mode to understand behavior** — `--debug` logs all LLM interactions so you can see what tools are being called

## Next steps

- [Analyze command](analyze.md) — Run a full codebase analysis
- [LLM providers](llm-providers.md) — Configure different providers for chat
- [Configuration](configuration.md) — Set defaults so you don't need flags every time
