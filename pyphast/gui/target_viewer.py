"""PhastEditorWidget – primary in-memory editor for the Phast target workbook."""

from __future__ import annotations

from typing import NamedTuple

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QMenu,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..core import target_layout as L
from ..core.columns import col_letter_to_index
from ..core.excel_io import find_sheet
from ..core.sheet_utils import find_last_populated_row


# ---------------------------------------------------------------------------
# Column specifications
# ---------------------------------------------------------------------------

class _ColSpec(NamedTuple):
    header: str
    col_letter: str
    numeric: bool = False  # True ⇒ allow text→float coercion; else preserve as string


_PV_COLS: list[_ColSpec] = [
    _ColSpec("Use",          L.PV_COL_USE),
    _ColSpec("Study",        L.PV_COL_STUDY),
    _ColSpec("Folder",       L.PV_COL_FOLDER),
    _ColSpec("Name",         L.PV_COL_NAME),
    _ColSpec("Material",     L.PV_COL_MATERIAL),
    _ColSpec("Spec. Vol",    L.PV_COL_SPECIFY_VOLUME),
    _ColSpec("Mass Inv",     L.PV_COL_MASS_INVENTORY,    True),
    _ColSpec("Vol Inv",      L.PV_COL_VOLUME_INVENTORY,  True),
    _ColSpec("Mat. Track",   L.PV_COL_MATERIAL_TO_TRACK),
    _ColSpec("Temp (°C)",    L.PV_COL_TEMPERATURE,       True),
    _ColSpec("Press (barg)", L.PV_COL_PRESSURE_GAUGE,    True),
]

_LEAK_COLS: list[_ColSpec] = [
    _ColSpec("Use",          L.LEAK_COL_USE),
    _ColSpec("Study",        L.LEAK_COL_STUDY),
    _ColSpec("Folder",       L.LEAK_COL_FOLDER),
    _ColSpec("PV Name",      L.LEAK_COL_PV_NAME),
    _ColSpec("Leak Name",    L.LEAK_COL_NAME),
    _ColSpec("Orifice (mm)", L.LEAK_COL_ORIFICE_DIAMETER, True),
    _ColSpec("Release Dir.", L.LEAK_COL_OUTDOOR_RELEASE_DIRECTION),
]

_MIX_COLS: list[_ColSpec] = [
    _ColSpec("Use",          L.MIX_COL_USE),
    _ColSpec("Stream Name",  L.MIX_COL_NAME),
    _ColSpec("Component",    L.MIX_COL_COMPONENT),
    _ColSpec("Mass %",       L.MIX_COL_MASS,  True),
    _ColSpec("Mole %",       L.MIX_COL_MOLE,  True),
    _ColSpec("Prop. Method", L.MIX_COL_PROPERTY_METHOD),
]

_TVL_COLS: list[_ColSpec] = [
    _ColSpec("Use",            L.TVL_COL_USE),
    _ColSpec("Study",          L.TVL_COL_STUDY),
    _ColSpec("Folder",         L.TVL_COL_FOLDER),
    _ColSpec("PV Name",        L.TVL_COL_PV_NAME),
    _ColSpec("TVL Name",       L.TVL_COL_NAME),
    _ColSpec("Orifice (mm)",   L.TVL_COL_ORIFICE_DIAMETER, True),
    _ColSpec("Release Dir.",   L.TVL_COL_OUTDOOR_RELEASE_DIRECTION),
    _ColSpec("Avg Rate Method",L.TVL_COL_AVG_RATE_METHOD),
    _ColSpec("Safety System",  L.TVL_COL_SAFETY_SYSTEM),
    _ColSpec("Isolation?",     L.TVL_COL_ISOLATION),
    _ColSpec("Time to Iso. (s)",L.TVL_COL_TIME_TO_ISOLATION, True),
]

_PV_KEY_COL   = L.PV_COL_NAME
_LEAK_KEY_COL = L.LEAK_COL_PV_NAME
_TVL_KEY_COL  = L.TVL_COL_PV_NAME
_MIX_KEY_COL  = L.MIX_COL_COMPONENT

_PV_NAME_COL_IDX   = next(i for i, c in enumerate(_PV_COLS)   if c.col_letter == L.PV_COL_NAME)
_LEAK_NAME_COL_IDX = next(i for i, c in enumerate(_LEAK_COLS) if c.col_letter == L.LEAK_COL_NAME)
_TVL_NAME_COL_IDX  = next(i for i, c in enumerate(_TVL_COLS)  if c.col_letter == L.TVL_COL_NAME)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_populated(v) -> bool:
    if v is None:
        return False
    if isinstance(v, str) and not v.strip():
        return False
    return True


def _to_write_value(text: str, numeric: bool = False):
    """Coerce edit-box text to a workbook value.

    For numeric columns, blank → None and parseable input → float; unparseable
    text is kept as-is so the user can see and fix it. For non-numeric columns
    the text is preserved verbatim — critical for dropdown fields like Phast's
    ``"0 No"`` / ``"1 Yes"`` whose strings would otherwise be silently turned
    into the floats ``0.0`` / ``1.0`` and rejected by Phast on import.
    """
    stripped = text.strip()
    if not stripped:
        return None
    if not numeric:
        return stripped
    try:
        return float(stripped)
    except ValueError:
        return stripped


def _make_table(cols: list[_ColSpec]) -> QTableWidget:
    table = QTableWidget(0, len(cols))
    table.setHorizontalHeaderLabels([c.header for c in cols])
    hh = table.horizontalHeader()
    hh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    hh.setStretchLastSection(True)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
    table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
    table.setWordWrap(False)
    return table


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

class TargetViewerWidget(QGroupBox):
    """Primary editor: PV / Leak / Mixture tables with cut/copy/paste support."""

    workbookModified        = Signal()
    pvInsertRequested       = Signal(int)        # after_excel_row
    pvDeleteRequested       = Signal(int, str)   # excel_row, pv_name
    pvBatchDeleteRequested  = Signal(object)     # list[(excel_row, pv_name)]
    leakInsertRequested     = Signal(int)        # after_excel_row
    leakDeleteRequested     = Signal(int)        # excel_row
    leakBatchDeleteRequested = Signal(object)    # list[excel_row]
    tvlInsertRequested      = Signal(int)        # after_excel_row
    tvlDeleteRequested      = Signal(int)        # excel_row
    tvlBatchDeleteRequested  = Signal(object)    # list[excel_row]
    pvPasteRowRequested     = Signal(int, int, bool, str)  # src_row, after_row, is_cut, pv_name
    leakPasteRowRequested   = Signal(int, int, bool)       # src_row, after_row, is_cut
    tvlPasteRowRequested    = Signal(int, int, bool)       # src_row, after_row, is_cut
    countsUpdated           = Signal(int, int, int)  # pv_n, leak_n, mix_n

    def __init__(self, parent=None) -> None:
        super().__init__("Workbook Editor", parent)
        self._wb = None
        self._updating = False
        self._row_clipboard: dict | None = None  # {"type", "excel_row", "is_cut", "pv_name"?}

        self._pv_row_map:   list[int] = []
        self._leak_row_map: list[int] = []
        self._tvl_row_map:  list[int] = []
        self._mix_row_map:  list[int] = []

        self._build_ui()

    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        self._pv_table   = _make_table(_PV_COLS)
        self._leak_table = _make_table(_LEAK_COLS)
        self._tvl_table  = _make_table(_TVL_COLS)
        self._mix_table  = _make_table(_MIX_COLS)

        # Context menus
        self._pv_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._pv_table.customContextMenuRequested.connect(self._on_pv_context_menu)

        self._leak_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._leak_table.customContextMenuRequested.connect(self._on_leak_context_menu)

        self._tvl_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tvl_table.customContextMenuRequested.connect(self._on_tvl_context_menu)

        self._mix_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._mix_table.customContextMenuRequested.connect(
            lambda pos: self._on_generic_context_menu(self._mix_table, pos)
        )

        # Right-clicking the row-number header shows the same context menu
        for table, handler in (
            (self._pv_table,   self._on_pv_context_menu),
            (self._leak_table, self._on_leak_context_menu),
            (self._tvl_table,  self._on_tvl_context_menu),
            (self._mix_table,  lambda pos: self._on_generic_context_menu(self._mix_table, pos)),
        ):
            vh = table.verticalHeader()
            vh.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            vh.customContextMenuRequested.connect(
                lambda pos, t=table, h=handler: self._on_vertical_header_context_menu(pos, t, h)
            )

        self._tab_widget = QTabWidget()
        self._tab_widget.addTab(self._pv_table,   "Pressure Vessels")
        self._tab_widget.addTab(self._leak_table, "Leaks")
        self._tab_widget.addTab(self._tvl_table,  "Time Varying Leaks")
        self._tab_widget.addTab(self._mix_table,  "Mixtures")
        layout.addWidget(self._tab_widget)

        self._pv_table.cellChanged.connect(
            lambda r, c: self._on_cell_changed(
                L.PV_SHEET_NAME, _PV_COLS, self._pv_row_map, self._pv_table, r, c,
            )
        )
        self._leak_table.cellChanged.connect(
            lambda r, c: self._on_cell_changed(
                L.LEAK_SHEET_NAME, _LEAK_COLS, self._leak_row_map, self._leak_table, r, c,
            )
        )
        self._tvl_table.cellChanged.connect(
            lambda r, c: self._on_cell_changed(
                L.TVL_SHEET_NAME, _TVL_COLS, self._tvl_row_map, self._tvl_table, r, c,
            )
        )
        self._mix_table.cellChanged.connect(
            lambda r, c: self._on_cell_changed(
                L.MIX_SHEET_NAME, _MIX_COLS, self._mix_row_map, self._mix_table, r, c,
            )
        )

        footer_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setMaximumWidth(80)
        refresh_btn.setToolTip("Re-read from the current workbook")
        refresh_btn.clicked.connect(self.refresh)
        footer_row.addStretch(1)
        footer_row.addWidget(refresh_btn)
        layout.addLayout(footer_row)

        # Keyboard shortcuts (scoped to this widget and its children)
        ctx = Qt.ShortcutContext.WidgetWithChildrenShortcut
        for key, slot in (
            (QKeySequence.StandardKey.Copy,  self._on_copy),
            (QKeySequence.StandardKey.Cut,   self._on_cut),
            (QKeySequence.StandardKey.Paste, self._on_paste),
        ):
            sc = QShortcut(key, self)
            sc.setContext(ctx)
            sc.activated.connect(slot)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_workbook(self, wb) -> None:
        self._wb = wb
        self.refresh()

    def refresh(self) -> None:
        if self._wb is None:
            self._clear_all()
            self.countsUpdated.emit(0, 0, 0)
            return
        try:
            self._load_tab(
                self._wb, L.PV_SHEET_NAME,   _PV_COLS,   _PV_KEY_COL,
                L.pv_scan_col_indices,   self._pv_table,   self._pv_row_map,
            )
            self._load_tab(
                self._wb, L.LEAK_SHEET_NAME, _LEAK_COLS, _LEAK_KEY_COL,
                L.leak_scan_col_indices, self._leak_table, self._leak_row_map,
            )
            self._load_tab(
                self._wb, L.TVL_SHEET_NAME,  _TVL_COLS,  _TVL_KEY_COL,
                L.tvl_scan_col_indices,  self._tvl_table,  self._tvl_row_map,
            )
            self._load_tab(
                self._wb, L.MIX_SHEET_NAME,  _MIX_COLS,  _MIX_KEY_COL,
                L.mix_scan_col_indices,  self._mix_table,  self._mix_row_map,
            )
            self.countsUpdated.emit(
                self._pv_table.rowCount(),
                self._leak_table.rowCount(),
                self._mix_table.rowCount(),
            )
        except Exception:  # noqa: BLE001
            self._clear_all()
            self.countsUpdated.emit(0, 0, 0)

    # ------------------------------------------------------------------
    # Context menus
    # ------------------------------------------------------------------

    def _selected_table_rows(self, table: QTableWidget, row_map: list[int]) -> list[int]:
        """Return sorted unique table row indices that are currently selected."""
        row_set: set[int] = set()
        for r in table.selectedRanges():
            for row in range(r.topRow(), r.bottomRow() + 1):
                row_set.add(row)
        return sorted(r for r in row_set if r < len(row_map))

    def _on_pv_context_menu(self, pos) -> None:
        table_row = self._pv_table.rowAt(pos.y())
        menu = QMenu(self)
        if 0 <= table_row < len(self._pv_row_map):
            excel_row = self._pv_row_map[table_row]
            name_item = self._pv_table.item(table_row, _PV_NAME_COL_IDX)
            pv_name = name_item.text() if name_item else ""
            menu.addAction("Add Pressure Vessel Above",
                           lambda: self.pvInsertRequested.emit(excel_row - 1))
            menu.addAction("Add Pressure Vessel Below",
                           lambda: self.pvInsertRequested.emit(excel_row))
            menu.addAction("Delete Pressure Vessel",
                           lambda: self.pvDeleteRequested.emit(excel_row, pv_name))
            sel = self._selected_table_rows(self._pv_table, self._pv_row_map)
            if len(sel) >= 2:
                pairs = [
                    (self._pv_row_map[r],
                     self._pv_table.item(r, _PV_NAME_COL_IDX).text()
                     if self._pv_table.item(r, _PV_NAME_COL_IDX) else "")
                    for r in sel
                ]
                menu.addAction(
                    f"Delete Selected Rows ({len(sel)})",
                    lambda p=pairs: self.pvBatchDeleteRequested.emit(p),
                )
            menu.addSeparator()
            menu.addAction("Copy Row",
                           lambda: self._set_row_clipboard("pv", excel_row, pv_name, False))
            menu.addAction("Cut Row",
                           lambda: self._set_row_clipboard("pv", excel_row, pv_name, True))
            if self._row_clipboard and self._row_clipboard["type"] == "pv":
                clip = self._row_clipboard
                menu.addAction("Paste Row Above",
                               lambda: self._emit_pv_paste_row(clip, excel_row - 1))
                menu.addAction("Paste Row Below",
                               lambda: self._emit_pv_paste_row(clip, excel_row))
            menu.addSeparator()
        self._add_clipboard_actions(menu, self._pv_table,
                                    _PV_COLS, self._pv_row_map, L.PV_SHEET_NAME)
        menu.exec(self._pv_table.viewport().mapToGlobal(pos))

    def _on_leak_context_menu(self, pos) -> None:
        table_row = self._leak_table.rowAt(pos.y())
        menu = QMenu(self)
        if 0 <= table_row < len(self._leak_row_map):
            excel_row = self._leak_row_map[table_row]
            menu.addAction("Add Leak Above",
                           lambda: self.leakInsertRequested.emit(excel_row - 1))
            menu.addAction("Add Leak Below",
                           lambda: self.leakInsertRequested.emit(excel_row))
            menu.addAction("Delete Leak",
                           lambda: self.leakDeleteRequested.emit(excel_row))
            sel = self._selected_table_rows(self._leak_table, self._leak_row_map)
            if len(sel) >= 2:
                rows = [self._leak_row_map[r] for r in sel]
                menu.addAction(
                    f"Delete Selected Rows ({len(sel)})",
                    lambda r=rows: self.leakBatchDeleteRequested.emit(r),
                )
            menu.addSeparator()
            menu.addAction("Copy Row",
                           lambda: self._set_row_clipboard("leak", excel_row, "", False))
            menu.addAction("Cut Row",
                           lambda: self._set_row_clipboard("leak", excel_row, "", True))
            if self._row_clipboard and self._row_clipboard["type"] == "leak":
                clip = self._row_clipboard
                menu.addAction("Paste Row Above",
                               lambda: self._emit_leak_paste_row(clip, excel_row - 1))
                menu.addAction("Paste Row Below",
                               lambda: self._emit_leak_paste_row(clip, excel_row))
            menu.addSeparator()
        self._add_clipboard_actions(menu, self._leak_table,
                                    _LEAK_COLS, self._leak_row_map, L.LEAK_SHEET_NAME)
        menu.exec(self._leak_table.viewport().mapToGlobal(pos))

    def _on_tvl_context_menu(self, pos) -> None:
        table_row = self._tvl_table.rowAt(pos.y())
        menu = QMenu(self)
        if 0 <= table_row < len(self._tvl_row_map):
            excel_row = self._tvl_row_map[table_row]
            menu.addAction("Add Time Varying Leak Above",
                           lambda: self.tvlInsertRequested.emit(excel_row - 1))
            menu.addAction("Add Time Varying Leak Below",
                           lambda: self.tvlInsertRequested.emit(excel_row))
            menu.addAction("Delete Time Varying Leak",
                           lambda: self.tvlDeleteRequested.emit(excel_row))
            sel = self._selected_table_rows(self._tvl_table, self._tvl_row_map)
            if len(sel) >= 2:
                rows = [self._tvl_row_map[r] for r in sel]
                menu.addAction(
                    f"Delete Selected Rows ({len(sel)})",
                    lambda r=rows: self.tvlBatchDeleteRequested.emit(r),
                )
            menu.addSeparator()
            menu.addAction("Copy Row",
                           lambda: self._set_row_clipboard("tvl", excel_row, "", False))
            menu.addAction("Cut Row",
                           lambda: self._set_row_clipboard("tvl", excel_row, "", True))
            if self._row_clipboard and self._row_clipboard["type"] == "tvl":
                clip = self._row_clipboard
                menu.addAction("Paste Row Above",
                               lambda: self._emit_tvl_paste_row(clip, excel_row - 1))
                menu.addAction("Paste Row Below",
                               lambda: self._emit_tvl_paste_row(clip, excel_row))
            menu.addSeparator()
        self._add_clipboard_actions(menu, self._tvl_table,
                                    _TVL_COLS, self._tvl_row_map, L.TVL_SHEET_NAME)
        menu.exec(self._tvl_table.viewport().mapToGlobal(pos))

    def _on_generic_context_menu(self, table, pos) -> None:
        """Context menu with only copy/cut/paste (used by Mixture table)."""
        if table is self._mix_table:
            cols, row_map, sheet = _MIX_COLS, self._mix_row_map, L.MIX_SHEET_NAME
        else:
            return
        menu = QMenu(self)
        self._add_clipboard_actions(menu, table, cols, row_map, sheet)
        menu.exec(table.viewport().mapToGlobal(pos))

    def _set_row_clipboard(self, type_: str, excel_row: int, pv_name: str, is_cut: bool) -> None:
        self._row_clipboard = {"type": type_, "excel_row": excel_row, "pv_name": pv_name, "is_cut": is_cut}

    def _emit_pv_paste_row(self, clip: dict, after_row: int) -> None:
        self.pvPasteRowRequested.emit(clip["excel_row"], after_row, clip["is_cut"], clip["pv_name"])
        if clip["is_cut"]:
            self._row_clipboard = None

    def _emit_leak_paste_row(self, clip: dict, after_row: int) -> None:
        self.leakPasteRowRequested.emit(clip["excel_row"], after_row, clip["is_cut"])
        if clip["is_cut"]:
            self._row_clipboard = None

    def _emit_tvl_paste_row(self, clip: dict, after_row: int) -> None:
        self.tvlPasteRowRequested.emit(clip["excel_row"], after_row, clip["is_cut"])
        if clip["is_cut"]:
            self._row_clipboard = None

    def _on_vertical_header_context_menu(self, header_pos, table, handler) -> None:
        """Relay a right-click on the row-number header to the normal context menu."""
        row = table.verticalHeader().logicalIndexAt(header_pos)
        if row < 0:
            return
        selected_rows = {idx.row() for idx in table.selectionModel().selectedIndexes()}
        if row not in selected_rows:
            table.selectRow(row)
        vp_y = table.rowViewportPosition(row) + max(0, table.rowHeight(row) // 2 - 1)
        handler(QPoint(0, vp_y))

    def _add_clipboard_actions(self, menu, table, cols, row_map, sheet_name) -> None:
        copy_act = QAction("Copy", self)
        copy_act.triggered.connect(lambda: self._copy_selection(table))
        cut_act = QAction("Cut", self)
        cut_act.triggered.connect(lambda: self._cut_selection(table, cols, row_map, sheet_name))
        paste_act = QAction("Paste", self)
        paste_act.triggered.connect(lambda: self._paste_to_table(table, cols, row_map, sheet_name))
        menu.addAction(copy_act)
        menu.addAction(cut_act)
        menu.addAction(paste_act)

    # ------------------------------------------------------------------
    # Cut / Copy / Paste
    # ------------------------------------------------------------------

    def _active_table_info(self):
        """Return (table, cols, row_map, sheet_name) for the focused table, or None."""
        focused = QApplication.focusWidget()
        candidates = [
            (self._pv_table,   _PV_COLS,   self._pv_row_map,   L.PV_SHEET_NAME),
            (self._leak_table, _LEAK_COLS, self._leak_row_map, L.LEAK_SHEET_NAME),
            (self._tvl_table,  _TVL_COLS,  self._tvl_row_map,  L.TVL_SHEET_NAME),
            (self._mix_table,  _MIX_COLS,  self._mix_row_map,  L.MIX_SHEET_NAME),
        ]
        for table, cols, row_map, sheet in candidates:
            w = focused
            while w is not None:
                if w is table:
                    return table, cols, row_map, sheet
                w = w.parent()
        # Fall back to current tab
        idx = self._tab_widget.currentIndex()
        return candidates[idx] if 0 <= idx < len(candidates) else None

    def _on_copy(self) -> None:
        info = self._active_table_info()
        if info:
            self._copy_selection(info[0])

    def _on_cut(self) -> None:
        info = self._active_table_info()
        if info:
            table, cols, row_map, sheet = info
            self._cut_selection(table, cols, row_map, sheet)

    def _on_paste(self) -> None:
        info = self._active_table_info()
        if info:
            table, cols, row_map, sheet = info
            self._paste_to_table(table, cols, row_map, sheet)

    def _copy_selection(self, table: QTableWidget) -> None:
        """Copy selected cells to the system clipboard as tab-delimited text."""
        sel_ranges = table.selectedRanges()
        if not sel_ranges:
            return
        rows_set: set[int] = set()
        cols_set: set[int] = set()
        for r in sel_ranges:
            for row in range(r.topRow(), r.bottomRow() + 1):
                rows_set.add(row)
            for col in range(r.leftColumn(), r.rightColumn() + 1):
                cols_set.add(col)
        rows = sorted(rows_set)
        cols = sorted(cols_set)
        lines = []
        for row in rows:
            cells = []
            for col in cols:
                item = table.item(row, col)
                cells.append(item.text() if item else "")
            lines.append("\t".join(cells))
        QApplication.clipboard().setText("\n".join(lines))

    def _cut_selection(self, table: QTableWidget, cols: list[_ColSpec],
                       row_map: list[int], sheet_name: str) -> None:
        """Copy selection to clipboard then clear the cells in the workbook."""
        self._copy_selection(table)
        if self._wb is None:
            return
        sel_ranges = table.selectedRanges()
        if not sel_ranges:
            return
        self._updating = True
        any_change = False
        try:
            ws = find_sheet(self._wb, sheet_name)
            for r in sel_ranges:
                for row in range(r.topRow(), r.bottomRow() + 1):
                    if row >= len(row_map):
                        continue
                    excel_row = row_map[row]
                    for col in range(r.leftColumn(), r.rightColumn() + 1):
                        if col >= len(cols):
                            continue
                        col_idx = col_letter_to_index(cols[col].col_letter)
                        ws.cell(row=excel_row, column=col_idx).value = None
                        item = table.item(row, col)
                        if item:
                            item.setText("")
                        any_change = True
        finally:
            self._updating = False
        if any_change:
            self.workbookModified.emit()

    def _paste_to_table(self, table: QTableWidget, cols: list[_ColSpec],
                        row_map: list[int], sheet_name: str) -> None:
        """Paste clipboard text into the current selection, tiling if necessary.

        When more cells are selected than the clipboard contains (in either
        dimension), the clipboard content repeats cyclically to fill the whole
        selection — e.g. pasting a single value into 10 selected rows sets all
        10 rows to that value.  Unselected rows/columns are never touched.
        """
        if self._wb is None:
            return
        text = QApplication.clipboard().text()
        if not text:
            return

        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        while lines and not lines[-1]:
            lines.pop()
        if not lines:
            return
        clip_rows = [line.split("\t") for line in lines]
        n_clip_rows = len(clip_rows)
        n_clip_cols = max(len(r) for r in clip_rows)

        # Determine target cells from the selection (all selected ranges merged).
        sel_ranges = table.selectedRanges()
        if sel_ranges:
            row_set: set[int] = set()
            col_set: set[int] = set()
            for r in sel_ranges:
                for row in range(r.topRow(), r.bottomRow() + 1):
                    row_set.add(row)
                for col in range(r.leftColumn(), r.rightColumn() + 1):
                    col_set.add(col)
            target_rows = sorted(row_set)
            target_cols = sorted(col_set)
        else:
            # Fall back: paste starting at the current / first selected item.
            current = table.currentItem()
            if current is None:
                items = table.selectedItems()
                if not items:
                    return
                current = min(items, key=lambda i: (i.row(), i.column()))
            start_r, start_c = current.row(), current.column()
            target_rows = list(range(start_r, min(start_r + n_clip_rows, table.rowCount())))
            target_cols = list(range(start_c, min(start_c + n_clip_cols, table.columnCount())))

        self._updating = True
        any_change = False
        try:
            ws = find_sheet(self._wb, sheet_name)
            for row_off, tbl_row in enumerate(target_rows):
                if tbl_row >= len(row_map):
                    break
                excel_row = row_map[tbl_row]
                clip_row = clip_rows[row_off % n_clip_rows]
                for col_off, tbl_col in enumerate(target_cols):
                    if tbl_col >= len(cols):
                        break
                    clip_text = clip_row[col_off % n_clip_cols] if col_off < len(clip_row) else ""
                    write_val = _to_write_value(clip_text, cols[tbl_col].numeric)
                    col_idx = col_letter_to_index(cols[tbl_col].col_letter)
                    ws.cell(row=excel_row, column=col_idx).value = write_val
                    display = "" if write_val is None else str(write_val)
                    item = table.item(tbl_row, tbl_col)
                    if item is None:
                        item = QTableWidgetItem(display)
                        table.setItem(tbl_row, tbl_col, item)
                    else:
                        item.setText(display)
                    any_change = True
        finally:
            self._updating = False
        if any_change:
            self.workbookModified.emit()

    # ------------------------------------------------------------------
    # Internal – loading
    # ------------------------------------------------------------------

    def _load_tab(self, wb, sheet_name, cols, key_col_letter,
                  scan_fn, table, row_map) -> None:
        self._updating = True
        row_map.clear()
        table.setRowCount(0)
        try:
            ws = find_sheet(wb, sheet_name)
        except Exception:  # noqa: BLE001
            self._updating = False
            return
        try:
            first_c, last_c = scan_fn()
            last_row = find_last_populated_row(ws, first_c, last_c, L.DATA_START_ROW)
            key_idx  = col_letter_to_index(key_col_letter)
            col_idxs = [col_letter_to_index(spec.col_letter) for spec in cols]
            for excel_row in range(L.DATA_START_ROW, last_row + 1):
                if not _is_populated(ws.cell(row=excel_row, column=key_idx).value):
                    continue
                tbl_row = table.rowCount()
                table.insertRow(tbl_row)
                row_map.append(excel_row)
                for tbl_col, c_idx in enumerate(col_idxs):
                    val  = ws.cell(row=excel_row, column=c_idx).value
                    text = "" if val is None else str(val)
                    table.setItem(tbl_row, tbl_col, QTableWidgetItem(text))
        finally:
            self._updating = False

    # ------------------------------------------------------------------
    # Internal – cell editing
    # ------------------------------------------------------------------

    def _on_cell_changed(self, sheet_name, cols, row_map, table,
                         tbl_row, tbl_col) -> None:
        if self._updating or self._wb is None:
            return
        if tbl_row >= len(row_map) or tbl_col >= len(cols):
            return
        excel_row  = row_map[tbl_row]
        col_letter = cols[tbl_col].col_letter
        col_idx    = col_letter_to_index(col_letter)
        item       = table.item(tbl_row, tbl_col)
        text       = item.text() if item is not None else ""
        write_val  = _to_write_value(text, cols[tbl_col].numeric)
        try:
            ws = find_sheet(self._wb, sheet_name)
            ws.cell(row=excel_row, column=col_idx).value = write_val
            self._updating = True
            if item is not None:
                item.setText("" if write_val is None else str(write_val))
            self._updating = False
            self.workbookModified.emit()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(
                self, "Edit failed",
                f"Could not update cell {col_letter}{excel_row}:\n{e}",
            )
            try:
                ws = find_sheet(self._wb, sheet_name)
                prev = ws.cell(row=excel_row, column=col_idx).value
                self._updating = True
                if item is not None:
                    item.setText("" if prev is None else str(prev))
                self._updating = False
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------
    # Internal – helpers
    # ------------------------------------------------------------------

    def _clear_all(self) -> None:
        self._updating = True
        for table, rmap in (
            (self._pv_table,   self._pv_row_map),
            (self._leak_table, self._leak_row_map),
            (self._tvl_table,  self._tvl_row_map),
            (self._mix_table,  self._mix_row_map),
        ):
            table.setRowCount(0)
            rmap.clear()
        self._updating = False
