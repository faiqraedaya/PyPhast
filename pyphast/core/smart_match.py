"""Smart matching of source component names to Phast canonical names.

Strategy (in order):

1. Exact match (case-insensitive, stripped).
2. Normalised match — strip non-alphanumerics and re-compare.
3. Smart-match dictionary lookup (built-in + user overrides from JSON).

If smart match is disabled, only steps 1 and 2 apply (and step 2 only for
exact matches against canonical names, never against shorthands).

A miss returns ``MatchResult(matched=False, name=<source name>)`` and the
caller writes the source name as-is so the transfer is not broken.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# Canonical Phast component names observed in the template.
# Keys are normalised lookup keys; values are exact Phast strings.
_DEFAULT_MAP: dict[str, str] = {
    # --- Inerts / non-hydrocarbons ---
    "N2": "NITROGEN (ASPHYXIATING)",
    "NITROGEN": "NITROGEN (ASPHYXIATING)",
    "CO2": "CARBON DIOXIDE (TOXIC)",
    "CARBONDIOXIDE": "CARBON DIOXIDE (TOXIC)",
    "H2O": "WATER",
    "WATER": "WATER",
    "H2S": "HYDROGEN SULFIDE",
    "HYDROGENSULFIDE": "HYDROGEN SULFIDE",
    "HYDROGENSULPHIDE": "HYDROGEN SULFIDE",
    "H2": "HYDROGEN",
    "HYDROGEN": "HYDROGEN",
    "O2": "OXYGEN",
    "OXYGEN": "OXYGEN",
    "CO": "CARBON MONOXIDE",
    "CARBONMONOXIDE": "CARBON MONOXIDE",
    "COS": "CARBONYL SULFIDE",
    "CARBONYLSULFIDE": "CARBONYL SULFIDE",
    "AR": "ARGON",
    "ARGON": "ARGON",
    "HE": "HELIUM",
    "HELIUM": "HELIUM",
    "SO2": "SULFUR DIOXIDE",
    "NH3": "AMMONIA (TOXIC)",
    "AMMONIA": "AMMONIA (TOXIC)",
    "HCL": "HYDROGEN CHLORIDE",
    "HF": "HYDROGEN FLUORIDE",
    "HCN": "HYDROGEN CYANIDE",

    # --- n-Alkanes (carbon-number shorthand and IUPAC) ---
    "C1": "METHANE",
    "METHANE": "METHANE",
    "C2": "ETHANE",
    "ETHANE": "ETHANE",
    "C3": "PROPANE",
    "PROPANE": "PROPANE",
    "NC4": "N-BUTANE",
    "NBUTANE": "N-BUTANE",
    "BUTANE": "N-BUTANE",
    "NC5": "N-PENTANE",
    "NPENTANE": "N-PENTANE",
    "PENTANE": "N-PENTANE",
    "NC6": "N-HEXANE",
    "NHEXANE": "N-HEXANE",
    "HEXANE": "N-HEXANE",
    "NC7": "N-HEPTANE",
    "NHEPTANE": "N-HEPTANE",
    "HEPTANE": "N-HEPTANE",
    "NC8": "N-OCTANE",
    "NOCTANE": "N-OCTANE",
    "OCTANE": "N-OCTANE",
    "NC9": "N-NONANE",
    "NNONANE": "N-NONANE",
    "NONANE": "N-NONANE",
    "NC10": "N-DECANE",
    "NDECANE": "N-DECANE",
    "DECANE": "N-DECANE",
    "NC11": "N-UNDECANE",
    "NC12": "N-DODECANE",
    "NC15": "N-PENTADECANE",
    "NC20": "N-EICOSANE",
    "NEICOSANE": "N-EICOSANE",
    "EICOSANE": "N-EICOSANE",

    # --- iso-Alkanes ---
    "IC4": "ISOBUTANE",
    "ICE4": "ISOBUTANE",
    "IBUTANE": "ISOBUTANE",
    "ISOBUTANE": "ISOBUTANE",
    "IC5": "ISOPENTANE",
    "IPENTANE": "ISOPENTANE",
    "ISOPENTANE": "ISOPENTANE",

    # --- Aromatics ---
    "BENZENE": "BENZENE",
    "TOLUENE": "TOLUENE",
    "MXYLENE": "M-XYLENE",
    "META-XYLENE": "M-XYLENE",
    "PXYLENE": "P-XYLENE",
    "PARA-XYLENE": "P-XYLENE",
    "OXYLENE": "O-XYLENE",
    "ORTHO-XYLENE": "O-XYLENE",
    "XYLENE": "M-XYLENE",  # ambiguous; bias to m-xylene
    "ETHYLBENZENE": "ETHYLBENZENE",

    # --- Olefins ---
    "C2=": "ETHYLENE",
    "ETHYLENE": "ETHYLENE",
    "ETHENE": "ETHYLENE",
    "C3=": "PROPYLENE",
    "PROPYLENE": "PROPYLENE",
    "PROPENE": "PROPYLENE",

    # --- Oxygenates / alcohols ---
    "MEOH": "METHANOL",
    "METHANOL": "METHANOL",
    "ETOH": "ETHANOL",
    "ETHANOL": "ETHANOL",
}


_NORMALISE_STRIP_RE = re.compile(r"[\s_\-/().,]+")


def _normalise(name: str) -> str:
    """Uppercase and strip whitespace, dashes, underscores, parens, etc.
    Used as the lookup key for the smart map.
    """
    return _NORMALISE_STRIP_RE.sub("", name.strip().upper())


@dataclass(frozen=True)
class MatchResult:
    matched: bool
    name: str  # canonical Phast name when matched, source name otherwise
    method: str  # "exact" | "normalised" | "smart" | "none"


class ComponentMatcher:
    """Maps source component names to Phast canonical names."""

    def __init__(
        self,
        smart_match: bool = True,
        user_overrides: dict[str, str] | None = None,
    ) -> None:
        self.smart_match = smart_match
        # Merge user overrides on top of defaults (overrides win).
        merged = dict(_DEFAULT_MAP)
        if user_overrides:
            for k, v in user_overrides.items():
                merged[_normalise(k)] = v.strip()
        self._map = merged
        # Reverse set of canonical names for exact-against-canonical detection.
        self._canonical = {v.upper(): v for v in merged.values()}

    def match(self, source_name: str) -> MatchResult:
        if source_name is None:
            return MatchResult(False, "", "none")
        raw = str(source_name).strip()
        if not raw:
            return MatchResult(False, "", "none")

        # 1. Exact match against a known canonical name (case-insensitive).
        upper = raw.upper()
        if upper in self._canonical:
            return MatchResult(True, self._canonical[upper], "exact")

        # 2. Normalised key against canonical names.
        norm = _normalise(raw)
        for canon_upper, canon in self._canonical.items():
            if _normalise(canon) == norm:
                return MatchResult(True, canon, "normalised")

        # 3. Smart-match dictionary lookup.
        if self.smart_match and norm in self._map:
            return MatchResult(True, self._map[norm], "smart")

        # Miss — caller decides what to do (per spec: write source as-is).
        return MatchResult(False, raw, "none")
