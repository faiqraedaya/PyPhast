# PyPhast

A desktop GUI for preparing and editing DNV Phast input spreadsheets.

---

## Features

- Tabular editor for **Pressure Vessel**, **Leak**, **Time Varying Leak**, and **Mixture** sheets with live in-cell editing.
- Collapsible hierarchy viewer showing the Workspace → Study → Folder → PV → Leak tree.
- Import data from a source workbook into the target Phast file via configurable column mappings.
- Three transfer modes: **Overwrite**, **Append**, and **Skip existing** rows.
- FBR (full-bore rupture) diameter lookup — filters leak sizes above the PV max line size.
- Phase-based routing: vapour/supercritical PVs are written to the Time Varying Leak sheet; liquid PVs to the Leak sheet.
- Smart-match maps common component name shorthands (e.g. `H2O → Water`) to Phast names.

---

## Requirements

- Python ≥ 3.13
- [PySide6](https://pypi.org/project/PySide6/) (Qt 6 bindings — installed separately; see below)
- [openpyxl](https://pypi.org/project/openpyxl/) ≥ 3.1.5

Tested on Windows. PySide6 is a runtime dependency not listed in `pyproject.toml`; install it explicitly.

---

## Installation

```bash
git clone https://github.com/faiqraedaya/PyPhast
cd PyPhast
pip install -e .
pip install PySide6
```

With [uv](https://github.com/astral-sh/uv) (a `uv.lock` is present):

```bash
git clone https://github.com/faiqraedaya/PyPhast
cd PyPhast
uv sync
uv pip install PySide6
```

---

## Quick start

```bash
python -m pyphast
```

The application opens a three-panel window. Use **File → Open** to load a target Phast `.xlsx` file.

---

## Usage

### Workbook editor (centre panel)

Displays the four main Phast data sheets in separate tabs. Click any cell to edit. Changes are held in memory until **File → Save** (or Ctrl+S).

### Hierarchy viewer (left panel)

Collapsible tree of the loaded workbook:

```
Workspace
└── Study
    └── Folder / Sub-folder (up to 5 levels)
        └── Pressure vessel
            └── Leak: orifice diameter
```

Right-click nodes to insert, delete, copy, or rename rows directly in the target workbook.

### Import panel (right panel)

Import data from a separate source workbook into the open Phast file.

| Tab | Writes to sheet |
|-----|-----------------|
| **Pressure Vessels** | `Pressure vessel` — name, stream, pressure, temperature, inventory |
| **Leaks** | `Leak` — one row per leak size per vessel, optional FBR diameter lookup |
| **Time Varying Leaks** | `Time varying leak` — vapour/SC-phase PVs routed here automatically |
| **Mixtures** | `Mixture` — stream IDs and component composition vectors |

Configure source column mappings, transfer mode, and leak sizes in each tab, then click **Transfer**.

---

## Configuration

Settings are persisted as JSON across sessions.

| Platform | Config file location |
|----------|----------------------|
| Windows  | `%APPDATA%\PyPhast\config.json` |
| macOS    | `~/Library/Application Support/PyPhast/config.json` |
| Linux    | `~/.config/PyPhast/config.json` |

Key settings (all configurable in-app; no manual editing required):

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `transfer_mode` | string | `"overwrite"` | `"overwrite"` \| `"append"` \| `"skip_existing"` |
| `import_decimal_places` | int | `-1` | Decimal places for imported values; `-1` = no rounding |
| `pressure_vessel.inventory_mode` | string | `"mass"` | `"mass"` or `"volume"` |
| `pressure_vessel.model_vapour_as_tvl` | bool | `false` | Route vapour-phase PVs to TVL sheet |
| `mixture.smart_match` | bool | `true` | Match component shorthands to Phast names |
| `mixture.skip_zero` | bool | `true` | Omit zero-fraction components on import |
| `leak.fbr_enabled` | bool | `false` | Enable full-bore rupture diameter lookup |

---

## Behaviour notes

- **Non-standard Phast archives** (`xl/workbook22.xml`, etc.) are normalised in memory on load — no manual fix-up needed.
- **Sheet lookup** is case-insensitive (`MIXTURE`, `Mixture`, and `mixture` all resolve correctly).
- **Row 63** is the first data row in all target sheets (Phast template convention).
- **Study and Folder columns** (B, C–G) on the Pressure vessel sheet are not populated by the PV import — a reminder appears before each transfer.
- **Last opened file** is remembered and reopened automatically on next launch (up to 10 recent files).

---

## Development

```bash
git clone https://github.com/faiqraedaya/PyPhast
cd PyPhast
pip install -e .
pip install PySide6
```

Run tests:

```bash
python -m pytest tests/
```

No linter or formatter is configured in the repository.

---

## Project structure

```
pyphast/
├── __init__.py                # version, app name
├── __main__.py                # entry point: python -m pyphast
├── config.py                  # JSON config persistence (AppConfig dataclass)
├── core/
│   ├── columns.py             # column letter ↔ index utilities
│   ├── excel_io.py            # load/save, Phast archive normalisation
│   ├── target_layout.py       # target sheet column/sheet constants
│   ├── sheet_utils.py         # range scan, clear, iterate helpers
│   ├── smart_match.py         # component name matcher + default dictionary
│   ├── pressure_vessel.py     # PV read / write
│   ├── leak.py                # Leak read / write
│   ├── time_varying_leak.py   # TVL read / write, phase-based routing
│   ├── pv_operations.py       # insert / delete / copy / reorder PV+Leak rows
│   ├── mixture.py             # Mixture read / write
│   └── validation.py          # cross-tab stream reference checks
└── gui/
    ├── main_window.py         # window, menu, layout, transfer orchestration
    ├── hierarchy_viewer.py    # left-panel tree widget
    ├── target_viewer.py       # centre-panel workbook editor tables
    ├── import_panel.py        # right-panel tab container
    ├── pressure_vessel_tab.py # import panel — PV tab
    ├── leak_tab.py            # import panel — Leak tab
    ├── time_varying_leak_tab.py # import panel — TVL tab
    ├── mixture_tab.py         # import panel — Mixture tab
    └── widgets.py             # FileSelector, ColumnLetterEdit, LabeledSpinBox
```

---

## License

This project is provided under the MIT License. See [LICENSE](LICENSE).

<!-- Unverified: PyPI availability. PySide6 is used at runtime but not listed in pyproject.toml dependencies. -->
