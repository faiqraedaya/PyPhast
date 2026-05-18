"""Main application window."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .. import __app_name__, __version__
from ..config import _MAX_RECENT, load_config, save_config
from ..core.excel_io import find_sheet, load_workbook, save_workbook
from ..core.sheet_utils import clear_range, find_last_populated_row
from ..core import target_layout as L
from ..core.columns import col_letter_to_index
from ..core.pv_operations import (
    add_leak_for_pv,
    add_tvl_for_pv,
    delete_leak_row,
    delete_pv_row,
    delete_tvl_row,
    find_next_pv_row,
    find_prev_pv_row,
    insert_leak_after,
    insert_leak_copy_after,
    insert_pv_after,
    insert_pv_copy_after,
    insert_tvl_after,
    insert_tvl_copy_after,
    rename_leak,
    rename_pv,
    rename_tvl,
    swap_pv_rows,
)
from .hierarchy_viewer import HierarchyViewerWidget
from .import_panel import ImportPanel
from .target_viewer import TargetViewerWidget


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self._target_wb   = None
        self._target_path = ""
        self._dirty       = False

        self._config = load_config()
        self._build_ui()
        self._build_menu()
        self._build_statusbar()
        self._apply_config()

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget(self)
        outer   = QVBoxLayout(central)

        self.hierarchy_viewer = HierarchyViewerWidget()
        self.hierarchy_viewer.pvInsertRequested.connect(self._pv_insert)
        self.hierarchy_viewer.pvDeleteRequested.connect(self._pv_delete)
        self.hierarchy_viewer.pvMoveUpRequested.connect(self._pv_move_up)
        self.hierarchy_viewer.pvMoveDownRequested.connect(self._pv_move_down)
        self.hierarchy_viewer.pvAddLeakRequested.connect(self._pv_add_leak)
        self.hierarchy_viewer.pvAddTvlRequested.connect(self._pv_add_tvl)
        self.hierarchy_viewer.pvPasteRequested.connect(self._pv_paste)
        self.hierarchy_viewer.leakInsertRequested.connect(self._leak_insert)
        self.hierarchy_viewer.leakDeleteRequested.connect(self._leak_delete)
        self.hierarchy_viewer.leakPasteRequested.connect(self._leak_paste)
        self.hierarchy_viewer.tvlInsertRequested.connect(self._tvl_insert)
        self.hierarchy_viewer.tvlDeleteRequested.connect(self._tvl_delete)
        self.hierarchy_viewer.tvlPasteRequested.connect(self._tvl_paste)
        self.hierarchy_viewer.pvRenameRequested.connect(self._pv_rename)
        self.hierarchy_viewer.leakRenameRequested.connect(self._leak_rename)
        self.hierarchy_viewer.tvlRenameRequested.connect(self._tvl_rename)

        self.target_viewer = TargetViewerWidget()
        self.target_viewer.workbookModified.connect(self._on_workbook_modified)
        self.target_viewer.pvInsertRequested.connect(self._pv_insert)
        self.target_viewer.pvDeleteRequested.connect(self._pv_delete)
        self.target_viewer.pvBatchDeleteRequested.connect(self._pv_batch_delete)
        self.target_viewer.leakInsertRequested.connect(self._leak_insert)
        self.target_viewer.leakDeleteRequested.connect(self._leak_delete)
        self.target_viewer.leakBatchDeleteRequested.connect(self._leak_batch_delete)
        self.target_viewer.tvlInsertRequested.connect(self._tvl_insert)
        self.target_viewer.tvlDeleteRequested.connect(self._tvl_delete)
        self.target_viewer.tvlBatchDeleteRequested.connect(self._tvl_batch_delete)
        self.target_viewer.pvPasteRowRequested.connect(self._pv_paste)
        self.target_viewer.leakPasteRowRequested.connect(self._leak_paste)
        self.target_viewer.tvlPasteRowRequested.connect(self._tvl_paste)
        self.target_viewer.countsUpdated.connect(self._on_counts_updated)

        self.import_panel = ImportPanel()
        self.import_panel.transferComplete.connect(self._on_transfer_complete)
        self.import_panel.logInfo.connect(self._log_info)
        self.import_panel.logWarn.connect(self._log_warn)
        self.import_panel.logError.connect(self._log_error)
        self.import_panel.configChanged.connect(self._save_config)

        self._log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(self._log_group)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        f = QFont("Consolas")
        f.setStyleHint(QFont.StyleHint.Monospace)
        self.log.setFont(f)
        clear_btn = QPushButton("Clear log")
        clear_btn.clicked.connect(self.log.clear)
        log_header = QHBoxLayout()
        log_header.addStretch(1)
        log_header.addWidget(clear_btn)
        log_layout.addLayout(log_header)
        log_layout.addWidget(self.log)

        h_splitter = QSplitter(Qt.Orientation.Horizontal)
        h_splitter.addWidget(self.hierarchy_viewer)
        h_splitter.addWidget(self.target_viewer)
        h_splitter.addWidget(self.import_panel)
        h_splitter.setStretchFactor(0, 1)
        h_splitter.setStretchFactor(1, 3)
        h_splitter.setStretchFactor(2, 2)

        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.addWidget(h_splitter)
        v_splitter.addWidget(self._log_group)
        v_splitter.setStretchFactor(0, 5)
        v_splitter.setStretchFactor(1, 1)

        outer.addWidget(v_splitter)
        self.setCentralWidget(central)

    # -----------------------------------------------------------------------
    # Menu bar
    # -----------------------------------------------------------------------

    def _build_menu(self) -> None:
        bar = self.menuBar()

        # ── File ──────────────────────────────────────────────────────────
        file_menu = bar.addMenu("&File")

        act_new = QAction("&New", self)
        act_new.setShortcut(QKeySequence.StandardKey.New)
        act_new.setStatusTip("Close the current file and start fresh")
        act_new.triggered.connect(self._file_new)
        file_menu.addAction(act_new)

        act_open = QAction("&Open…", self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.setStatusTip("Open a Phast input workbook")
        act_open.triggered.connect(self._file_open)
        file_menu.addAction(act_open)

        self._act_open_last = QAction("Open &Last", self)
        self._act_open_last.setShortcut("Ctrl+Shift+O")
        self._act_open_last.setStatusTip("Reopen the most recently opened workbook")
        self._act_open_last.setEnabled(False)
        self._act_open_last.triggered.connect(self._file_open_last)
        file_menu.addAction(self._act_open_last)

        self._recent_menu = file_menu.addMenu("Open &Recent")
        self._recent_menu.setEnabled(False)

        file_menu.addSeparator()

        self._act_save = QAction("&Save", self)
        self._act_save.setShortcut(QKeySequence.StandardKey.Save)
        self._act_save.setStatusTip("Save all changes back to disk")
        self._act_save.setEnabled(False)
        self._act_save.triggered.connect(self._file_save)
        file_menu.addAction(self._act_save)

        file_menu.addSeparator()

        act_exit = QAction("E&xit", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        # ── Edit ──────────────────────────────────────────────────────────
        edit_menu = bar.addMenu("&Edit")

        act_clear_pv = QAction("Clear &Pressure Vessel data…", self)
        act_clear_pv.setStatusTip(
            "Remove all pressure vessel rows from the workbook (unsaved)"
        )
        act_clear_pv.triggered.connect(
            lambda: self._clear_sheet_data(
                L.PV_SHEET_NAME, L.pv_scan_col_indices()
            )
        )
        edit_menu.addAction(act_clear_pv)

        act_clear_leak = QAction("Clear &Leak data…", self)
        act_clear_leak.setStatusTip(
            "Remove all leak rows from the workbook (unsaved)"
        )
        act_clear_leak.triggered.connect(
            lambda: self._clear_sheet_data(
                L.LEAK_SHEET_NAME, L.leak_scan_col_indices()
            )
        )
        edit_menu.addAction(act_clear_leak)

        act_clear_tvl = QAction("Clear &Time Varying Leak data…", self)
        act_clear_tvl.setStatusTip(
            "Remove all time varying leak rows from the workbook (unsaved)"
        )
        act_clear_tvl.triggered.connect(
            lambda: self._clear_sheet_data(
                L.TVL_SHEET_NAME, L.tvl_scan_col_indices()
            )
        )
        edit_menu.addAction(act_clear_tvl)

        act_clear_mix = QAction("Clear &Mixture data…", self)
        act_clear_mix.setStatusTip(
            "Remove all mixture rows from the workbook (unsaved)"
        )
        act_clear_mix.triggered.connect(
            lambda: self._clear_sheet_data(
                L.MIX_SHEET_NAME, L.mix_scan_col_indices()
            )
        )
        edit_menu.addAction(act_clear_mix)

        # ── View ──────────────────────────────────────────────────────────
        view_menu = bar.addMenu("&View")

        self._act_toggle_hierarchy = QAction("Show &Project Hierarchy", self)
        self._act_toggle_hierarchy.setCheckable(True)
        self._act_toggle_hierarchy.setChecked(True)
        self._act_toggle_hierarchy.triggered.connect(self._toggle_hierarchy)
        view_menu.addAction(self._act_toggle_hierarchy)

        self._act_toggle_import = QAction("Show &Data Transfer", self)
        self._act_toggle_import.setCheckable(True)
        self._act_toggle_import.setChecked(True)
        self._act_toggle_import.triggered.connect(self._toggle_import)
        view_menu.addAction(self._act_toggle_import)

        self._act_toggle_log = QAction("Show &Log", self)
        self._act_toggle_log.setCheckable(True)
        self._act_toggle_log.setChecked(True)
        self._act_toggle_log.setShortcut("Ctrl+L")
        self._act_toggle_log.triggered.connect(self._toggle_log)
        view_menu.addAction(self._act_toggle_log)

        # ── About ─────────────────────────────────────────────────────────
        about_menu = bar.addMenu("&About")

        act_about = QAction(f"About {__app_name__}…", self)
        act_about.triggered.connect(self._show_about)
        about_menu.addAction(act_about)

    # -----------------------------------------------------------------------
    # Status bar
    # -----------------------------------------------------------------------

    def _build_statusbar(self) -> None:
        sb = self.statusBar()
        self._sb_counts = QLabel("  ")
        self._sb_file = QLabel("  No file loaded")
        self._sb_modified = QLabel("  ● Modified  ")
        self._sb_modified.setStyleSheet("color: #e67e22; font-weight: bold;")
        self._sb_modified.setVisible(False)
        sb.addPermanentWidget(self._sb_counts)
        sb.addPermanentWidget(self._sb_file)
        sb.addPermanentWidget(self._sb_modified)

    # -----------------------------------------------------------------------
    # File operations
    # -----------------------------------------------------------------------

    def _file_new(self) -> None:
        if not self._confirm_discard():
            return
        self._target_wb   = None
        self._target_path = ""
        self._dirty       = False
        self.import_panel.set_workbook(None)
        self.target_viewer.load_workbook(None)
        self.hierarchy_viewer.load_workbook(None)
        self._act_save.setEnabled(False)
        self._update_title()
        self._update_statusbar()
        self._log_info("New — workbook cleared.")

    def _file_open(self) -> None:
        if not self._confirm_discard():
            return
        start = str(Path(self._target_path).parent) if self._target_path else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Phast workbook", start, "Excel files (*.xlsx *.xlsm)"
        )
        if path:
            self._open_file(path)

    def _file_open_last(self) -> None:
        if not self._config.recent_files:
            return
        if not self._confirm_discard():
            return
        self._open_file(self._config.recent_files[0])

    # -----------------------------------------------------------------------

    def _add_to_recent(self, path: str) -> None:
        recent = self._config.recent_files
        # Remove duplicates then prepend, keep max _MAX_RECENT entries
        recent = [p for p in recent if p != path]
        recent.insert(0, path)
        self._config.recent_files = recent[:_MAX_RECENT]
        self._update_recent_menu()

    def _update_recent_menu(self) -> None:
        self._recent_menu.clear()
        recent = self._config.recent_files
        if not recent:
            self._recent_menu.setEnabled(False)
            self._act_open_last.setEnabled(False)
            return
        self._recent_menu.setEnabled(True)
        self._act_open_last.setEnabled(True)
        for path in recent:
            p = Path(path)
            label = p.name
            act = QAction(label, self)
            act.setStatusTip(path)
            act.setToolTip(path)
            if not p.exists():
                act.setEnabled(False)
            else:
                act.triggered.connect(lambda checked=False, fp=path: self._open_recent(fp))
            self._recent_menu.addAction(act)
        self._recent_menu.addSeparator()
        act_clear = QAction("Clear Recent", self)
        act_clear.triggered.connect(self._clear_recent)
        self._recent_menu.addAction(act_clear)

    def _open_recent(self, path: str) -> None:
        if not self._confirm_discard():
            return
        self._open_file(path)

    def _clear_recent(self) -> None:
        self._config.recent_files = []
        self._update_recent_menu()
        self._save_config()

    # -----------------------------------------------------------------------

    def _file_save(self) -> None:
        if self._target_wb is None or not self._target_path:
            return
        try:
            save_workbook(self._target_wb, self._target_path)
            self._dirty = False
            self._update_title()
            self._update_statusbar()
            self.statusBar().showMessage("Saved.", 3000)
            self._log_info(f"Saved: {self._target_path}")
            self._save_config()
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Save failed", f"Could not save file:\n{e}")
            self._log_error(f"Save failed: {e}")

    def _open_file(self, path: str) -> None:
        try:
            self._log_info(f"Opening: {path}")
            wb = load_workbook(path, data_only=False)
            self._target_wb   = wb
            self._target_path = path
            self._dirty       = False
            self.import_panel.set_workbook(wb)
            self.target_viewer.load_workbook(wb)
            self.hierarchy_viewer.load_workbook(wb)
            self._act_save.setEnabled(True)
            self._update_title()
            self._update_statusbar()
            self._add_to_recent(path)
            self._save_config()
            self._log_info("File loaded.")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Open failed", f"Could not open file:\n{e}")
            self._log_error(f"Open failed: {e}")

    def _confirm_discard(self) -> bool:
        if not self._dirty:
            return True
        reply = QMessageBox.question(
            self,
            "Unsaved changes",
            "The workbook has unsaved changes.\n"
            "Do you want to save before continuing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Save:
            self._file_save()
            return not self._dirty
        if reply == QMessageBox.StandardButton.Discard:
            return True
        return False

    # -----------------------------------------------------------------------
    # Edit menu actions
    # -----------------------------------------------------------------------

    def _clear_sheet_data(
        self, sheet_name: str, col_range: tuple[int, int]
    ) -> None:
        if self._target_wb is None:
            QMessageBox.information(
                self, "No file", "Open a workbook first (File → Open)."
            )
            return
        first_c, last_c = col_range
        reply = QMessageBox.question(
            self,
            f"Clear {sheet_name} data",
            f"Remove all data rows from the '{sheet_name}' sheet?\n"
            "The change won't be saved to disk until you use File → Save.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            ws = find_sheet(self._target_wb, sheet_name)
            last_row = find_last_populated_row(
                ws, first_c, last_c, L.DATA_START_ROW
            )
            if last_row >= L.DATA_START_ROW:
                clear_range(ws, first_c, last_c, L.DATA_START_ROW, last_row)
                self._set_dirty()
                self.target_viewer.refresh()
                self.hierarchy_viewer.refresh()
                self._log_info(
                    f"Cleared '{sheet_name}' rows "
                    f"{L.DATA_START_ROW}–{last_row}."
                )
            else:
                self._log_info(f"'{sheet_name}' is already empty.")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Clear failed", f"Could not clear data:\n{e}")
            self._log_error(f"Clear failed: {e}")

    # -----------------------------------------------------------------------
    # PV operations (from hierarchy or workbook editor context menus / buttons)
    # -----------------------------------------------------------------------

    def _pv_insert(self, after_excel_row: int) -> None:
        if self._target_wb is None:
            return
        try:
            new_row = insert_pv_after(self._target_wb, after_excel_row)
            self._set_dirty()
            self.target_viewer.refresh()
            self.hierarchy_viewer.refresh()
            self._log_info(f"Inserted new pressure vessel at row {new_row}.")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Insert failed", f"Could not insert row:\n{e}")
            self._log_error(f"PV insert failed: {e}")

    def _pv_delete(self, excel_row: int, pv_name: str) -> None:
        if self._target_wb is None:
            return
        label = f'"{pv_name}"' if pv_name else f"row {excel_row}"
        reply = QMessageBox.question(
            self,
            "Delete Pressure Vessel",
            f"Delete pressure vessel {label} and all its associated leaks?\n"
            "This cannot be undone (until you close without saving).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            delete_pv_row(self._target_wb, excel_row, pv_name)
            self._set_dirty()
            self.target_viewer.refresh()
            self.hierarchy_viewer.refresh()
            self._log_info(f"Deleted pressure vessel {label}.")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Delete failed", f"Could not delete row:\n{e}")
            self._log_error(f"PV delete failed: {e}")

    def _pv_batch_delete(self, rows) -> None:
        if self._target_wb is None:
            return
        count = len(rows)
        reply = QMessageBox.question(
            self,
            "Delete Pressure Vessels",
            f"Delete {count} pressure vessel(s) and all their associated leaks and TVLs?\n"
            "This cannot be undone (until you close without saving).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            for excel_row, pv_name in sorted(rows, key=lambda x: x[0], reverse=True):
                delete_pv_row(self._target_wb, excel_row, pv_name)
            self._set_dirty()
            self.target_viewer.refresh()
            self.hierarchy_viewer.refresh()
            self._log_info(f"Deleted {count} pressure vessel(s).")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Delete failed", f"Could not delete rows:\n{e}")
            self._log_error(f"PV batch delete failed: {e}")

    def _pv_move_up(self, excel_row: int) -> None:
        if self._target_wb is None:
            return
        try:
            prev_row = find_prev_pv_row(self._target_wb, excel_row)
            if prev_row is None:
                return
            swap_pv_rows(self._target_wb, prev_row, excel_row)
            self._set_dirty()
            self.target_viewer.refresh()
            self.hierarchy_viewer.refresh()
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Move failed", f"Could not move row:\n{e}")
            self._log_error(f"PV move up failed: {e}")

    def _pv_move_down(self, excel_row: int) -> None:
        if self._target_wb is None:
            return
        try:
            next_row = find_next_pv_row(self._target_wb, excel_row)
            if next_row is None:
                return
            swap_pv_rows(self._target_wb, excel_row, next_row)
            self._set_dirty()
            self.target_viewer.refresh()
            self.hierarchy_viewer.refresh()
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Move failed", f"Could not move row:\n{e}")
            self._log_error(f"PV move down failed: {e}")

    def _pv_add_leak(self, pv_excel_row: int, pv_name: str) -> None:
        if self._target_wb is None:
            return
        try:
            new_row = add_leak_for_pv(self._target_wb, pv_name, pv_excel_row)
            if new_row < 0:
                self._log_warn("Could not find or create leak sheet.")
                return
            self._set_dirty()
            self.target_viewer.refresh()
            self.hierarchy_viewer.refresh()
            self._log_info(f"Added new leak for '{pv_name}' at row {new_row}.")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Add leak failed", f"Could not add leak:\n{e}")
            self._log_error(f"Add leak failed: {e}")

    def _pv_paste(self, src_row: int, after_row: int, is_cut: bool, pv_name: str) -> None:
        if self._target_wb is None:
            return
        try:
            insert_pv_copy_after(self._target_wb, src_row, after_row)
            if is_cut:
                actual_src = src_row + 1 if src_row > after_row else src_row
                delete_pv_row(self._target_wb, actual_src, pv_name)
            self._set_dirty()
            self.target_viewer.refresh()
            self.hierarchy_viewer.refresh()
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Paste failed", f"Could not paste PV:\n{e}")
            self._log_error(f"PV paste failed: {e}")

    def _leak_insert(self, after_excel_row: int) -> None:
        if self._target_wb is None:
            return
        try:
            new_row = insert_leak_after(self._target_wb, after_excel_row)
            self._set_dirty()
            self.target_viewer.refresh()
            self.hierarchy_viewer.refresh()
            self._log_info(f"Inserted new leak at row {new_row}.")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Insert failed", f"Could not insert leak:\n{e}")
            self._log_error(f"Leak insert failed: {e}")

    def _leak_delete(self, excel_row: int) -> None:
        if self._target_wb is None:
            return
        reply = QMessageBox.question(
            self,
            "Delete Leak",
            f"Delete leak at row {excel_row}?\n"
            "This cannot be undone (until you close without saving).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            delete_leak_row(self._target_wb, excel_row)
            self._set_dirty()
            self.target_viewer.refresh()
            self.hierarchy_viewer.refresh()
            self._log_info(f"Deleted leak at row {excel_row}.")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Delete failed", f"Could not delete leak:\n{e}")
            self._log_error(f"Leak delete failed: {e}")

    def _leak_paste(self, src_row: int, after_row: int, is_cut: bool) -> None:
        if self._target_wb is None:
            return
        try:
            insert_leak_copy_after(self._target_wb, src_row, after_row)
            if is_cut:
                actual_src = src_row + 1 if src_row > after_row else src_row
                delete_leak_row(self._target_wb, actual_src)
            self._set_dirty()
            self.target_viewer.refresh()
            self.hierarchy_viewer.refresh()
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Paste failed", f"Could not paste leak:\n{e}")
            self._log_error(f"Leak paste failed: {e}")

    def _leak_batch_delete(self, excel_rows) -> None:
        if self._target_wb is None:
            return
        count = len(excel_rows)
        reply = QMessageBox.question(
            self,
            "Delete Leaks",
            f"Delete {count} leak row(s)?\n"
            "This cannot be undone (until you close without saving).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            for excel_row in sorted(excel_rows, reverse=True):
                delete_leak_row(self._target_wb, excel_row)
            self._set_dirty()
            self.target_viewer.refresh()
            self.hierarchy_viewer.refresh()
            self._log_info(f"Deleted {count} leak row(s).")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Delete failed", f"Could not delete rows:\n{e}")
            self._log_error(f"Leak batch delete failed: {e}")

    def _tvl_batch_delete(self, excel_rows) -> None:
        if self._target_wb is None:
            return
        count = len(excel_rows)
        reply = QMessageBox.question(
            self,
            "Delete Time Varying Leaks",
            f"Delete {count} time varying leak row(s)?\n"
            "This cannot be undone (until you close without saving).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            for excel_row in sorted(excel_rows, reverse=True):
                delete_tvl_row(self._target_wb, excel_row)
            self._set_dirty()
            self.target_viewer.refresh()
            self.hierarchy_viewer.refresh()
            self._log_info(f"Deleted {count} TVL row(s).")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Delete failed", f"Could not delete rows:\n{e}")
            self._log_error(f"TVL batch delete failed: {e}")

    def _pv_add_tvl(self, pv_excel_row: int, pv_name: str) -> None:
        if self._target_wb is None:
            return
        try:
            new_row = add_tvl_for_pv(self._target_wb, pv_name, pv_excel_row)
            if new_row < 0:
                self._log_warn("Could not find or create time varying leak sheet.")
                return
            self._set_dirty()
            self.target_viewer.refresh()
            self.hierarchy_viewer.refresh()
            self._log_info(f"Added new TVL for '{pv_name}' at row {new_row}.")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Add TVL failed", f"Could not add TVL:\n{e}")
            self._log_error(f"Add TVL failed: {e}")

    def _tvl_insert(self, after_excel_row: int) -> None:
        if self._target_wb is None:
            return
        try:
            new_row = insert_tvl_after(self._target_wb, after_excel_row)
            self._set_dirty()
            self.target_viewer.refresh()
            self.hierarchy_viewer.refresh()
            self._log_info(f"Inserted new time varying leak at row {new_row}.")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Insert failed", f"Could not insert TVL:\n{e}")
            self._log_error(f"TVL insert failed: {e}")

    def _tvl_delete(self, excel_row: int) -> None:
        if self._target_wb is None:
            return
        reply = QMessageBox.question(
            self,
            "Delete Time Varying Leak",
            f"Delete time varying leak at row {excel_row}?\n"
            "This cannot be undone (until you close without saving).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            delete_tvl_row(self._target_wb, excel_row)
            self._set_dirty()
            self.target_viewer.refresh()
            self.hierarchy_viewer.refresh()
            self._log_info(f"Deleted time varying leak at row {excel_row}.")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Delete failed", f"Could not delete TVL:\n{e}")
            self._log_error(f"TVL delete failed: {e}")

    def _tvl_paste(self, src_row: int, after_row: int, is_cut: bool) -> None:
        if self._target_wb is None:
            return
        try:
            insert_tvl_copy_after(self._target_wb, src_row, after_row)
            if is_cut:
                actual_src = src_row + 1 if src_row > after_row else src_row
                delete_tvl_row(self._target_wb, actual_src)
            self._set_dirty()
            self.target_viewer.refresh()
            self.hierarchy_viewer.refresh()
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Paste failed", f"Could not paste TVL:\n{e}")
            self._log_error(f"TVL paste failed: {e}")

    def _pv_rename(self, excel_row: int, old_name: str, new_name: str) -> None:
        if self._target_wb is None:
            return
        try:
            rename_pv(self._target_wb, excel_row, old_name, new_name)
            self._set_dirty()
            self.target_viewer.refresh()
            self.hierarchy_viewer.refresh()
            self._log_info(f"Renamed pressure vessel '{old_name}' → '{new_name}'.")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Rename failed", f"Could not rename pressure vessel:\n{e}")
            self._log_error(f"PV rename failed: {e}")

    def _leak_rename(self, excel_row: int, new_name: str) -> None:
        if self._target_wb is None:
            return
        try:
            rename_leak(self._target_wb, excel_row, new_name)
            self._set_dirty()
            self.target_viewer.refresh()
            self.hierarchy_viewer.refresh()
            self._log_info(f"Renamed leak at row {excel_row} → '{new_name}'.")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Rename failed", f"Could not rename leak:\n{e}")
            self._log_error(f"Leak rename failed: {e}")

    def _tvl_rename(self, excel_row: int, new_name: str) -> None:
        if self._target_wb is None:
            return
        try:
            rename_tvl(self._target_wb, excel_row, new_name)
            self._set_dirty()
            self.target_viewer.refresh()
            self.hierarchy_viewer.refresh()
            self._log_info(f"Renamed TVL at row {excel_row} → '{new_name}'.")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Rename failed", f"Could not rename time varying leak:\n{e}")
            self._log_error(f"TVL rename failed: {e}")

    # -----------------------------------------------------------------------
    # View menu actions
    # -----------------------------------------------------------------------

    def _toggle_hierarchy(self, checked: bool) -> None:
        self.hierarchy_viewer.setVisible(checked)

    def _toggle_import(self, checked: bool) -> None:
        self.import_panel.setVisible(checked)

    def _toggle_log(self, checked: bool) -> None:
        self._log_group.setVisible(checked)

    # -----------------------------------------------------------------------
    # Workbook-modified callbacks
    # -----------------------------------------------------------------------

    def _on_workbook_modified(self) -> None:
        self._set_dirty()
        self.hierarchy_viewer.refresh()

    def _on_transfer_complete(self, success: bool) -> None:
        if success:
            self._set_dirty()
        self.target_viewer.refresh()
        self.hierarchy_viewer.refresh()

    def _set_dirty(self) -> None:
        if not self._dirty:
            self._dirty = True
            self._update_title()
            self._update_statusbar()

    # -----------------------------------------------------------------------
    # Title and status bar
    # -----------------------------------------------------------------------

    def _update_title(self) -> None:
        name  = Path(self._target_path).name if self._target_path else "(no file)"
        dirty = " ●" if self._dirty else ""
        self.setWindowTitle(f"{__app_name__} v{__version__} — {name}{dirty}")

    def _update_statusbar(self) -> None:
        if self._target_path:
            self._sb_file.setText(f"  {Path(self._target_path).name}")
        else:
            self._sb_file.setText("  No file loaded")
            self._sb_counts.setText("  ")
        self._sb_modified.setVisible(self._dirty)

    def _on_counts_updated(self, pv_n: int, leak_n: int, mix_n: int) -> None:
        if self._target_wb is None:
            self._sb_counts.setText("  ")
        else:
            self._sb_counts.setText(
                f"  {pv_n} PV(s) · {leak_n} leak(s) · {mix_n} mixture component(s)  "
            )

    # -----------------------------------------------------------------------
    # About dialog
    # -----------------------------------------------------------------------

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            f"About {__app_name__}",
            f"<b>{__app_name__}</b> v{__version__}<br><br>"
            "A full-featured editor for Phast input Excel workbooks.<br><br>"
            "Built with <b>PySide6</b> and <b>openpyxl</b>.",
        )

    # -----------------------------------------------------------------------
    # Logging
    # -----------------------------------------------------------------------

    def _log(self, prefix: str, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        for line in str(msg).splitlines() or [""]:
            self.log.appendPlainText(f"[{ts}] {prefix} {line}")

    def _log_info(self, msg: str) -> None:
        self._log("[INFO]", msg)

    def _log_warn(self, msg: str) -> None:
        self._log("[WARN]", msg)

    def _log_error(self, msg: str) -> None:
        self._log("[ERR ]", msg)

    # -----------------------------------------------------------------------
    # Config persistence
    # -----------------------------------------------------------------------

    def _apply_config(self) -> None:
        self.import_panel.load_from_config(self._config)
        self._update_title()
        self._update_statusbar()
        self._update_recent_menu()
        if self._config.target_path and Path(self._config.target_path).exists():
            self._open_file(self._config.target_path)

    def _save_config(self) -> None:
        self._config.target_path = self._target_path
        self.import_panel.save_to_config(self._config)
        try:
            save_config(self._config)
        except OSError as e:
            self._log_warn(f"Could not save config: {e}")

    # -----------------------------------------------------------------------
    # Close event
    # -----------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._confirm_discard():
            event.ignore()
            return
        self._save_config()
        super().closeEvent(event)
