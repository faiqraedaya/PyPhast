"""Pressure Vessels tab UI."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ..config import PressureVesselConfig
from ..core.pressure_vessel import (
    InventoryMode,
    PressureVesselSourceConfig,
)
from .widgets import ColumnLetterEdit, LabeledSpinBox


class PressureVesselTab(QWidget):
    """Configures and triggers a pressure vessel transfer."""

    transferRequested = Signal()
    """Emitted when the user clicks the Transfer button. The main window
    reads :pymeth:`source_config` and :pymeth:`options_partial` to perform
    the transfer.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._preferred_sheet: str = ""
        self._build_ui()

    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # --- Source group --------------------------------------------------
        src_group = QGroupBox("Source (isolatable section table)")
        src_form = QFormLayout(src_group)

        self.sheet_combo = QComboBox()
        self.sheet_combo.setPlaceholderText("(select source file first)")

        self.start_row = LabeledSpinBox(minimum=1, value=5)

        self.name_col = ColumnLetterEdit("A")
        self.stream_col = ColumnLetterEdit("B")
        self.pressure_col = ColumnLetterEdit("C")
        self.temperature_col = ColumnLetterEdit("D")
        self.inventory_col = ColumnLetterEdit("E")

        src_form.addRow("Sheet:", self.sheet_combo)
        src_form.addRow("Start row (data):", self.start_row)
        src_form.addRow("Name column:", self.name_col)
        src_form.addRow("Stream column:", self.stream_col)
        src_form.addRow("Pressure column (barg):", self.pressure_col)
        src_form.addRow("Temperature column (°C):", self.temperature_col)
        src_form.addRow("Inventory column:", self.inventory_col)

        # --- Inventory mode group -----------------------------------------
        inv_group = QGroupBox("Inventory")
        inv_layout = QHBoxLayout(inv_group)

        self.rb_mass = QRadioButton("Mass (kg)")
        self.rb_volume = QRadioButton("Volume (m³)")
        self.rb_mass.setChecked(True)
        bg = QButtonGroup(self)
        bg.addButton(self.rb_mass)
        bg.addButton(self.rb_volume)

        self.cb_unlimited = QCheckBox("Assume unlimited inventory (100,000)")
        self.cb_unlimited.toggled.connect(self._on_unlimited_toggled)

        inv_layout.addWidget(self.rb_mass)
        inv_layout.addWidget(self.rb_volume)
        inv_layout.addStretch(1)
        inv_layout.addWidget(self.cb_unlimited)

        # --- Vapour phase routing group ------------------------------------
        tvl_group = QGroupBox("Vapour phase routing")
        tvl_layout = QVBoxLayout(tvl_group)

        self.cb_tvl = QCheckBox("Model vapour releases as time varying leaks")
        self.cb_tvl.toggled.connect(self._on_tvl_toggled)

        tvl_form_widget = QWidget()
        tvl_form = QFormLayout(tvl_form_widget)
        tvl_form.setContentsMargins(0, 0, 0, 0)
        self.phase_col = ColumnLetterEdit("")
        self.phase_col.setPlaceholderText("e.g. F")
        tvl_form.addRow("Phase column (source):", self.phase_col)
        self._tvl_form_widget = tvl_form_widget
        self._tvl_form_widget.setEnabled(False)

        tvl_note = QLabel(
            "When enabled, sections with phase V or SC are written to the "
            "'Time varying leak' sheet; all other phases go to 'Leak'."
        )
        tvl_note.setWordWrap(True)
        tvl_note.setStyleSheet("color: #666;")

        tvl_layout.addWidget(self.cb_tvl)
        tvl_layout.addWidget(self._tvl_form_widget)
        tvl_layout.addWidget(tvl_note)

        # --- Action --------------------------------------------------------
        action_layout = QHBoxLayout()
        self.btn_transfer = QPushButton("Transfer to Pressure vessel sheet")
        self.btn_transfer.clicked.connect(self.transferRequested.emit)
        action_layout.addStretch(1)
        action_layout.addWidget(self.btn_transfer)

        self.note_label = QLabel(
            "Note: Study (col B) and Folder (col C) are NOT populated by "
            "this transfer — they must be filled in manually before importing "
            "into Phast."
        )
        self.note_label.setWordWrap(True)
        self.note_label.setStyleSheet("color: #666;")

        # --- Compose -------------------------------------------------------
        layout.addWidget(src_group)
        layout.addWidget(inv_group)
        layout.addWidget(tvl_group)
        layout.addWidget(self.note_label)
        layout.addStretch(1)
        layout.addLayout(action_layout)

    # ------------------------------------------------------------------

    def _on_unlimited_toggled(self, checked: bool) -> None:
        self.inventory_col.setDisabled(checked)

    def _on_tvl_toggled(self, checked: bool) -> None:
        self._tvl_form_widget.setEnabled(checked)

    # ------------------------------------------------------------------

    def set_sheet_names(self, names: list[str]) -> None:
        self.sheet_combo.blockSignals(True)
        self.sheet_combo.clear()
        self.sheet_combo.addItems(names)
        if self._preferred_sheet and self._preferred_sheet in names:
            self.sheet_combo.setCurrentText(self._preferred_sheet)
        elif names:
            self.sheet_combo.setCurrentIndex(0)
        self.sheet_combo.blockSignals(False)

    def source_config(self) -> PressureVesselSourceConfig:
        return PressureVesselSourceConfig(
            sheet=self.sheet_combo.currentText().strip(),
            start_row=self.start_row.value(),
            name_col=self.name_col.value(),
            stream_col=self.stream_col.value(),
            pressure_col=self.pressure_col.value(),
            temperature_col=self.temperature_col.value(),
            inventory_col=self.inventory_col.value(),
        )

    def inventory_mode(self) -> InventoryMode:
        return (
            InventoryMode.VOLUME if self.rb_volume.isChecked() else InventoryMode.MASS
        )

    def assume_unlimited(self) -> bool:
        return self.cb_unlimited.isChecked()

    def model_vapour_as_tvl(self) -> bool:
        return self.cb_tvl.isChecked()

    def phase_col_letter(self) -> str:
        return self.phase_col.value()

    # ------------------------------------------------------------------
    # Persistence

    def load_from_config(self, cfg: PressureVesselConfig) -> None:
        self._preferred_sheet = cfg.sheet
        self.start_row.setValue(cfg.start_row)
        self.name_col.setText(cfg.name_col)
        self.stream_col.setText(cfg.stream_col)
        self.pressure_col.setText(cfg.pressure_col)
        self.temperature_col.setText(cfg.temperature_col)
        self.inventory_col.setText(cfg.inventory_col)
        if cfg.inventory_mode == "volume":
            self.rb_volume.setChecked(True)
        else:
            self.rb_mass.setChecked(True)
        self.cb_unlimited.setChecked(cfg.assume_unlimited)
        self._on_unlimited_toggled(cfg.assume_unlimited)
        self.cb_tvl.setChecked(cfg.model_vapour_as_tvl)
        self.phase_col.setText(cfg.phase_col)
        self._on_tvl_toggled(cfg.model_vapour_as_tvl)

    def save_to_config(self, cfg: PressureVesselConfig) -> None:
        cfg.sheet = self.sheet_combo.currentText()
        cfg.start_row = self.start_row.value()
        cfg.name_col = self.name_col.value()
        cfg.stream_col = self.stream_col.value()
        cfg.pressure_col = self.pressure_col.value()
        cfg.temperature_col = self.temperature_col.value()
        cfg.inventory_col = self.inventory_col.value()
        cfg.inventory_mode = self.inventory_mode().value
        cfg.assume_unlimited = self.assume_unlimited()
        cfg.model_vapour_as_tvl = self.model_vapour_as_tvl()
        cfg.phase_col = self.phase_col_letter()
