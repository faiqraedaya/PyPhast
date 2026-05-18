"""HierarchyViewerWidget – tree view of the Phast target workbook structure.

Displays: Workspace > Study > Folder(s) > Pressure Vessel(s) > Leak(s)
with full expand/collapse support and right-click context menu for PV and
Leak operations (add, delete, move, copy, cut, paste).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QMenu,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from ..core.columns import col_letter_to_index
from ..core.excel_io import find_sheet
from ..core.sheet_utils import find_last_populated_row
from ..core import target_layout as L

_WORKSPACE_SHEET = "Workspace"
_STUDY_SHEET = "Study"

_COL_B = col_letter_to_index("B")
_FOLDER_COL_INDICES = tuple(
    col_letter_to_index(c) for c in ("C", "D", "E", "F", "G")
)
_COL_H = col_letter_to_index("H")
_LEAK_NAME_COL    = col_letter_to_index(L.LEAK_COL_NAME)
_LEAK_ORIFICE_COL = col_letter_to_index(L.LEAK_COL_ORIFICE_DIAMETER)
_TVL_NAME_COL     = col_letter_to_index(L.TVL_COL_NAME)
_TVL_ORIFICE_COL  = col_letter_to_index(L.TVL_COL_ORIFICE_DIAMETER)

_ROLE = Qt.ItemDataRole.UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _str_val(ws, row: int, col: int) -> str:
    v = ws.cell(row=row, column=col).value
    return str(v).strip() if v is not None else ""


def _folder_path(ws, row: int) -> tuple[str, ...]:
    parts = []
    for col in _FOLDER_COL_INDICES:
        s = _str_val(ws, row, col)
        if s:
            parts.append(s)
    return tuple(parts)


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

class HierarchyViewerWidget(QGroupBox):
    """Tree showing Workspace > Study > Folder(s) > PV(s) > Leak(s)."""

    # PV operations
    pvInsertRequested   = Signal(int)          # after_excel_row
    pvDeleteRequested   = Signal(int, str)     # excel_row, pv_name
    pvMoveUpRequested   = Signal(int)          # excel_row
    pvMoveDownRequested = Signal(int)          # excel_row
    pvAddLeakRequested  = Signal(int, str)     # pv_excel_row, pv_name
    pvAddTvlRequested   = Signal(int, str)     # pv_excel_row, pv_name
    pvPasteRequested    = Signal(int, int, bool, str)  # src_row, after_row, is_cut, pv_name

    # Leak operations
    leakInsertRequested = Signal(int)          # after_excel_row
    leakDeleteRequested = Signal(int)          # excel_row
    leakPasteRequested  = Signal(int, int, bool)  # src_row, after_row, is_cut

    # TVL operations
    tvlInsertRequested  = Signal(int)          # after_excel_row
    tvlDeleteRequested  = Signal(int)          # excel_row
    tvlPasteRequested   = Signal(int, int, bool)  # src_row, after_row, is_cut

    # Rename operations
    pvRenameRequested   = Signal(int, str, str)  # excel_row, old_name, new_name
    leakRenameRequested = Signal(int, str)        # excel_row, new_name
    tvlRenameRequested  = Signal(int, str)        # excel_row, new_name

    def __init__(self, parent=None) -> None:
        super().__init__("Project Hierarchy", parent)
        self._wb = None
        self._clipboard: tuple | None = None
        self._clipboard_is_cut: bool = False
        self._build_ui()

    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setAlternatingRowColors(True)
        self._tree.setAnimated(True)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.currentItemChanged.connect(self._on_selection_changed)

        layout.addWidget(self._tree)

        # ── Buttons below the tree ────────────────────────────────────────
        btn_row = QHBoxLayout()

        self._move_up_btn = QPushButton("▲ Move Up")
        self._move_up_btn.setToolTip("Move selected pressure vessel up")
        self._move_up_btn.setEnabled(False)
        self._move_up_btn.clicked.connect(self._on_move_up)

        self._move_down_btn = QPushButton("▼ Move Down")
        self._move_down_btn.setToolTip("Move selected pressure vessel down")
        self._move_down_btn.setEnabled(False)
        self._move_down_btn.clicked.connect(self._on_move_down)

        expand_btn  = QPushButton("Expand All")
        expand_btn.clicked.connect(self._tree.expandAll)
        collapse_btn = QPushButton("Collapse All")
        collapse_btn.clicked.connect(self._tree.collapseAll)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)

        btn_row.addWidget(self._move_up_btn)
        btn_row.addWidget(self._move_down_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(expand_btn)
        btn_row.addWidget(collapse_btn)
        btn_row.addWidget(refresh_btn)

        layout.addLayout(btn_row)

        # ── Keyboard shortcuts ────────────────────────────────────────────
        ctx = Qt.ShortcutContext.WidgetWithChildrenShortcut
        for key, slot in (
            (QKeySequence.StandardKey.Copy,  self._on_copy),
            (QKeySequence.StandardKey.Cut,   self._on_cut),
            (QKeySequence.StandardKey.Paste, self._on_paste),
            (QKeySequence(Qt.Key.Key_F2),    self._on_rename),
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
        self._tree.clear()
        if self._wb is None:
            return
        try:
            self._build_tree(self._wb)
        except Exception:  # noqa: BLE001
            pass

    def expand_all(self) -> None:
        self._tree.expandAll()

    def collapse_all(self) -> None:
        self._tree.collapseAll()

    # ------------------------------------------------------------------
    # Tree construction
    # ------------------------------------------------------------------

    def _build_tree(self, wb) -> None:
        workspace_name = self._read_workspace(wb)
        study_names    = self._read_studies(wb)
        pv_data        = self._read_pv_rows(wb)
        leak_data      = self._read_leak_rows(wb)
        tvl_data       = self._read_tvl_rows(wb)

        ws_item = QTreeWidgetItem(self._tree, [workspace_name or "(unnamed workspace)"])
        ws_item.setExpanded(True)

        for study in study_names:
            study_item = QTreeWidgetItem(ws_item, [study])
            study_item.setExpanded(True)

            folder_cache: dict[tuple[str, ...], QTreeWidgetItem] = {}

            for folder_path, pv_name, excel_row in pv_data.get(study, []):
                parent: QTreeWidgetItem = study_item
                for depth in range(len(folder_path)):
                    partial = folder_path[: depth + 1]
                    if partial not in folder_cache:
                        f_item = QTreeWidgetItem(parent, [folder_path[depth]])
                        f_item.setExpanded(True)
                        folder_cache[partial] = f_item
                    parent = folder_cache[partial]

                pv_item = QTreeWidgetItem(parent, [pv_name])
                pv_item.setExpanded(True)
                pv_item.setData(0, _ROLE, ("pv", excel_row, pv_name))

                for leak_text, leak_row, leak_name in leak_data.get((study, folder_path, pv_name), []):
                    leak_item = QTreeWidgetItem(pv_item, [leak_text])
                    leak_item.setData(0, _ROLE, ("leak", leak_row, leak_name))

                for tvl_text, tvl_row, tvl_name in tvl_data.get((study, folder_path, pv_name), []):
                    tvl_item = QTreeWidgetItem(pv_item, [tvl_text])
                    tvl_item.setData(0, _ROLE, ("tvl", tvl_row, tvl_name))

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _on_context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        menu = QMenu(self)

        if item is not None:
            menu.addAction("Expand",   lambda: item.setExpanded(True))
            menu.addAction("Collapse", lambda: item.setExpanded(False))

        data = item.data(0, _ROLE) if item else None

        if data and data[0] == "pv":
            _, excel_row, pv_name = data
            menu.addSeparator()
            menu.addAction("Rename",
                           lambda: self._on_rename())
            menu.addAction("Add Pressure Vessel Above",
                           lambda: self.pvInsertRequested.emit(excel_row - 1))
            menu.addAction("Add Pressure Vessel Below",
                           lambda: self.pvInsertRequested.emit(excel_row))
            menu.addAction("Add Leak",
                           lambda: self.pvAddLeakRequested.emit(excel_row, pv_name))
            menu.addAction("Add Time Varying Leak",
                           lambda: self.pvAddTvlRequested.emit(excel_row, pv_name))
            menu.addAction("Delete Pressure Vessel",
                           lambda: self.pvDeleteRequested.emit(excel_row, pv_name))
            menu.addSeparator()
            menu.addAction("Move Up",
                           lambda: self.pvMoveUpRequested.emit(excel_row))
            menu.addAction("Move Down",
                           lambda: self.pvMoveDownRequested.emit(excel_row))
            menu.addSeparator()
            menu.addAction("Copy",
                           lambda: self._set_clipboard(data, is_cut=False))
            menu.addAction("Cut",
                           lambda: self._set_clipboard(data, is_cut=True))
            if self._clipboard and self._clipboard[0] == "pv":
                src = self._clipboard
                menu.addAction("Paste Below", lambda: self._emit_pv_paste(src, excel_row))

        elif data and data[0] == "leak":
            _, leak_row, _leak_name = data
            menu.addSeparator()
            menu.addAction("Rename",
                           lambda: self._on_rename())
            menu.addAction("Add Leak Above",
                           lambda: self.leakInsertRequested.emit(leak_row - 1))
            menu.addAction("Add Leak Below",
                           lambda: self.leakInsertRequested.emit(leak_row))
            menu.addAction("Delete Leak",
                           lambda: self.leakDeleteRequested.emit(leak_row))
            menu.addSeparator()
            menu.addAction("Copy",
                           lambda: self._set_clipboard(data, is_cut=False))
            menu.addAction("Cut",
                           lambda: self._set_clipboard(data, is_cut=True))
            if self._clipboard and self._clipboard[0] == "leak":
                src = self._clipboard
                menu.addAction("Paste Below", lambda: self._emit_leak_paste(src, leak_row))

        elif data and data[0] == "tvl":
            _, tvl_row, _tvl_name = data
            menu.addSeparator()
            menu.addAction("Rename",
                           lambda: self._on_rename())
            menu.addAction("Add Time Varying Leak Above",
                           lambda: self.tvlInsertRequested.emit(tvl_row - 1))
            menu.addAction("Add Time Varying Leak Below",
                           lambda: self.tvlInsertRequested.emit(tvl_row))
            menu.addAction("Delete Time Varying Leak",
                           lambda: self.tvlDeleteRequested.emit(tvl_row))
            menu.addSeparator()
            menu.addAction("Copy",
                           lambda: self._set_clipboard(data, is_cut=False))
            menu.addAction("Cut",
                           lambda: self._set_clipboard(data, is_cut=True))
            if self._clipboard and self._clipboard[0] == "tvl":
                src = self._clipboard
                menu.addAction("Paste Below", lambda: self._emit_tvl_paste(src, tvl_row))

        if not menu.isEmpty():
            menu.exec(self._tree.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Clipboard helpers
    # ------------------------------------------------------------------

    def _set_clipboard(self, data: tuple, is_cut: bool) -> None:
        self._clipboard = data
        self._clipboard_is_cut = is_cut

    def _emit_pv_paste(self, src: tuple, after_row: int) -> None:
        _, src_row, pv_name = src
        self.pvPasteRequested.emit(src_row, after_row, self._clipboard_is_cut, pv_name)
        if self._clipboard_is_cut:
            self._clipboard = None

    def _emit_leak_paste(self, src: tuple, after_row: int) -> None:
        src_row = src[1]
        self.leakPasteRequested.emit(src_row, after_row, self._clipboard_is_cut)
        if self._clipboard_is_cut:
            self._clipboard = None

    def _emit_tvl_paste(self, src: tuple, after_row: int) -> None:
        src_row = src[1]
        self.tvlPasteRequested.emit(src_row, after_row, self._clipboard_is_cut)
        if self._clipboard_is_cut:
            self._clipboard = None

    # ------------------------------------------------------------------
    # Keyboard shortcut handlers
    # ------------------------------------------------------------------

    def _on_copy(self) -> None:
        data = self._current_item_data()
        if data:
            self._clipboard = data
            self._clipboard_is_cut = False

    def _on_cut(self) -> None:
        data = self._current_item_data()
        if data:
            self._clipboard = data
            self._clipboard_is_cut = True

    def _on_paste(self) -> None:
        if not self._clipboard:
            return
        item = self._tree.currentItem()
        if item is None:
            return
        item_data = item.data(0, _ROLE)
        if not item_data:
            return
        clip_type = self._clipboard[0]
        if clip_type == "pv" and item_data[0] == "pv":
            self._emit_pv_paste(self._clipboard, item_data[1])
        elif clip_type == "leak" and item_data[0] == "leak":
            self._emit_leak_paste(self._clipboard, item_data[1])  # item_data[1] = leak_row
        elif clip_type == "tvl" and item_data[0] == "tvl":
            self._emit_tvl_paste(self._clipboard, item_data[1])   # item_data[1] = tvl_row

    # ------------------------------------------------------------------
    # Move-button callbacks
    # ------------------------------------------------------------------

    def _current_item_data(self):
        item = self._tree.currentItem()
        if item is None:
            return None
        return item.data(0, _ROLE)

    def _on_move_up(self) -> None:
        data = self._current_item_data()
        if data and data[0] == "pv":
            self.pvMoveUpRequested.emit(data[1])

    def _on_move_down(self) -> None:
        data = self._current_item_data()
        if data and data[0] == "pv":
            self.pvMoveDownRequested.emit(data[1])

    def _on_rename(self) -> None:
        item = self._tree.currentItem()
        if item is None:
            return
        data = item.data(0, _ROLE)
        if not data:
            return
        kind = data[0]
        if kind == "pv":
            _, excel_row, old_name = data
            new_name, ok = QInputDialog.getText(
                self, "Rename Pressure Vessel", "New name:", text=old_name
            )
            if ok and new_name.strip() and new_name.strip() != old_name:
                self.pvRenameRequested.emit(excel_row, old_name, new_name.strip())
        elif kind == "leak":
            _, leak_row, current_name = data
            new_name, ok = QInputDialog.getText(
                self, "Rename Leak", "New name:", text=current_name
            )
            if ok and new_name.strip() and new_name.strip() != current_name:
                self.leakRenameRequested.emit(leak_row, new_name.strip())
        elif kind == "tvl":
            _, tvl_row, current_name = data
            new_name, ok = QInputDialog.getText(
                self, "Rename Time Varying Leak", "New name:", text=current_name
            )
            if ok and new_name.strip() and new_name.strip() != current_name:
                self.tvlRenameRequested.emit(tvl_row, new_name.strip())

    def _on_selection_changed(self, current, _previous) -> None:
        data = current.data(0, _ROLE) if current else None
        is_pv = data is not None and data[0] == "pv"
        self._move_up_btn.setEnabled(is_pv)
        self._move_down_btn.setEnabled(is_pv)

    # ------------------------------------------------------------------
    # Data readers
    # ------------------------------------------------------------------

    def _read_workspace(self, wb) -> str:
        try:
            ws = find_sheet(wb, _WORKSPACE_SHEET)
            return _str_val(ws, L.DATA_START_ROW, _COL_B)
        except Exception:  # noqa: BLE001
            return ""

    def _read_studies(self, wb) -> list[str]:
        try:
            ws = find_sheet(wb, _STUDY_SHEET)
        except Exception:  # noqa: BLE001
            return []
        last_row = find_last_populated_row(ws, _COL_B, _COL_B, L.DATA_START_ROW)
        seen: set[str] = set()
        studies: list[str] = []
        for r in range(L.DATA_START_ROW, last_row + 1):
            name = _str_val(ws, r, _COL_B)
            if name and name not in seen:
                seen.add(name)
                studies.append(name)
        return studies

    def _read_pv_rows(
        self, wb
    ) -> dict[str, list[tuple[tuple[str, ...], str, int]]]:
        result: dict[str, list[tuple[tuple[str, ...], str, int]]] = {}
        try:
            ws = find_sheet(wb, L.PV_SHEET_NAME)
        except Exception:  # noqa: BLE001
            return result
        first_c, last_c = L.pv_scan_col_indices()
        last_row = find_last_populated_row(ws, first_c, last_c, L.DATA_START_ROW)
        seen: set[tuple] = set()
        for r in range(L.DATA_START_ROW, last_row + 1):
            study   = _str_val(ws, r, _COL_B)
            pv_name = _str_val(ws, r, _COL_H)
            if not study or not pv_name:
                continue
            fp  = _folder_path(ws, r)
            key = (study, fp, pv_name)
            if key in seen:
                continue
            seen.add(key)
            result.setdefault(study, []).append((fp, pv_name, r))
        return result

    def _read_leak_rows(
        self, wb
    ) -> dict[tuple[str, tuple[str, ...], str], list[tuple[str, int]]]:
        """Return {(study, folder_path, pv_name): [(leak_text, excel_row), ...]}."""
        result: dict[tuple[str, tuple[str, ...], str], list[tuple[str, int]]] = {}
        try:
            ws = find_sheet(wb, L.LEAK_SHEET_NAME)
        except Exception:  # noqa: BLE001
            return result
        first_c, last_c = L.leak_scan_col_indices()
        last_row = find_last_populated_row(ws, first_c, last_c, L.DATA_START_ROW)
        for r in range(L.DATA_START_ROW, last_row + 1):
            study   = _str_val(ws, r, _COL_B)
            pv_name = _str_val(ws, r, _COL_H)
            if not study or not pv_name:
                continue
            leak_name = _str_val(ws, r, _LEAK_NAME_COL)
            if not leak_name:
                continue
            orifice   = _str_val(ws, r, _LEAK_ORIFICE_COL)
            leak_text = f"{leak_name}: {orifice}" if orifice else leak_name
            key = (study, _folder_path(ws, r), pv_name)
            result.setdefault(key, []).append((leak_text, r, leak_name))
        return result

    def _read_tvl_rows(
        self, wb
    ) -> dict[tuple[str, tuple[str, ...], str], list[tuple[str, int]]]:
        """Return {(study, folder_path, pv_name): [(tvl_text, excel_row), ...]}."""
        result: dict[tuple[str, tuple[str, ...], str], list[tuple[str, int]]] = {}
        try:
            ws = find_sheet(wb, L.TVL_SHEET_NAME)
        except Exception:  # noqa: BLE001
            return result
        first_c, last_c = L.tvl_scan_col_indices()
        last_row = find_last_populated_row(ws, first_c, last_c, L.DATA_START_ROW)
        for r in range(L.DATA_START_ROW, last_row + 1):
            study   = _str_val(ws, r, _COL_B)
            pv_name = _str_val(ws, r, _COL_H)
            if not study or not pv_name:
                continue
            tvl_name = _str_val(ws, r, _TVL_NAME_COL)
            if not tvl_name:
                continue
            orifice  = _str_val(ws, r, _TVL_ORIFICE_COL)
            tvl_text = f"TVL: {tvl_name}: {orifice}" if orifice else f"TVL: {tvl_name}"
            key = (study, _folder_path(ws, r), pv_name)
            result.setdefault(key, []).append((tvl_text, r, tvl_name))
        return result
