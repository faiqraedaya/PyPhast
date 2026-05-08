# PyPhast

A desktop editor for DNV Phast input spreadsheets.  Open a Phast workbook, inspect and edit its contents, import data from an isolatable-section workbook, then save — all without touching the file until you're ready.

---

## Features

### Workbook editor (centre panel)
Tabular view of the three main Phast data sheets — **Pressure Vessels**, **Leaks**, and **Mixtures** — with live in-cell editing.  Changes are held in memory until you explicitly save.

### Hierarchy viewer (left panel)
Collapsible tree of the loaded workbook:

```
Workspace
└── Study
    └── Folder / Sub-folder (up to 5 levels)
        └── Pressure vessel
            └── Leak: orifice diameter
```

### Import panel (right panel)
Import data from a separate source workbook (e.g. an isolatable-section table) into the open Phast file:

| Tab | Writes to |
|-----|-----------|
| **Pressure Vessels** | `Pressure vessel` sheet — name, stream, pressure, temperature, inventory |
| **Leaks** | `Leak` sheet — one row per leak size per vessel, optional FBR diameter lookup |
| **Mixtures** | `MIXTURE` sheet — stream IDs and component composition vectors |

**Transfer modes:** Overwrite (clears rows from 63 down) or Append (writes after existing data).

### Deferred save
All edits and imports modify the in-memory workbook only.  The title bar shows a `●` and the status bar shows **Modified** when there are unsaved changes.  Use **File → Save** (Ctrl+S) to write to disk.  Closing, opening, or creating a new file prompts to save if needed.

---

## Install

```bash
pip install -r requirements.txt
```

Requires Python 3.11+ and the packages below:

| Package | Version |
|---------|---------|
| PySide6 | ≥ 6.5 |
| openpyxl | ≥ 3.1 |

---

## Run

```bash
python main.py
# or
python -m PyPhast
```

---

## Menu reference

| Menu | Item | Shortcut |
|------|------|----------|
| File | New | Ctrl+N |
| File | Open… | Ctrl+O |
| File | Save | Ctrl+S |
| File | Exit | Ctrl+Q |
| Edit | Clear Pressure Vessel data… | — |
| Edit | Clear Leak data… | — |
| Edit | Clear Mixture data… | — |
| View | Expand hierarchy | Ctrl+→ |
| View | Collapse hierarchy | Ctrl+← |
| View | Show Log | Ctrl+L |
| About | About PyPhast… | — |

---

## Behaviour notes

- **Non-standard Phast archives** (`xl/workbook22.xml` etc.) are normalised in memory on load — no manual fix-up needed.
- **Sheet lookup** is case-insensitive (`MIXTURE`, `Mixture`, `mixture` all work).
- **Row 63** is the first data row in all target sheets (Phast template convention).
- **Study and Folder columns** (B, C–G) on the Pressure vessel sheet are not populated by the PV import — a reminder appears before each transfer.
- **Smart-match** maps common component shorthands to Phast names (e.g. `H2O → Water`); misses are written as-is and logged.
- **Specified condition** (col N) and **Liquid mole fraction** (col Q) on the Pressure vessel sheet are left blank — Phast computes them on import.
- **Last opened file** is remembered and reopened automatically on next launch.

---

## Project layout

```
PyPhast/
├── config.py                  # JSON config persistence
├── core/
│   ├── columns.py             # column letter ↔ index utilities
│   ├── excel_io.py            # load/save, Phast archive normalisation
│   ├── target_layout.py       # target sheet column/sheet constants
│   ├── sheet_utils.py         # range scan, clear, iterate helpers
│   ├── smart_match.py         # component name matcher + default dictionary
│   ├── pressure_vessel.py     # PV read / write
│   ├── leak.py                # Leak read / write
│   ├── mixture.py             # Mixture read / write
│   └── validation.py          # cross-tab stream reference checks
└── gui/
    ├── main_window.py         # window, menu, layout, transfer orchestration
    ├── hierarchy_viewer.py    # left-panel tree widget
    ├── target_viewer.py       # centre-panel workbook editor tables
    ├── pressure_vessel_tab.py # import panel — PV tab
    ├── leak_tab.py            # import panel — Leak tab
    ├── mixture_tab.py         # import panel — Mixture tab
    └── widgets.py             # FileSelector, ColumnLetterEdit, LabeledSpinBox
```

---

## Extending

To add support for a new Phast sheet type:

1. Add layout constants to `core/target_layout.py`.
2. Create `core/<type>.py` with `<Type>SourceConfig`, `<Type>Options`, `read_*`, `write_*`.
3. Create `gui/<type>_tab.py`.
4. Wire into `gui/main_window.py` (one tab + one transfer handler).
5. Extend `config.py` with a matching config dataclass.
