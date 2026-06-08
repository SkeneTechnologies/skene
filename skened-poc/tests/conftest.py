"""Shared test fixtures: isolated data dir + throwaway git repos."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from skened.config import Settings, get_settings


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


@pytest.fixture
def data_dir(tmp_path: pytest.TempPathFactory, monkeypatch) -> Path:
    """Point the daemon's settings at an isolated data dir for the test."""
    d = Path(tmp_path) / "skene-data"
    monkeypatch.setenv("SKENE_DATA_DIR", str(d))
    # Disable the working-branch monitor by default so the background poller can't add
    # surprise runs mid-test; monitor tests opt back in explicitly.
    monkeypatch.setenv("SKENE_MONITOR_ENABLED", "false")
    get_settings.cache_clear()
    settings = get_settings()
    settings.ensure_dirs()
    yield d
    get_settings.cache_clear()


@pytest.fixture
def settings(data_dir: Path) -> Settings:
    return get_settings()


@pytest.fixture
def rich_repo(tmp_path) -> Path:
    """A repo (plain dir) with files exercising several pipeline signals."""
    repo = Path(tmp_path) / "rich"
    files = {
        "app/signup/route.ts": "export async function POST(req) { /* create account, signup */ }\n",
        "src/api/billing.ts": (
            "import Stripe from 'stripe';\n"
            "app.post('/api/checkout', handler);  // subscription checkout\n"
            "// handle stripe webhook for subscription upgrades\n"
        ),
        "src/analytics.ts": (
            "posthog.capture('signup_completed');\n"
            "track('estimate_created');\n"
        ),
        "src/referral.ts": "// referral + invite share-link flow\nexport function invite() {}\n",
        "src/email.ts": "import sendgrid from '@sendgrid/mail';\nexport function sendEmail() {}\n",
        "README.md": "# Rich demo\n",
    }
    for rel, content in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return repo


@pytest.fixture
def git_repo(tmp_path) -> Path:
    """A repo with an initial commit on the default branch plus a 'feature' branch."""
    repo = Path(tmp_path) / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Tester")
    (repo / "README.md").write_text("# Sample project\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial commit")

    _git(repo, "branch", "feature")
    # Diverge the feature branch so it has a distinct HEAD commit.
    _git(repo, "checkout", "feature")
    (repo / "feature.txt").write_text("feature work\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "feature work")
    _git(repo, "checkout", "main")
    return repo
