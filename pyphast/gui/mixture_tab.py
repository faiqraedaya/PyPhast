"""Mixtures tab UI."""

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

from ..config import MixtureConfig
from ..core.mixture import CompositionBasis, MixtureSourceConfig
from .widgets import ColumnLetterEdit, LabeledSpinBox


class MixtureTab(QWidget):
    """Configures and triggers a mixture transfer."""

    transferRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._preferred_sheet: str = ""
        self._build_ui()

    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # --- Source group --------------------------------------------------
        src_group = QGroupBox("Source (composition matrix)")
        src_form = QFormLayout(src_group)

        self.sheet_combo = QComboBox()
        self.sheet_combo.setPlaceholderText("(select source file first)")

        self.header_row = LabeledSpinBox(minimum=1, value=4)
        self.start_row = LabeledSpinBox(minimum=1, value=5)

        self.stream_col = ColumnLetterEdit("J")
        self.components_first_col = ColumnLetterEdit("U")
        self.components_last_col = ColumnLetterEdit("AG")

        src_form.addRow("Sheet:", self.sheet_combo)
        src_form.addRow("Header row (component names):", self.header_row)
        src_form.addRow("Start row (data):", self.start_row)
        src_form.addRow("Stream column:", self.stream_col)
        src_form.addRow(
            "Components — first column:", self.components_first_col
        )
        src_form.addRow(
            "Components — last column:", self.components_last_col
        )

        # --- Composition basis --------------------------------------------
        basis_group = QGroupBox("Composition basis")
        basis_layout = QHBoxLayout(basis_group)
        self.rb_mole = QRadioButton("Mole fraction / %")
        self.rb_mass = QRadioButton("Mass fraction / %")
        self.rb_mole.setChecked(True)
        bg = QButtonGroup(self)
        bg.addButton(self.rb_mole)
        bg.addButton(self.rb_mass)
        basis_layout.addWidget(self.rb_mole)
        basis_layout.addWidget(self.rb_mass)
        basis_layout.addStretch(1)

        # --- Matching options ---------------------------------------------
        match_group = QGroupBox("Component name matching")
        match_layout = QVBoxLayout(match_group)
        self.cb_smart = QCheckBox("Smart match")
        self.cb_smart.setChecked(True)
        self.cb_smart_note = QLabel(
            "Enable smart matching of component names from common short"
            " names to Phast-compatible names (e.g. 'H2O' matches 'Water')."
        )
        self.cb_smart_note.setWordWrap(True)
        self.cb_smart_note.setStyleSheet("color: #666;")

        self.cb_skip_zero = QCheckBox("Skip zero-composition components")
        self.cb_skip_zero.setChecked(True)
        self.cb_skip_zero_note = QLabel(
            "When enabled, any component with zero composition in all streams "
            "will be skipped and not transferred to the MIXTURE sheet."
        )
        self.cb_skip_zero_note.setWordWrap(True)
        self.cb_skip_zero_note.setStyleSheet("color: #666;")

        match_layout.addWidget(self.cb_smart)
        match_layout.addWidget(self.cb_smart_note)
        match_layout.addWidget(self.cb_skip_zero)
        match_layout.addWidget(self.cb_skip_zero_note)
        match_layout.addStretch(1)

        # --- Action --------------------------------------------------------
        action_layout = QHBoxLayout()
        self.btn_transfer = QPushButton("Transfer to MIXTURE sheet")
        self.btn_transfer.clicked.connect(self.transferRequested.emit)
        action_layout.addStretch(1)
        action_layout.addWidget(self.btn_transfer)

        self.note_label = QLabel(
            "Unmatched component names are written as-is to be corrected "
            "manually in Phast (warnings shown in the log)."
        )
        self.note_label.setWordWrap(True)
        self.note_label.setStyleSheet("color: #666;")

        # --- Compose -------------------------------------------------------
        layout.addWidget(src_group)
        layout.addWidget(basis_group)
        layout.addWidget(match_group)
        layout.addWidget(self.note_label)
        layout.addStretch(1)
        layout.addLayout(action_layout)

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

    def source_config(self) -> MixtureSourceConfig:
        return MixtureSourceConfig(
            sheet=self.sheet_combo.currentText().strip(),
            header_row=self.header_row.value(),
            start_row=self.start_row.value(),
            stream_col=self.stream_col.value(),
            components_first_col=self.components_first_col.value(),
            components_last_col=self.components_last_col.value(),
        )

    def composition_basis(self) -> CompositionBasis:
        return (
            CompositionBasis.MASS
            if self.rb_mass.isChecked()
            else CompositionBasis.MOLE
        )

    def smart_match(self) -> bool:
        return self.cb_smart.isChecked()

    def skip_zero(self) -> bool:
        return self.cb_skip_zero.isChecked()

    # ------------------------------------------------------------------
    # Persistence

    def load_from_config(self, cfg: MixtureConfig) -> None:
        self._preferred_sheet = cfg.sheet
        self.header_row.setValue(cfg.header_row)
        self.start_row.setValue(cfg.start_row)
        self.stream_col.setText(cfg.stream_col)
        self.components_first_col.setText(cfg.components_first_col)
        self.components_last_col.setText(cfg.components_last_col)
        if cfg.composition_basis == "mass":
            self.rb_mass.setChecked(True)
        else:
            self.rb_mole.setChecked(True)
        self.cb_smart.setChecked(cfg.smart_match)
        self.cb_skip_zero.setChecked(cfg.skip_zero)

    def save_to_config(self, cfg: MixtureConfig) -> None:
        cfg.sheet = self.sheet_combo.currentText()
        cfg.header_row = self.header_row.value()
        cfg.start_row = self.start_row.value()
        cfg.stream_col = self.stream_col.value()
        cfg.components_first_col = self.components_first_col.value()
        cfg.components_last_col = self.components_last_col.value()
        cfg.composition_basis = self.composition_basis().value
        cfg.smart_match = self.smart_match()
        cfg.skip_zero = self.skip_zero()
