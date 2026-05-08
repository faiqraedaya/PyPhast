"""Cross-tab validation: check that pressure-vessel materials are defined as
mixtures, and warn about the gap. Designed to be unobtrusive — the user
asked for "seamless and not annoying", so failures here never block a transfer.
"""

from __future__ import annotations

from openpyxl.workbook.workbook import Workbook

from .columns import col_letter_to_index
from .excel_io import find_sheet
from .mixture import MixtureSourceConfig
from .pressure_vessel import (
    PressureVesselSourceConfig,
    TransferReport,
)
from .sheet_utils import iter_populated_rows


def collect_mixture_stream_names(
    src_wb: Workbook, mix_cfg: MixtureSourceConfig
) -> set[str]:
    """Return the set of stream names defined in the source mixtures table."""
    ws = find_sheet(src_wb, mix_cfg.sheet)
    stream_idx = col_letter_to_index(mix_cfg.stream_col)
    out: set[str] = set()
    for r in iter_populated_rows(ws, stream_idx, mix_cfg.start_row):
        v = ws.cell(row=r, column=stream_idx).value
        if v is None:
            continue
        s = str(v).strip()
        if s:
            out.add(s)
    return out


def collect_pv_stream_refs(
    src_wb: Workbook, pv_cfg: PressureVesselSourceConfig
) -> set[str]:
    """Return the set of stream/material references used by pressure vessels."""
    ws = find_sheet(src_wb, pv_cfg.sheet)
    name_idx = col_letter_to_index(pv_cfg.name_col)
    stream_idx = col_letter_to_index(pv_cfg.stream_col)
    out: set[str] = set()
    for r in iter_populated_rows(ws, name_idx, pv_cfg.start_row):
        v = ws.cell(row=r, column=stream_idx).value
        if v is None:
            continue
        s = str(v).strip()
        if s:
            out.add(s)
    return out


def warn_unresolved_pv_streams(
    pv_refs: set[str], mix_streams: set[str], report: TransferReport
) -> None:
    """Append a warning if PV references are missing from the mixtures source."""
    missing = sorted(pv_refs - mix_streams)
    if missing:
        report.warnings.append(
            "Pressure vessel material(s) not defined in the Mixtures source: "
            + ", ".join(repr(m) for m in missing)
            + ". Define them on the Mixtures tab before importing into Phast."
        )
