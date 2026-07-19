from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
LEGACY_INSTALLATION_STATE_PATH = PROJECT_ROOT / "data" / "installation.json"

load_dotenv(ENV_PATH)


@dataclass(frozen=True)
class GitHubConfig:
    repository: str
    token: str
    connect_timeout: float = 10.0
    read_timeout: float = 60.0


def load_github_config() -> GitHubConfig:
    return GitHubConfig(
        repository=os.getenv("GITHUB_REPOSITORY", "ErrorsLab32/Not-ME").strip(),
        token=os.getenv("GITHUB_TOKEN", "").strip(),
    )
