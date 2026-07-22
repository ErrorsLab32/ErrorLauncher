from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ReleaseAsset:
    asset_id: int
    name: str
    size: int
    content_type: str
    api_url: str
    digest: str | None = None

    @property
    def is_split_archive_part(self) -> bool:
        return re.search(r"\.7z\.\d+$", self.name, flags=re.IGNORECASE) is not None


@dataclass(frozen=True)
class ReleaseInfo:
    tag_name: str
    name: str
    body: str
    published_at: str
    assets: tuple[ReleaseAsset, ...]
    http_status: int
    removed_files: tuple[str, ...] = ()
    installed_size_bytes: int | None = None

    @property
    def archive_parts(self) -> tuple[ReleaseAsset, ...]:
        return tuple(asset for asset in self.assets if asset.is_split_archive_part)

    @property
    def total_asset_size(self) -> int:
        return sum(asset.size for asset in self.assets)

    @property
    def total_archive_size(self) -> int:
        return sum(asset.size for asset in self.archive_parts)


@dataclass(frozen=True)
class DownloadProgress:
    current_file: str
    file_index: int
    file_count: int
    downloaded_bytes: int
    total_bytes: int
    bytes_per_second: float
    retry_status: str = ""

    @property
    def percent(self) -> int:
        if self.total_bytes <= 0:
            return 0
        return min(100, int(self.downloaded_bytes * 100 / self.total_bytes))
