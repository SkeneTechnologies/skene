# Releasing

This monorepo contains two independently released packages. Each has its own CI/CD pipeline, versioning, and distribution channel.

| Package | Directory | Distribution | Tag pattern |
|--------|-----------|-------------|-------------|
| Python CLI | `src/skene/` | [PyPI](https://pypi.org/project/skene/) | `v*` (e.g. `v0.3.0`) |
| TUI | `tui/` | [GitHub Releases](https://github.com/SkeneTechnologies/skene/releases) | `tui-v*` (e.g. `tui-v0.3.0`) |

## Pre-release versions

Tags containing `rc`, `b`, `beta`, `alpha`, or `a` followed by a number are treated as pre-releases:

- `tui-v0.3.0rc1` / `v0.3.0rc1` — release candidate
- `tui-v0.3.0b1` / `v0.3.0b1` — beta
- `tui-v0.3.0a1` / `v0.3.0a1` — alpha

Pre-release TUI builds are automatically marked as pre-release on GitHub (not "latest"). Pre-release Python packages are marked as such on PyPI following [PEP 440](https://peps.python.org/pep-0440/).

---

## Python CLI

### Files to update

1. **`pyproject.toml`** — `version = "X.Y.Z"`
2. **`src/skene/__init__.py`** — `__version__ = "X.Y.Z"`

### Steps

```bash
# 1. Update version in pyproject.toml (and __init__.py if applicable)
#    Example: "0.2.1" for stable, "0.3.0rc1" for release candidate

# 2. Commit the version bump
git add pyproject.toml src/skene/__init__.py
git commit -m "Bump skene version to X.Y.Z"
git push origin main

# 3. Create a GitHub Release (this triggers PyPI publishing)
gh release create vX.Y.Z --title "vX.Y.Z" --generate-notes

# For pre-releases:
gh release create vX.Y.Zrc1 --prerelease --title "vX.Y.Zrc1" --generate-notes
```

### What happens

1. Creating the GitHub Release triggers `.github/workflows/publish.yml`
2. The workflow builds the Python package and publishes to PyPI via trusted publishing
3. Users can install with `pip install skene` or `uvx skene`

---

## TUI

### Version handling

The binary version is automatically injected via `-ldflags` at build time — `tui/internal/constants/constants.go` does _not_ need to be updated manually for the TUI version.

The TUI pins the Python CLI version it depends on via `GrowthPackageVersion` in `tui/internal/constants/constants.go`. When releasing a new Python CLI version that the TUI should use, update this constant.

- **Stable releases:** Update `VERSION` in `tui/Makefile` (e.g. `VERSION=tui-v0.3.0`). This is used by the no-Go fallback download path and for local builds, and should always point to the latest stable release. If the pinned Python CLI version needs bumping, also update `GrowthPackageVersion` in `tui/internal/constants/constants.go`.
- **Pre-releases:** Do _not_ update the Makefile. The CI workflow reads the version from the git tag directly, so the Makefile should keep pointing to the latest stable release.

### Stable release steps

```bash
# 1. Update VERSION in tui/Makefile
#    Set it to the tag you're about to create, e.g. VERSION=tui-v0.3.0
# 2. If needed, update GrowthPackageVersion in tui/internal/constants/constants.go
#    to match the Python CLI version the TUI should use

# 3. Commit the version bump
git add tui/Makefile tui/internal/constants/constants.go
git commit -m "Bump TUI version to X.Y.Z"
git push origin main

# 3. Tag and push (this triggers the release workflow)
git tag tui-vX.Y.Z
git push origin tui-vX.Y.Z
```

### Pre-release steps

```bash
# No file changes needed — just tag and push
git tag tui-vX.Y.Za1
git push origin tui-vX.Y.Za1
```

### What happens

1. Pushing the tag triggers `.github/workflows/tui-release.yml`
2. The workflow builds cross-platform binaries:
   - `skene-darwin-amd64` (macOS Intel)
   - `skene-darwin-arm64` (macOS Apple Silicon)
   - `skene-linux-amd64`
   - `skene-linux-arm64`
   - `skene-windows-amd64`
   - `skene-windows-arm64`
3. Binaries are packaged (`.tar.gz` for macOS/Linux, `.zip` for Windows) and attached to a GitHub Release

---

## CI pipelines

Both packages have CI that runs on push/PR to `main`:

| Workflow | File | Triggers on |
|----------|------|-------------|
| Python CI | `.github/workflows/ci.yml` | Push/PR, ignores `tui/**` changes |
| TUI CI | `.github/workflows/tui-ci.yml` | Push/PR affecting `tui/**` only |

The CI pipelines run independently — Python changes don't trigger Go CI and vice versa.

---

## Checklist

### Python release
- [ ] Version bumped in `pyproject.toml`
- [ ] Version bumped in `src/skene/__init__.py`
- [ ] Changes committed and pushed to `main`
- [ ] GitHub Release created (`gh release create vX.Y.Z`)
- [ ] Verify on [PyPI](https://pypi.org/project/skene/)

### TUI stable release
- [ ] `VERSION` updated in `tui/Makefile`
- [ ] `GrowthPackageVersion` updated in `tui/internal/constants/constants.go` (if Python CLI version changed)
- [ ] Changes committed and pushed to `main`
- [ ] Tag created and pushed (`git tag tui-vX.Y.Z && git push origin tui-vX.Y.Z`)
- [ ] Verify on [GitHub Releases](https://github.com/SkeneTechnologies/skene/releases)

### TUI pre-release
- [ ] Tag created and pushed (`git tag tui-vX.Y.Za1 && git push origin tui-vX.Y.Za1`)
- [ ] Verify on [GitHub Releases](https://github.com/SkeneTechnologies/skene/releases)
