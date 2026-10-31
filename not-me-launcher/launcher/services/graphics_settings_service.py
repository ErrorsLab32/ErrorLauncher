"""Apply launcher graphics presets to Unreal's per-user settings file."""

import os
from pathlib import Path
import tempfile


PRESET_LEVELS = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "epic": 3,
    "cinema": 4,
}

QUALITY_KEYS = (
    "sg.ViewDistanceQuality",
    "sg.AntiAliasingQuality",
    "sg.ShadowQuality",
    "sg.GlobalIlluminationQuality",
    "sg.ReflectionQuality",
    "sg.PostProcessQuality",
    "sg.TextureQuality",
    "sg.EffectsQuality",
    "sg.FoliageQuality",
    "sg.ShadingQuality",
    "sg.LandscapeQuality",
)
QUALITY_KEY_NAMES = {key.lower() for key in QUALITY_KEYS}


class GraphicsSettingsError(Exception):
    pass


def game_settings_path(local_app_data: Path | None = None) -> Path:
    if local_app_data is None:
        location = os.getenv("LOCALAPPDATA")
        if not location:
            raise GraphicsSettingsError("Не удалось найти папку настроек игры (LOCALAPPDATA).")
        local_app_data = Path(location)
    return local_app_data / "Alone" / "Saved" / "Config" / "Windows" / "GameUserSettings.ini"


def apply_graphics_preset(preset: str, local_app_data: Path | None = None) -> Path:
    if preset not in PRESET_LEVELS:
        raise GraphicsSettingsError("Неизвестный пресет графики.")
    path = game_settings_path(local_app_data)
    try:
        existing = path.read_text(encoding="utf-8-sig") if path.is_file() else ""
        updated = _with_preset(existing, PRESET_LEVELS[preset])
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n", dir=path.parent,
                prefix=f".{path.name}.", suffix=".tmp", delete=False,
            ) as output:
                temporary = Path(output.name)
                output.write(updated)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    except (OSError, UnicodeError) as error:
        raise GraphicsSettingsError(
            f"Не удалось сохранить настройки графики: {path}"
        ) from error
    return path


def _with_preset(existing: str, level: int) -> str:
    """Keep game-owned settings and replace only scalability group values."""
    lines: list[str] = []
    section = ""
    insert_at: int | None = None
    for line in existing.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if section == "scalabilitygroups" and insert_at is None:
                insert_at = len(lines)
            section = stripped[1:-1].lower()
            lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip().lower() if "=" in stripped else ""
        # Older test batches put sg.* in GameUserSettings, where Unreal does not
        # keep its generated scalability values. Remove those stale duplicates.
        if key in QUALITY_KEY_NAMES:
            continue
        lines.append(line)
    if section == "scalabilitygroups" and insert_at is None:
        insert_at = len(lines)
    values = [f"{key}={level}" for key in QUALITY_KEYS]
    if insert_at is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(["[ScalabilityGroups]", *values])
    else:
        lines[insert_at:insert_at] = values
    if not any(line.strip().lower() == "[/script/engine.gameusersettings]" for line in lines):
        lines.extend([
            "", "[/Script/Engine.GameUserSettings]",
            "bUseVSync=False", "FrameRateLimit=60.000000",
            "ResolutionSizeX=1920", "ResolutionSizeY=1080",
            "LastUserConfirmedResolutionSizeX=1920",
            "LastUserConfirmedResolutionSizeY=1080",
            "FullscreenMode=1", "LastConfirmedFullscreenMode=1",
            "PreferredFullscreenMode=1",
        ])
    return "\n".join(lines).rstrip("\n") + "\n"
