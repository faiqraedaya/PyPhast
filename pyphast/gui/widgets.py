"""Small reusable widgets and helpers for the PyPhast GUI."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QRegularExpressionValidator
from PySide6.QtCore import QRegularExpression
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from ..core.columns import is_valid_col_letter


class ColumnLetterEdit(QLineEdit):
    """QLineEdit constrained to valid Excel column letters (A–XFD)."""

    def __init__(self, default: str = "A", parent: QWidget | None = None):
        super().__init__(default, parent)
        rx = QRegularExpression(r"^[A-Za-z]{1,3}$")
        self.setValidator(QRegularExpressionValidator(rx, self))
        self.setMaxLength(3)
        self.setMaximumWidth(60)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont("Consolas")
        f.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(f)

    def value(self) -> str:
        return self.text().strip().upper()

    def is_valid(self) -> bool:
        return is_valid_col_letter(self.text())


class FileSelector(QWidget):
    """Read-only path field + 'Browse…' button. Emits ``pathChanged`` on change."""

    pathChanged = Signal(str)

    def __init__(
        self,
        label: str,
        caption: str = "Select file",
        filter_str: str = "Excel files (*.xlsx *.xlsm)",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._caption = caption
        self._filter = filter_str

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel(label)
        self._label.setMinimumWidth(80)
        self._edit = QLineEdit()
        self._edit.setReadOnly(True)
        self._edit.setPlaceholderText("(none selected)")
        self._btn = QPushButton("Browse…")
        self._btn.clicked.connect(self._on_browse)

        layout.addWidget(self._label)
        layout.addWidget(self._edit, 1)
        layout.addWidget(self._btn)

    def path(self) -> str:
        return self._edit.text().strip()

    def setPath(self, path: str) -> None:
        if path != self._edit.text():
            self._edit.setText(path)
            self.pathChanged.emit(path)

    def _on_browse(self) -> None:
        start_dir = self._edit.text() or ""
        path, _ = QFileDialog.getOpenFileName(
            self, self._caption, start_dir, self._filter
        )
        if path:
            self.setPath(path)


class LabeledSpinBox(QSpinBox):
    """SpinBox with sensible defaults for row numbers."""

    def __init__(
        self,
        minimum: int = 1,
        maximum: int = 1_048_576,
        value: int = 1,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setRange(minimum, maximum)
        self.setValue(value)
        self.setMaximumWidth(100)
