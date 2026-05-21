# PyPhast

A desktop GUI for preparing and editing DNV Phast input spreadsheets.

## Features

- Tabular editor for Pressure Vessel, Leak, Time Varying Leak, and Mixture sheets with live in-cell editing.
- Collapsible hierarchy viewer showing the Workspace → Study → Folder → PV → Leak tree.
- Import data from a source workbook into a target Phast file via configurable column mappings.
- Three transfer modes: Overwrite, Append, and Skip existing rows.
- Phase-based routing: vapour/supercritical PVs are written to the Time Varying Leak sheet; liquid PVs to the Leak sheet.

## Installation

```bash
git clone https://github.com/faiqraedaya/PyPhast
cd PyPhast
uv sync
uv pip install PySide6
```

## Usage

```bash
uv run python -m pyphast
```

## License

[MIT](LICENSE)
