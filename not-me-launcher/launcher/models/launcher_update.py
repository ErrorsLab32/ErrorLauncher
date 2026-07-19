from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path


class LauncherUpdateState(Enum):
    Idle = auto()
    Checking = auto()
    UpdateAvailable = auto()
    WaitingForGameOperation = auto()
    Downloading = auto()
    Verifying = auto()
    ReadyToApply = auto()
    Applying = auto()
    Restarting = auto()
    Error = auto()


@dataclass(frozen=True)
class LauncherUpdateManifest:
    version: str
    platform: str
    asset: str
    entrypoint: Path
    sha256: str


@dataclass(frozen=True)
class LauncherUpdateAsset:
    name: str
    url: str
    size: int
    digest: str | None


@dataclass(frozen=True)
class LauncherUpdateRelease:
    tag_name: str
    manifest: LauncherUpdateManifest
    package: LauncherUpdateAsset


@dataclass(frozen=True)
class LauncherUpdateProgress:
    downloaded_bytes: int
    total_bytes: int

    @property
    def percent(self) -> int:
        if self.total_bytes <= 0:
            return 0
        return min(100, int(self.downloaded_bytes * 100 / self.total_bytes))
