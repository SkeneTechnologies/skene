# Installation

How to install skene using uvx, pip, or from source.

## Prerequisites

- **Python 3.11 or later.** Check your version with `python3 --version`.

---

## Option 1: uvx (Recommended)

[uvx](https://docs.astral.sh/uv/) runs Python CLI tools without installing them globally. This is the fastest way to start using skene.

If you don't have `uv` installed yet:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then run any skene command directly:

```bash
uvx skene analyze .
uvx skene plan
```

No `pip install` needed. `uvx` downloads the package into an isolated environment on first run and caches it for subsequent calls.

---

## Option 2: pip

Install skene into your current Python environment:

```bash
pip install skene
```

After installation, the `skene` and `skene` commands are available on your PATH:

```bash
skene analyze .
skene chat
```

---

## Option 3: From source

Clone the repository and install in development mode:

```bash
git clone https://github.com/SkeneTechnologies/skene.git
cd skene
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
| `mcp` | MCP server support (`skene-mcp` entry point). Adds `mcp>=1.0.0` and `xxhash>=3.0`. |
| `ui` | Interactive terminal prompts via `questionary>=2.0`. |

```bash
# With uvx (use --from to specify extras)
uvx --from "skene[mcp]" skene-mcp

# With uv
uv pip install skene[mcp]

# With pip
pip install skene[mcp]
pip install skene[mcp,ui]
```

---

## Verifying the installation

Run the version check to confirm everything is working:

```bash
skene --version
```

Expected output:

```
skene 0.2.1
```

If you used `uvx`:

```bash
uvx skene --version
```

---

## Next steps

Proceed to the [Quickstart](quickstart.md) to configure an LLM provider and run your first codebase analysis.
