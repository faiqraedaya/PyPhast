"""User-facing settings persisted as JSON across sessions.

Stored in a platform-appropriate location via Qt's QStandardPaths:
- Linux:   ~/.config/PyPhast/config.json
- macOS:   ~/Library/Application Support/PyPhast/config.json
- Windows: %APPDATA%/PyPhast/config.json
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from PySide6.QtCore import QStandardPaths

from . import __app_name__


@dataclass
class PressureVesselConfig:
    sheet: str = ""
    header_row: int = 4
    start_row: int = 5
    name_col: str = "A"
    stream_col: str = "B"
    pressure_col: str = "C"
    temperature_col: str = "D"
    inventory_col: str = "E"
    inventory_mode: str = "mass"  # "mass" | "volume"
    assume_unlimited: bool = False


@dataclass
class MixtureConfig:
    sheet: str = ""
    header_row: int = 4
    start_row: int = 5
    stream_col: str = "A"
    components_first_col: str = "B"
    components_last_col: str = "Z"
    composition_basis: str = "mole"  # "mole" | "mass"
    smart_match: bool = True
    skip_zero: bool = True
    user_overrides: dict[str, str] = field(default_factory=dict)


@dataclass
class LeakSizeConfig:
    name: str = ""
    orifice_diameter: str = ""  # stored as string; empty = not configured


@dataclass
class LeakConfig:
    leak_sizes: list[LeakSizeConfig] = field(
        default_factory=lambda: [LeakSizeConfig() for _ in range(10)]
    )
    fbr_enabled: bool = False
    fbr_max_line_size_col: str = "Z"


@dataclass
class AppConfig:
    source_path: str = ""
    target_path: str = ""
    transfer_mode: str = "overwrite"  # "overwrite" | "append"
    import_decimal_places: int = -1   # -1 = no rounding
    pressure_vessel: PressureVesselConfig = field(
        default_factory=PressureVesselConfig
    )
    mixture: MixtureConfig = field(default_factory=MixtureConfig)
    leak: LeakConfig = field(default_factory=LeakConfig)


# ---------------------------------------------------------------------------


def config_path() -> Path:
    base = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppConfigLocation
    )
    if not base:
        base = str(Path.home() / ".config" / __app_name__)
    p = Path(base) / "config.json"
    return p


def load_config() -> AppConfig:
    p = config_path()
    if not p.exists():
        return AppConfig()
    try:
        with p.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError):
        return AppConfig()
    return _from_dict(raw)


def save_config(cfg: AppConfig) -> None:
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, indent=2)


# ---------------------------------------------------------------------------


def _from_dict(raw: dict[str, Any]) -> AppConfig:
    pv_raw = raw.get("pressure_vessel", {}) or {}
    mix_raw = raw.get("mixture", {}) or {}
    leak_raw = raw.get("leak", {}) or {}

    pv = _populate(PressureVesselConfig(), pv_raw)
    mix = _populate(MixtureConfig(), mix_raw)
    leak = _populate_leak(LeakConfig(), leak_raw)

    cfg = AppConfig(
        source_path=raw.get("source_path", ""),
        target_path=raw.get("target_path", ""),
        transfer_mode=raw.get("transfer_mode", "overwrite"),
        import_decimal_places=int(raw.get("import_decimal_places", -1)),
        pressure_vessel=pv,
        mixture=mix,
        leak=leak,
    )
    return cfg


def _populate(obj, raw: dict[str, Any]):
    valid = {f.name for f in fields(obj)}
    for k, v in raw.items():
        if k in valid:
            setattr(obj, k, v)
    return obj


def _populate_leak(obj: "LeakConfig", raw: dict[str, Any]) -> "LeakConfig":
    if "fbr_enabled" in raw:
        obj.fbr_enabled = bool(raw["fbr_enabled"])
    if "fbr_max_line_size_col" in raw:
        obj.fbr_max_line_size_col = str(raw["fbr_max_line_size_col"])
    raw_sizes = raw.get("leak_sizes")
    if isinstance(raw_sizes, list):
        sizes: list[LeakSizeConfig] = []
        for item in raw_sizes:
            if isinstance(item, dict):
                sizes.append(LeakSizeConfig(
                    name=str(item.get("name", "")),
                    orifice_diameter=str(item.get("orifice_diameter", "")),
                ))
            else:
                sizes.append(LeakSizeConfig())
        while len(sizes) < 10:
            sizes.append(LeakSizeConfig())
        obj.leak_sizes = sizes[:10]
    return obj
