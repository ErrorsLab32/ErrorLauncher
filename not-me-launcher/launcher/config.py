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
    credential_source: str = "none"
    connect_timeout: float = 10.0
    read_timeout: float = 60.0


@dataclass(frozen=True)
class LauncherUpdateConfig:
    repository: str = "ErrorsLab32/ErrorLauncher"
    check_interval_ms: int = 300_000


def load_github_config() -> GitHubConfig:
    values = dotenv_values(ENV_PATH)
    environment_token = os.getenv("GITHUB_TOKEN", "").strip()
    dotenv_token = str(values.get("GITHUB_TOKEN") or "").strip()
    built_token = _decode_built_game_releases_token()
    if environment_token:
        token, source = environment_token, "env"
    elif dotenv_token:
        token, source = dotenv_token, "env"
    elif built_token:
        token, source = built_token, "embedded"
    else:
        token, source = "", "none"
    return GitHubConfig(
        repository="ErrorsLab32/Not-ME",
        token=token,
        credential_source=source,
    )


def _decode_built_game_releases_token() -> str:
    if not BUILT_GAME_RELEASES_TOKEN_B64:
        return ""
    try:
        return base64.b64decode(
            BUILT_GAME_RELEASES_TOKEN_B64, validate=True
        ).decode("utf-8").strip()
    except (ValueError, UnicodeDecodeError):
        return ""


def load_launcher_update_config() -> LauncherUpdateConfig:
    return LauncherUpdateConfig(
        repository=os.getenv(
            "LAUNCHER_GITHUB_REPOSITORY",
            "ErrorsLab32/ErrorLauncher",
        ).strip()
    )
