from enum import Enum, auto


class InstallationState(Enum):
    NotInstalled = auto()
    CheckingForUpdates = auto()
    ReadyToDownload = auto()
    Downloading = auto()
    Downloaded = auto()
    Installing = auto()
    ReadyToPlay = auto()
    UpdateAvailable = auto()
    Error = auto()
