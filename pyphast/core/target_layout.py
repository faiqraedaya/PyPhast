"""Constants describing the target Phast input workbook layout.

Centralised here so all writers reference the same column letters and
defaults. Update here if the Phast template changes.
"""

from __future__ import annotations

from .columns import col_letter_to_index

# ---- Common ----------------------------------------------------------------

DATA_START_ROW = 63
"""First row of writable data in the target template."""

# ---- Pressure vessel sheet -------------------------------------------------

PV_SHEET_NAME = "Pressure vessel"

PV_COL_USE = "A"
PV_COL_STUDY = "B"
PV_COL_FOLDER = "C"
PV_COL_NAME = "H"
PV_COL_MATERIAL = "I"
PV_COL_SPECIFY_VOLUME = "J"
PV_COL_MASS_INVENTORY = "K"
PV_COL_VOLUME_INVENTORY = "L"
PV_COL_MATERIAL_TO_TRACK = "M"
PV_COL_TEMPERATURE = "O"
PV_COL_PRESSURE_GAUGE = "P"

# Used for end-of-data scan in append mode and for clearing in overwrite mode.
# User confirmed: final populated column on this sheet is EI.
PV_SCAN_FIRST_COL = "A"
PV_SCAN_LAST_COL = "EI"

PV_VALUE_USE = "Yes"
PV_VALUE_VOLUME_NO = "0 No"
PV_VALUE_VOLUME_YES = "1 Yes"

UNLIMITED_INVENTORY_VALUE = 100_000.0

# ---- Mixture sheet ---------------------------------------------------------

# NOTE: actual sheet name in the supplied template is "MIXTURE" (uppercase),
# but lookup is case-insensitive (see excel_io.find_sheet).
MIX_SHEET_NAME = "MIXTURE"

MIX_COL_USE = "A"
MIX_COL_PHYSICAL_PROPERTIES_SYSTEM = "B"
MIX_COL_MATERIALS = "C"
MIX_COL_NAME = "F"
MIX_COL_COMPONENT = "G"
MIX_COL_MASS = "H"
MIX_COL_MOLE = "I"
MIX_COL_PROPERTY_METHOD = "J"

# Columns scanned to detect last existing row (covers the multi-row block
# of components belonging to a single mixture name).
MIX_SCAN_FIRST_COL = "A"
MIX_SCAN_LAST_COL = "J"

MIX_VALUE_USE = "Yes"
MIX_VALUE_PHYSICAL_PROPERTIES_SYSTEM = "Physical Properties System"
MIX_VALUE_MATERIALS = "Materials"
MIX_VALUE_PROPERTY_METHOD = "PhastMC"


# ---- Helper indices --------------------------------------------------------


def pv_scan_col_indices() -> tuple[int, int]:
    return (
        col_letter_to_index(PV_SCAN_FIRST_COL),
        col_letter_to_index(PV_SCAN_LAST_COL),
    )


def mix_scan_col_indices() -> tuple[int, int]:
    return (
        col_letter_to_index(MIX_SCAN_FIRST_COL),
        col_letter_to_index(MIX_SCAN_LAST_COL),
    )


# ---- Leak sheet ------------------------------------------------------------

LEAK_SHEET_NAME = "Leak"

LEAK_COL_USE = "A"
LEAK_COL_STUDY = "B"
LEAK_COL_FOLDER = "C"
LEAK_COL_PV_NAME = "H"
LEAK_COL_NAME = "T"
LEAK_COL_ORIFICE_DIAMETER = "U"
LEAK_COL_OUTDOOR_RELEASE_DIRECTION = "Z"

LEAK_SCAN_FIRST_COL = "A"
LEAK_SCAN_LAST_COL = "AA"

LEAK_VALUE_USE = "Yes"
LEAK_VALUE_OUTDOOR_RELEASE_DIRECTION = "0 Horizontal"


def leak_scan_col_indices() -> tuple[int, int]:
    return (
        col_letter_to_index(LEAK_SCAN_FIRST_COL),
        col_letter_to_index(LEAK_SCAN_LAST_COL),
    )
