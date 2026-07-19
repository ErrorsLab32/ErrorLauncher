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
    check_interval_ms: int = 3_600_000


@dataclass(frozen=True)
class AuthConfig:
    api_base_url: str = "http://192.168.55.100:8000"
    connect_timeout: float = 10.0
    read_timeout: float = 30.0


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


def load_auth_config() -> AuthConfig:
    values = dotenv_values(ENV_PATH)
    configured_url = os.getenv(
        "API_BASE_URL",
        str(values.get("API_BASE_URL") or "http://192.168.55.100:8000"),
    ).strip()
    api_base_url = os.getenv("NOT_ME_API_BASE_URL", "").strip() or configured_url
    return AuthConfig(api_base_url=api_base_url.rstrip("/"))
