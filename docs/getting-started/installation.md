# Installation

How to install skene-growth using uvx, pip, or from source.

## Prerequisites

- **Python 3.11 or later.** Check your version with `python3 --version`.

---

## Option 1: uvx (Recommended)

[uvx](https://docs.astral.sh/uv/) runs Python CLI tools without installing them globally. This is the fastest way to start using skene-growth.

If you don't have `uv` installed yet:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then run any skene-growth command directly:

```bash
uvx skene-growth analyze .
uvx skene-growth plan
```

No `pip install` needed. `uvx` downloads the package into an isolated environment on first run and caches it for subsequent calls.

### The `skene` shorthand

The package also registers a `skene` entry point that launches the interactive chat interface:

```bash
uvx --from skene-growth skene
```

> **Note:** Because `skene` is not the package name, you need `--from skene-growth` when using `uvx`. If you install via pip (Option 2), you can run `skene` directly.

---

## Option 2: pip

Install skene-growth into your current Python environment:

```bash
pip install skene-growth
```

After installation, the `skene-growth` and `skene` commands are available on your PATH:

```bash
skene-growth analyze .
skene chat
```

---

## Option 3: From source

Clone the repository and install in development mode:

```bash
git clone https://github.com/SkeneTechnologies/skene-growth.git
cd skene-growth
```

Using `uv` (recommended):

```bash
uv sync
```

Using pip:

```bash
pip install -e .
```

To include all optional dependencies:

```bash
pip install -e ".[mcp,ui]"
```

---

## Optional extras

Install extras for additional functionality:

| Extra | What it adds |
|-------|--------------|
| `mcp` | MCP server support (`skene-growth-mcp` entry point). Adds `mcp>=1.0.0` and `xxhash>=3.0`. |
| `ui` | Interactive terminal prompts via `questionary>=2.0`. |

```bash
# With uvx (use --from to specify extras)
uvx --from "skene-growth[mcp]" skene-growth-mcp

# With uv
uv pip install skene-growth[mcp]

# With pip
pip install skene-growth[mcp]
pip install skene-growth[mcp,ui]
```

---

## Verifying the installation

Run the version check to confirm everything is working:

```bash
skene-growth --version
```

Expected output:

```
skene-growth 0.2.1
```

If you used `uvx`:

```bash
uvx skene-growth --version
```

---

## Next steps

Proceed to the [Quickstart](quickstart.md) to configure an LLM provider and run your first codebase analysis.
