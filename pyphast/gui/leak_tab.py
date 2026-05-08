"""Leaks tab UI."""

from __future__ import annotations

from PySide6.QtCore import QRegularExpression, Signal
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import LeakConfig, LeakSizeConfig
from ..core.leak import LeakOptions, LeakSizeEntry
from ..core.pressure_vessel import TransferMode
from .widgets import ColumnLetterEdit

_NUM_LEAKS = 10


class _DiameterEdit(QLineEdit):
    """QLineEdit accepting positive numbers or empty string."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        rx = QRegularExpression(r"^\d*\.?\d*$")
        self.setValidator(QRegularExpressionValidator(rx, self))
        self.setMaximumWidth(110)
        self.setPlaceholderText("e.g. 25")

    def float_value(self) -> float | None:
        t = self.text().strip()
        if not t:
            return None
        try:
            return float(t)
        except ValueError:
            return None


class LeakTab(QWidget):
    """Configures and triggers a Leak sheet transfer."""

    transferRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name_edits: list[QLineEdit] = []
        self._diameter_edits: list[_DiameterEdit] = []
        self._build_ui()

    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # --- Leak sizes table ---------------------------------------------
        sizes_group = QGroupBox("Leak sizes (up to 10)")
        grid = QGridLayout(sizes_group)
        grid.setColumnStretch(1, 1)

        grid.addWidget(QLabel("<b>#</b>"), 0, 0)
        grid.addWidget(QLabel("<b>Name</b>"), 0, 1)
        grid.addWidget(QLabel("<b>Orifice diameter (mm)</b>"), 0, 2)

        for i in range(_NUM_LEAKS):
            name_edit = QLineEdit()
            name_edit.setPlaceholderText(f"Leak {i + 1} name")
            name_edit.textChanged.connect(self._refresh_diameter_states)
            diam_edit = _DiameterEdit()
            self._name_edits.append(name_edit)
            self._diameter_edits.append(diam_edit)
            grid.addWidget(QLabel(str(i + 1)), i + 1, 0)
            grid.addWidget(name_edit, i + 1, 1)
            grid.addWidget(diam_edit, i + 1, 2)

        # --- FBR group ----------------------------------------------------
        fbr_group = QGroupBox("Full-bore rupture (FBR)")
        fbr_layout = QVBoxLayout(fbr_group)

        self.cb_fbr = QCheckBox(
            "Use source file column for FBR orifice diameter"
        )
        self.cb_fbr.toggled.connect(self._on_fbr_toggled)

        fbr_form_widget = QWidget()
        fbr_form = QFormLayout(fbr_form_widget)
        fbr_form.setContentsMargins(0, 0, 0, 0)
        self.fbr_col = ColumnLetterEdit("Z")
        fbr_form.addRow("Max line size column (source):", self.fbr_col)
        self._fbr_form_widget = fbr_form_widget
        self._fbr_form_widget.setEnabled(False)

        fbr_note = QLabel(
            "When enabled, any leak named 'FBR' will use this source column "
            "as its orifice diameter. The source sheet and name column are "
            "taken from the Pressure Vessels tab."
        )
        fbr_note.setWordWrap(True)
        fbr_note.setStyleSheet("color: #666;")

        fbr_layout.addWidget(self.cb_fbr)
        fbr_layout.addWidget(self._fbr_form_widget)
        fbr_layout.addWidget(fbr_note)

        # --- Action -------------------------------------------------------
        action_layout = QHBoxLayout()
        self.btn_transfer = QPushButton("Transfer to Leak sheet")
        self.btn_transfer.clicked.connect(self.transferRequested.emit)
        action_layout.addStretch(1)
        action_layout.addWidget(self.btn_transfer)

        layout.addWidget(sizes_group)
        layout.addWidget(fbr_group)
        layout.addStretch(1)
        layout.addLayout(action_layout)

    # ------------------------------------------------------------------

    def _on_fbr_toggled(self, checked: bool) -> None:
        self._fbr_form_widget.setEnabled(checked)
        self._refresh_diameter_states()

    def _refresh_diameter_states(self) -> None:
        fbr_active = self.cb_fbr.isChecked()
        for name_edit, diam_edit in zip(self._name_edits, self._diameter_edits):
            is_fbr_row = fbr_active and name_edit.text().strip().upper() == "FBR"
            diam_edit.setEnabled(not is_fbr_row)
            diam_edit.setPlaceholderText(
                "(from source file)" if is_fbr_row else "e.g. 25"
            )

    # ------------------------------------------------------------------

    def fbr_enabled(self) -> bool:
        return self.cb_fbr.isChecked()

    def fbr_col_letter(self) -> str:
        return self.fbr_col.value()

    def leak_options(self, transfer_mode: TransferMode) -> LeakOptions:
        sizes: list[LeakSizeEntry] = []
        for name_edit, diam_edit in zip(self._name_edits, self._diameter_edits):
            name = name_edit.text().strip()
            if not name:
                continue
            sizes.append(LeakSizeEntry(
                name=name,
                orifice_diameter=diam_edit.float_value(),
            ))
        return LeakOptions(
            leak_sizes=sizes,
            fbr_enabled=self.cb_fbr.isChecked(),
            transfer_mode=transfer_mode,
        )

    # ------------------------------------------------------------------
    # Persistence

    def load_from_config(self, cfg: LeakConfig) -> None:
        for i, entry in enumerate(cfg.leak_sizes[:_NUM_LEAKS]):
            self._name_edits[i].setText(entry.name)
            self._diameter_edits[i].setText(entry.orifice_diameter)
        self.cb_fbr.setChecked(cfg.fbr_enabled)
        self.fbr_col.setText(cfg.fbr_max_line_size_col)
        self._on_fbr_toggled(cfg.fbr_enabled)

    def save_to_config(self, cfg: LeakConfig) -> None:
        for i in range(_NUM_LEAKS):
            cfg.leak_sizes[i] = LeakSizeConfig(
                name=self._name_edits[i].text().strip(),
                orifice_diameter=self._diameter_edits[i].text().strip(),
            )
        cfg.fbr_enabled = self.cb_fbr.isChecked()
        cfg.fbr_max_line_size_col = self.fbr_col.value()
