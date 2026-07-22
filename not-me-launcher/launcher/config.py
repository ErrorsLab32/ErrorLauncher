from dataclasses import dataclass
import base64
import os
from pathlib import Path

from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
LEGACY_INSTALLATION_STATE_PATH = PROJECT_ROOT / "data" / "installation.json"
BUILT_GAME_RELEASES_TOKEN_B64 = ""

@dataclass(frozen=True)
class GitHubConfig:
    repository: str
    token: str
    connect_timeout: float = 10.0
    read_timeout: float = 60.0


@dataclass(frozen=True)
class LauncherUpdateConfig:
    repository: str = "ErrorsLab32/ErrorLauncher"
    check_interval_ms: int = 300_000


def load_github_config() -> GitHubConfig:
    values = dotenv_values(ENV_PATH)
    local_token = str(values.get("GITHUB_TOKEN") or "").strip()
    built_token = (
        base64.b64decode(BUILT_GAME_RELEASES_TOKEN_B64).decode("utf-8")
        if BUILT_GAME_RELEASES_TOKEN_B64
        else ""
    )
    return GitHubConfig(
        repository="ErrorsLab32/Not-ME",
        token=local_token or built_token,
    )


def load_launcher_update_config() -> LauncherUpdateConfig:
    return LauncherUpdateConfig(
        repository=os.getenv(
            "LAUNCHER_GITHUB_REPOSITORY",
            "ErrorsLab32/ErrorLauncher",
        ).strip()
    )
