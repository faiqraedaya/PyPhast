"""Row-level operations for inserting, deleting, copying and reordering PV/Leak rows.

All functions operate on the in-memory openpyxl Workbook. Nothing is written to
disk; the caller is responsible for saving.
"""

from __future__ import annotations

from .columns import col_letter_to_index
from .excel_io import find_sheet
from .sheet_utils import clear_range, find_last_populated_row
from . import target_layout as L

_PV_CONTEXT_LAST_COL = col_letter_to_index("G")  # A–G: Use, Study, Folder×5

_LEAK_CONTEXT_COLS = (
    col_letter_to_index(L.LEAK_COL_USE),
    col_letter_to_index(L.LEAK_COL_STUDY),
    col_letter_to_index(L.LEAK_COL_FOLDER),
    col_letter_to_index(L.LEAK_COL_PV_NAME),
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _copy_row(ws, src: int, dst: int, first_c: int, last_c: int) -> None:
    for c in range(first_c, last_c + 1):
        ws.cell(row=dst, column=c).value = ws.cell(row=src, column=c).value


def _insert_blank_row(ws, after_row: int, first_c: int, last_c: int) -> int:
    """Shift rows (after_row+1 … last_row) down by one; clear the new slot."""
    last_row = find_last_populated_row(ws, first_c, last_c, L.DATA_START_ROW)
    new_row = after_row + 1
    for r in range(last_row, new_row - 1, -1):
        _copy_row(ws, r, r + 1, first_c, last_c)
    clear_range(ws, first_c, last_c, new_row, new_row)
    return new_row


# ---------------------------------------------------------------------------
# Pressure vessel operations
# ---------------------------------------------------------------------------

def insert_pv_after(wb, after_excel_row: int) -> int:
    """Shift PV rows after *after_excel_row* down by one; return the new blank row.

    The new row inherits Study/Folder context (cols A–G) from *after_excel_row*
    and is given a placeholder name.
    """
    ws = find_sheet(wb, L.PV_SHEET_NAME)
    first_c, last_c = L.pv_scan_col_indices()
    new_row = _insert_blank_row(ws, after_excel_row, first_c, last_c)
    for c in range(first_c, _PV_CONTEXT_LAST_COL + 1):
        ws.cell(row=new_row, column=c).value = ws.cell(row=after_excel_row, column=c).value
    ws.cell(row=new_row, column=col_letter_to_index(L.PV_COL_NAME)).value = (
        "New Pressure Vessel"
    )
    return new_row


def insert_pv_copy_after(wb, src_row: int, after_row: int) -> int:
    """Insert a deep copy of *src_row* after *after_row*; return the new row."""
    ws = find_sheet(wb, L.PV_SHEET_NAME)
    first_c, last_c = L.pv_scan_col_indices()
    new_row = _insert_blank_row(ws, after_row, first_c, last_c)
    # The insert may have shifted src_row if it sat after after_row.
    actual_src = src_row + 1 if src_row > after_row else src_row
    _copy_row(ws, actual_src, new_row, first_c, last_c)
    return new_row


def delete_pv_row(wb, excel_row: int, pv_name: str) -> None:
    """Remove one PV row and shift later rows up; also removes associated leaks."""
    ws_pv = find_sheet(wb, L.PV_SHEET_NAME)
    first_c, last_c = L.pv_scan_col_indices()
    last_row = find_last_populated_row(ws_pv, first_c, last_c, L.DATA_START_ROW)
    for r in range(excel_row, last_row):
        _copy_row(ws_pv, r + 1, r, first_c, last_c)
    clear_range(ws_pv, first_c, last_c, last_row, last_row)
    if pv_name:
        _delete_leaks_for_pv(wb, pv_name)


def swap_pv_rows(wb, row1: int, row2: int) -> None:
    """Swap all cell values between two PV rows (for move-up/move-down)."""
    ws = find_sheet(wb, L.PV_SHEET_NAME)
    first_c, last_c = L.pv_scan_col_indices()
    for c in range(first_c, last_c + 1):
        v1 = ws.cell(row=row1, column=c).value
        v2 = ws.cell(row=row2, column=c).value
        ws.cell(row=row1, column=c).value = v2
        ws.cell(row=row2, column=c).value = v1


def find_prev_pv_row(wb, excel_row: int) -> int | None:
    """Return the Excel row of the nearest populated PV above *excel_row*, or None."""
    ws = find_sheet(wb, L.PV_SHEET_NAME)
    name_col = col_letter_to_index(L.PV_COL_NAME)
    for r in range(excel_row - 1, L.DATA_START_ROW - 1, -1):
        if ws.cell(row=r, column=name_col).value:
            return r
    return None


def find_next_pv_row(wb, excel_row: int) -> int | None:
    """Return the Excel row of the nearest populated PV below *excel_row*, or None."""
    ws = find_sheet(wb, L.PV_SHEET_NAME)
    first_c, last_c = L.pv_scan_col_indices()
    last_row = find_last_populated_row(ws, first_c, last_c, L.DATA_START_ROW)
    name_col = col_letter_to_index(L.PV_COL_NAME)
    for r in range(excel_row + 1, last_row + 1):
        if ws.cell(row=r, column=name_col).value:
            return r
    return None


# ---------------------------------------------------------------------------
# Leak operations
# ---------------------------------------------------------------------------

def insert_leak_after(wb, after_excel_row: int) -> int:
    """Shift leak rows after *after_excel_row* down; return the new blank row.

    Inherits PV Name, Study, Folder, Use from *after_excel_row*.
    """
    ws = find_sheet(wb, L.LEAK_SHEET_NAME)
    first_c, last_c = L.leak_scan_col_indices()
    new_row = _insert_blank_row(ws, after_excel_row, first_c, last_c)
    for col in _LEAK_CONTEXT_COLS:
        ws.cell(row=new_row, column=col).value = ws.cell(row=after_excel_row, column=col).value
    ws.cell(row=new_row, column=col_letter_to_index(L.LEAK_COL_NAME)).value = "New Leak"
    return new_row


def add_leak_for_pv(wb, pv_name: str, pv_excel_row: int) -> int:
    """Add a new leak for *pv_name* after its last existing leak (or at sheet end).

    Context (Study, Folder, Use) is taken from the PV sheet when no prior leak
    exists for this vessel.
    """
    try:
        ws_leak = find_sheet(wb, L.LEAK_SHEET_NAME)
    except Exception:  # noqa: BLE001
        return -1

    first_c, last_c = L.leak_scan_col_indices()
    last_row = find_last_populated_row(ws_leak, first_c, last_c, L.DATA_START_ROW)
    pv_col = col_letter_to_index(L.LEAK_COL_PV_NAME)

    last_pv_leak: int | None = None
    for r in range(L.DATA_START_ROW, last_row + 1):
        v = ws_leak.cell(row=r, column=pv_col).value
        if v is not None and str(v).strip() == pv_name:
            last_pv_leak = r

    if last_pv_leak is not None:
        return insert_leak_after(wb, last_pv_leak)

    # No existing leaks for this PV — append at end, seeding context from PV row.
    new_row = max(last_row + 1, L.DATA_START_ROW)
    try:
        ws_pv = find_sheet(wb, L.PV_SHEET_NAME)
        ws_leak.cell(row=new_row, column=col_letter_to_index(L.LEAK_COL_USE)).value = (
            ws_pv.cell(row=pv_excel_row, column=col_letter_to_index(L.PV_COL_USE)).value
        )
        ws_leak.cell(row=new_row, column=col_letter_to_index(L.LEAK_COL_STUDY)).value = (
            ws_pv.cell(row=pv_excel_row, column=col_letter_to_index(L.PV_COL_STUDY)).value
        )
        ws_leak.cell(row=new_row, column=col_letter_to_index(L.LEAK_COL_FOLDER)).value = (
            ws_pv.cell(row=pv_excel_row, column=col_letter_to_index(L.PV_COL_FOLDER)).value
        )
    except Exception:  # noqa: BLE001
        pass
    ws_leak.cell(row=new_row, column=col_letter_to_index(L.LEAK_COL_PV_NAME)).value = pv_name
    ws_leak.cell(row=new_row, column=col_letter_to_index(L.LEAK_COL_NAME)).value = "New Leak"
    return new_row


def delete_leak_row(wb, excel_row: int) -> None:
    """Remove one leak row and shift later rows up."""
    ws = find_sheet(wb, L.LEAK_SHEET_NAME)
    first_c, last_c = L.leak_scan_col_indices()
    last_row = find_last_populated_row(ws, first_c, last_c, L.DATA_START_ROW)
    for r in range(excel_row, last_row):
        _copy_row(ws, r + 1, r, first_c, last_c)
    clear_range(ws, first_c, last_c, last_row, last_row)


def insert_leak_copy_after(wb, src_row: int, after_row: int) -> int:
    """Insert a deep copy of leak *src_row* after *after_row*; return new row."""
    ws = find_sheet(wb, L.LEAK_SHEET_NAME)
    first_c, last_c = L.leak_scan_col_indices()
    new_row = _insert_blank_row(ws, after_row, first_c, last_c)
    actual_src = src_row + 1 if src_row > after_row else src_row
    _copy_row(ws, actual_src, new_row, first_c, last_c)
    return new_row


# ---------------------------------------------------------------------------
# Internal – bulk leak deletion used by delete_pv_row
# ---------------------------------------------------------------------------

def _delete_leaks_for_pv(wb, pv_name: str) -> None:
    try:
        ws = find_sheet(wb, L.LEAK_SHEET_NAME)
    except Exception:  # noqa: BLE001
        return
    first_c, last_c = L.leak_scan_col_indices()
    last_row = find_last_populated_row(ws, first_c, last_c, L.DATA_START_ROW)
    pv_col = col_letter_to_index(L.LEAK_COL_PV_NAME)

    rows_to_delete: list[int] = [
        r for r in range(L.DATA_START_ROW, last_row + 1)
        if (ws.cell(row=r, column=pv_col).value or "") and
           str(ws.cell(row=r, column=pv_col).value).strip() == pv_name
    ]

    offset = 0
    for orig_r in rows_to_delete:
        actual_r = orig_r - offset
        actual_last = last_row - offset
        for r in range(actual_r, actual_last):
            _copy_row(ws, r + 1, r, first_c, last_c)
        clear_range(ws, first_c, last_c, actual_last, actual_last)
        offset += 1
