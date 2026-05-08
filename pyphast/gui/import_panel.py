"""ImportPanel – right-hand data-transfer widget."""

from __future__ import annotations

import traceback
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QRadioButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
)

from ..config import AppConfig
from ..core.excel_io import list_sheet_names, load_workbook
from ..core.leak import (
    LeakSourceConfig,
    read_fbr_diameters,
    read_pv_names_from_target,
    write_leaks,
)
from ..core.mixture import MixtureOptions, read_mixtures, write_mixtures
from ..core.pressure_vessel import (
    PressureVesselOptions,
    TransferMode,
    TransferReport,
    read_pressure_vessels,
    write_pressure_vessels,
)
from ..core.validation import (
    collect_mixture_stream_names,
    collect_pv_stream_refs,
    warn_unresolved_pv_streams,
)
from .leak_tab import LeakTab
from .mixture_tab import MixtureTab
from .pressure_vessel_tab import PressureVesselTab
from .widgets import FileSelector


class ImportPanel(QGroupBox):
    """Right-hand panel: source file, transfer mode, and per-type transfer tabs."""

    transferComplete = Signal(bool)  # True = no errors → caller should set dirty
    logInfo  = Signal(str)
    logWarn  = Signal(str)
    logError = Signal(str)
    configChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("Data transfer", parent)
        self._target_wb = None
        self._mixture_user_overrides: dict = {}
        self._build_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_workbook(self, wb) -> None:
        self._target_wb = wb

    def load_from_config(self, config: AppConfig) -> None:
        self._mixture_user_overrides = config.mixture.user_overrides
        self.source_selector.setPath(config.source_path)
        if config.transfer_mode == "append":
            self.rb_append.setChecked(True)
        else:
            self.rb_overwrite.setChecked(True)
        self._decimal_places_spin.setValue(config.import_decimal_places)
        self.pv_tab.load_from_config(config.pressure_vessel)
        self.mix_tab.load_from_config(config.mixture)
        self.leak_tab.load_from_config(config.leak)
        self._refresh_sheet_names()

    def save_to_config(self, config: AppConfig) -> None:
        config.source_path   = self.source_selector.path()
        config.transfer_mode = self._transfer_mode().value
        config.import_decimal_places = self._decimal_places_spin.value()
        self.pv_tab.save_to_config(config.pressure_vessel)
        self.mix_tab.save_to_config(config.mixture)
        self.leak_tab.save_to_config(config.leak)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.source_selector = FileSelector(
            "File:", caption="Select source xlsx (isolatable sections)"
        )
        self.source_selector.pathChanged.connect(self._on_source_changed)
        layout.addWidget(self.source_selector)

        mode_row = QHBoxLayout()
        self.rb_overwrite = QRadioButton("Overwrite")
        self.rb_overwrite.setToolTip("Clear existing rows from 63 down before writing")
        self.rb_append = QRadioButton("Append")
        self.rb_append.setToolTip("Continue writing after the last existing row")
        self.rb_overwrite.setChecked(True)
        bg = QButtonGroup(self)
        bg.addButton(self.rb_overwrite)
        bg.addButton(self.rb_append)
        mode_row.addWidget(self.rb_overwrite)
        mode_row.addWidget(self.rb_append)
        mode_row.addStretch(1)

        dp_label = QLabel("Decimal places:")
        self._decimal_places_spin = QSpinBox()
        self._decimal_places_spin.setRange(-1, 15)
        self._decimal_places_spin.setValue(-1)
        self._decimal_places_spin.setSpecialValueText("—")
        self._decimal_places_spin.setMaximumWidth(60)
        self._decimal_places_spin.setToolTip(
            "Round imported numbers to this many decimal places.\n"
            "— means no rounding."
        )
        mode_row.addWidget(dp_label)
        mode_row.addWidget(self._decimal_places_spin)
        layout.addLayout(mode_row)

        self.tabs     = QTabWidget()
        self.pv_tab   = PressureVesselTab()
        self.mix_tab  = MixtureTab()
        self.leak_tab = LeakTab()
        self.tabs.addTab(self.pv_tab,   "Pressure Vessels")
        self.tabs.addTab(self.leak_tab, "Leaks")
        self.tabs.addTab(self.mix_tab,  "Mixtures")
        self.pv_tab.transferRequested.connect(self._run_pv_transfer)
        self.leak_tab.transferRequested.connect(self._run_leak_transfer)
        self.mix_tab.transferRequested.connect(self._run_mix_transfer)
        layout.addWidget(self.tabs, 1)

    # ------------------------------------------------------------------
    # Source file
    # ------------------------------------------------------------------

    def _on_source_changed(self, _: str) -> None:
        self.configChanged.emit()
        self._refresh_sheet_names()

    def _refresh_sheet_names(self) -> None:
        path = self.source_selector.path()
        if not path or not Path(path).exists():
            return
        try:
            names = list_sheet_names(path)
            self.pv_tab.set_sheet_names(names)
            self.mix_tab.set_sheet_names(names)
        except Exception as e:  # noqa: BLE001
            self.logWarn.emit(f"Could not read sheet names from source: {e}")

    # ------------------------------------------------------------------
    # Transfer mode
    # ------------------------------------------------------------------

    def _transfer_mode(self) -> TransferMode:
        return TransferMode.APPEND if self.rb_append.isChecked() else TransferMode.OVERWRITE

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    def _guard_paths(self) -> bool:
        src = self.source_selector.path()
        if not src:
            QMessageBox.warning(
                self, "No source file",
                "Select a source xlsx in the Import panel on the right.",
            )
            return False
        if not Path(src).exists():
            QMessageBox.warning(self, "Missing file", "Source file does not exist.")
            return False
        if self._target_wb is None:
            QMessageBox.warning(
                self, "No workbook open",
                "Open a Phast target file first (File → Open).",
            )
            return False
        return True

    def _guard_pv_config(self, cfg) -> bool:
        if not cfg.sheet:
            QMessageBox.warning(self, "Missing sheet", "Specify the source sheet name.")
            return False
        return True

    def _guard_mix_config(self, cfg) -> bool:
        if not cfg.sheet:
            QMessageBox.warning(self, "Missing sheet", "Specify the source sheet name.")
            return False
        return True

    # ------------------------------------------------------------------
    # Transfer: pressure vessels
    # ------------------------------------------------------------------

    def _run_pv_transfer(self) -> None:
        if not self._guard_paths():
            return

        QMessageBox.information(
            self,
            "Reminder",
            "Study (col B) and Folder (col C) are not populated by this "
            "transfer. Fill these in manually in the workbook editor before "
            "importing into Phast.",
        )

        cfg_pv = self.pv_tab.source_config()
        if not self._guard_pv_config(cfg_pv):
            return

        _dp = self._decimal_places_spin.value()
        opts   = PressureVesselOptions(
            inventory_mode=self.pv_tab.inventory_mode(),
            assume_unlimited=self.pv_tab.assume_unlimited(),
            transfer_mode=self._transfer_mode(),
            decimal_places=None if _dp < 0 else _dp,
        )
        report = TransferReport()

        try:
            self.logInfo.emit(f"Loading source: {self.source_selector.path()}")
            src_wb = load_workbook(self.source_selector.path(), data_only=True)

            rows = read_pressure_vessels(src_wb, cfg_pv, opts, report)
            self.logInfo.emit(f"Read {len(rows)} pressure vessel(s) from source.")

            mix_cfg = self.mix_tab.source_config()
            if mix_cfg.sheet:
                try:
                    mix_streams = collect_mixture_stream_names(src_wb, mix_cfg)
                    pv_refs = {r.stream for r in rows if r.stream}
                    warn_unresolved_pv_streams(pv_refs, mix_streams, report)
                except Exception as e:  # noqa: BLE001
                    report.warnings.append(f"Cross-tab validation skipped: {e}")

            write_pressure_vessels(self._target_wb, rows, opts, report)

        except Exception as e:  # noqa: BLE001
            report.errors.append(f"{type(e).__name__}: {e}")
            self.logError.emit(traceback.format_exc())

        self.configChanged.emit()
        self._render_report(report, "Pressure Vessels")
        self.transferComplete.emit(not report.errors)

    # ------------------------------------------------------------------
    # Transfer: mixtures
    # ------------------------------------------------------------------

    def _run_mix_transfer(self) -> None:
        if not self._guard_paths():
            return

        cfg_mix = self.mix_tab.source_config()
        if not self._guard_mix_config(cfg_mix):
            return

        _dp = self._decimal_places_spin.value()
        opts   = MixtureOptions(
            composition_basis=self.mix_tab.composition_basis(),
            smart_match=self.mix_tab.smart_match(),
            user_overrides=self._mixture_user_overrides,
            transfer_mode=self._transfer_mode(),
            skip_zero=self.mix_tab.skip_zero(),
            decimal_places=None if _dp < 0 else _dp,
        )
        report = TransferReport()

        try:
            self.logInfo.emit(f"Loading source: {self.source_selector.path()}")
            src_wb = load_workbook(self.source_selector.path(), data_only=True)

            records = read_mixtures(src_wb, cfg_mix, opts, report)
            self.logInfo.emit(
                f"Read {len(records)} mixture(s) with "
                f"{sum(len(r.components) for r in records)} component row(s)."
            )

            pv_cfg = self.pv_tab.source_config()
            if pv_cfg.sheet:
                try:
                    pv_refs     = collect_pv_stream_refs(src_wb, pv_cfg)
                    mix_streams = {r.name for r in records}
                    warn_unresolved_pv_streams(pv_refs, mix_streams, report)
                except Exception as e:  # noqa: BLE001
                    report.warnings.append(f"Cross-tab validation skipped: {e}")

            write_mixtures(self._target_wb, records, opts, report)

        except Exception as e:  # noqa: BLE001
            report.errors.append(f"{type(e).__name__}: {e}")
            self.logError.emit(traceback.format_exc())

        self.configChanged.emit()
        self._render_report(report, "Mixtures")
        self.transferComplete.emit(not report.errors)

    # ------------------------------------------------------------------
    # Transfer: leaks
    # ------------------------------------------------------------------

    def _run_leak_transfer(self) -> None:
        if not self._guard_paths():
            return

        opts = self.leak_tab.leak_options(self._transfer_mode())
        if not opts.leak_sizes:
            QMessageBox.warning(
                self, "No leak sizes",
                "Enter at least one leak name before transferring.",
            )
            return

        if opts.fbr_enabled and not self.pv_tab.source_config().sheet:
            QMessageBox.warning(
                self, "FBR lookup",
                "FBR is enabled but the Pressure Vessels tab has no "
                "source sheet configured. Configure it there first.",
            )
            return

        report = TransferReport()

        try:
            pv_records = read_pv_names_from_target(self._target_wb, report)
            self.logInfo.emit(
                f"Found {len(pv_records)} pressure vessel(s) in workbook."
            )
            if not pv_records:
                report.warnings.append(
                    "No pressure vessels found in the Pressure vessel sheet. "
                    "Transfer pressure vessels first."
                )

            fbr_diameters: dict[str, float] = {}
            if opts.fbr_enabled:
                pv_cfg = self.pv_tab.source_config()
                self.logInfo.emit(
                    f"Loading source for FBR lookup: {self.source_selector.path()}"
                )
                src_wb = load_workbook(self.source_selector.path(), data_only=True)
                fbr_src = LeakSourceConfig(
                    sheet=pv_cfg.sheet,
                    name_col=pv_cfg.name_col,
                    start_row=pv_cfg.start_row,
                    max_line_size_col=self.leak_tab.fbr_col_letter(),
                )
                fbr_diameters = read_fbr_diameters(src_wb, fbr_src, report)
                self.logInfo.emit(
                    f"Read FBR diameters for {len(fbr_diameters)} section(s)."
                )

            write_leaks(self._target_wb, pv_records, opts, fbr_diameters, report)

        except Exception as e:  # noqa: BLE001
            report.errors.append(f"{type(e).__name__}: {e}")
            self.logError.emit(traceback.format_exc())

        self.configChanged.emit()
        self._render_report(report, "Leaks")
        self.transferComplete.emit(not report.errors)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def _render_report(self, report: TransferReport, label: str) -> None:
        self.logInfo.emit(f"--- {label} report ---")
        for line in report.info:
            self.logInfo.emit(line)
        if report.rows_written:
            self.logInfo.emit(
                f"Wrote {report.rows_written} row(s) "
                f"({report.first_row}–{report.last_row})."
            )
        else:
            self.logInfo.emit("No rows written.")
        for w in report.warnings:
            self.logWarn.emit(w)
        for e in report.errors:
            self.logError.emit(e)

        if report.errors:
            QMessageBox.critical(self, "Transfer failed", "\n\n".join(report.errors))
        elif report.warnings:
            QMessageBox.information(
                self,
                "Transfer complete (with warnings)",
                f"Wrote {report.rows_written} row(s) into workbook.\n"
                "See log for details.\nCheck the workbook editor for any issues.\n"
                "Use File → Save to persist changes.",
            )
        else:
            QMessageBox.information(
                self,
                "Transfer complete",
                f"Wrote {report.rows_written} row(s) into workbook.\n"
                "Check the workbook editor for any issues.\n"
                "Use File → Save to persist changes.",
            )
