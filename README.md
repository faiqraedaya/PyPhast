# PyPhast

A desktop editor for DNV Phast input spreadsheets.

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
| **Mixtures** | `Mixture` sheet — stream IDs and component composition vectors |

**Transfer modes:** Overwrite (clears existing rows) or Append (writes after existing data).

---

## Install

1. Clone the repository:
   ```bash
   git clone https://github.com/faiqraedaya/PyPhast
   cd "PyPhast"
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage 

1. Launch the application:
   ```bash
   python main.py
   ```

   Or, to run directly as a module:
   ```bash
   python -m PyPhast
   ```

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

## Project structure

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

## License

This project is provided under the MIT License.