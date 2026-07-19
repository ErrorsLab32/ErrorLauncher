from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
LEGACY_INSTALLATION_STATE_PATH = PROJECT_ROOT / "data" / "installation.json"

@dataclass(frozen=True)
class GitHubConfig:
    repository: str
    token: str
    connect_timeout: float = 10.0
    read_timeout: float = 60.0


@dataclass(frozen=True)
class LauncherUpdateConfig:
    repository: str = "ErrorsLab32/ErrorLauncher"
    check_interval_ms: int = 3_600_000


def load_github_config() -> GitHubConfig:
    values = dotenv_values(ENV_PATH)
    return GitHubConfig(
        repository="ErrorsLab32/Not-ME",
        token=str(values.get("GITHUB_TOKEN") or "").strip(),
    )


def load_launcher_update_config() -> LauncherUpdateConfig:
    return LauncherUpdateConfig(
        repository=os.getenv(
            "LAUNCHER_GITHUB_REPOSITORY",
            "ErrorsLab32/ErrorLauncher",
        ).strip()
    )
