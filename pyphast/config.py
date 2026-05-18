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
    model_vapour_as_tvl: bool = False
    phase_col: str = ""


@dataclass
class MixtureConfig:
    sheet: str = ""
    header_row: int = 4
    start_row: int = 5
    stream_col: str = "J"
    components_first_col: str = "U"
    components_last_col: str = "AG"
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
class TimeVaryingLeakConfig:
    leak_sizes: list[LeakSizeConfig] = field(
        default_factory=lambda: [LeakSizeConfig() for _ in range(10)]
    )
    fbr_enabled: bool = False
    fbr_max_line_size_col: str = "Z"
    avg_rate_method: str = "1 Average rates"
    safety_system: str = "1 Yes"
    isolation: str = "1 Successful"
    time_to_isolation: str = ""


_MAX_RECENT = 10


@dataclass
class AppConfig:
    source_path: str = ""
    target_path: str = ""
    transfer_mode: str = "overwrite"  # "overwrite" | "append" | "skip_existing"
    import_decimal_places: int = -1   # -1 = no rounding
    recent_files: list[str] = field(default_factory=list)
    pressure_vessel: PressureVesselConfig = field(
        default_factory=PressureVesselConfig
    )
    mixture: MixtureConfig = field(default_factory=MixtureConfig)
    leak: LeakConfig = field(default_factory=LeakConfig)
    time_varying_leak: TimeVaryingLeakConfig = field(
        default_factory=TimeVaryingLeakConfig
    )


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
    tvl_raw = raw.get("time_varying_leak", {}) or {}

    pv = _populate(PressureVesselConfig(), pv_raw)
    mix = _populate(MixtureConfig(), mix_raw)
    leak = _populate_leak(LeakConfig(), leak_raw)
    tvl = _populate_tvl(TimeVaryingLeakConfig(), tvl_raw)

    raw_recent = raw.get("recent_files", [])
    recent: list[str] = [str(p) for p in raw_recent if isinstance(p, str)][:_MAX_RECENT]

    cfg = AppConfig(
        source_path=raw.get("source_path", ""),
        target_path=raw.get("target_path", ""),
        transfer_mode=raw.get("transfer_mode", "overwrite"),
        import_decimal_places=int(raw.get("import_decimal_places", -1)),
        recent_files=recent,
        pressure_vessel=pv,
        mixture=mix,
        leak=leak,
        time_varying_leak=tvl,
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


def _populate_tvl(obj: "TimeVaryingLeakConfig", raw: dict[str, Any]) -> "TimeVaryingLeakConfig":
    if "fbr_enabled" in raw:
        obj.fbr_enabled = bool(raw["fbr_enabled"])
    if "fbr_max_line_size_col" in raw:
        obj.fbr_max_line_size_col = str(raw["fbr_max_line_size_col"])
    if "avg_rate_method" in raw:
        obj.avg_rate_method = str(raw["avg_rate_method"])
    if "safety_system" in raw:
        obj.safety_system = str(raw["safety_system"])
    if "isolation" in raw:
        obj.isolation = str(raw["isolation"])
    if "time_to_isolation" in raw:
        obj.time_to_isolation = str(raw["time_to_isolation"])
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
