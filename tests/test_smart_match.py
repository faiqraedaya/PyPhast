"""Tests for pyphast.core.smart_match."""

import pytest

from pyphast.core.smart_match import ComponentMatcher, MatchResult


class TestExactMatch:
    """Source name is (or normalises to) a canonical Phast name."""

    def test_exact_canonical_methane(self):
        m = ComponentMatcher()
        r = m.match("METHANE")
        assert r == MatchResult(matched=True, name="METHANE", method="exact")

    def test_exact_canonical_case_insensitive(self):
        m = ComponentMatcher()
        r = m.match("methane")
        assert r.matched is True
        assert r.name == "METHANE"
        assert r.method == "exact"

    def test_exact_canonical_mixed_case(self):
        m = ComponentMatcher()
        r = m.match("Methane")
        assert r.matched is True
        assert r.name == "METHANE"

    def test_exact_multi_word_canonical(self):
        # "NITROGEN (ASPHYXIATING)" is the canonical name
        m = ComponentMatcher()
        r = m.match("NITROGEN (ASPHYXIATING)")
        assert r.matched is True
        assert r.name == "NITROGEN (ASPHYXIATING)"
        assert r.method == "exact"

    def test_exact_hyphenated_canonical(self):
        m = ComponentMatcher()
        r = m.match("N-BUTANE")
        assert r.matched is True
        assert r.name == "N-BUTANE"
        assert r.method == "exact"

    def test_exact_water(self):
        m = ComponentMatcher()
        r = m.match("WATER")
        assert r.matched is True
        assert r.name == "WATER"
        assert r.method == "exact"

    def test_exact_water_lowercase(self):
        m = ComponentMatcher()
        r = m.match("water")
        assert r.matched is True
        assert r.name == "WATER"


class TestNormalisedMatch:
    """Non-canonical form that normalises to match a canonical Phast name."""

    def test_normalised_nbutane(self):
        # "NBUTANE" normalises the same way as "N-BUTANE"
        m = ComponentMatcher()
        r = m.match("NBUTANE")
        assert r.matched is True
        assert r.name == "N-BUTANE"
        assert r.method == "normalised"

    def test_normalised_underscore_separator(self):
        m = ComponentMatcher()
        r = m.match("n_butane")
        assert r.matched is True
        assert r.name == "N-BUTANE"
        assert r.method == "normalised"

    def test_normalised_nitrogen_with_spaces_stripped(self):
        # "nitrogen asphyxiating" strips to "NITROGENASPHYXIATING"
        # which matches normalise("NITROGEN (ASPHYXIATING)")
        m = ComponentMatcher()
        r = m.match("nitrogen asphyxiating")
        assert r.matched is True
        assert r.name == "NITROGEN (ASPHYXIATING)"
        assert r.method == "normalised"


class TestSmartMatch:
    """Source name maps via the shorthand dictionary."""

    def test_smart_c1_methane(self):
        m = ComponentMatcher()
        r = m.match("C1")
        assert r == MatchResult(matched=True, name="METHANE", method="smart")

    def test_smart_n2_nitrogen(self):
        m = ComponentMatcher()
        r = m.match("N2")
        assert r.matched is True
        assert r.name == "NITROGEN (ASPHYXIATING)"
        assert r.method == "smart"

    def test_smart_h2o_water(self):
        m = ComponentMatcher()
        r = m.match("H2O")
        assert r.matched is True
        assert r.name == "WATER"
        assert r.method == "smart"

    def test_smart_co2(self):
        m = ComponentMatcher()
        r = m.match("CO2")
        assert r.matched is True
        assert r.name == "CARBON DIOXIDE (TOXIC)"

    def test_smart_h2s(self):
        m = ComponentMatcher()
        r = m.match("H2S")
        assert r.matched is True
        assert r.name == "HYDROGEN SULFIDE"

    def test_smart_ic4_isobutane(self):
        m = ComponentMatcher()
        r = m.match("IC4")
        assert r.matched is True
        assert r.name == "ISOBUTANE"

    def test_smart_nc4_nbutane(self):
        m = ComponentMatcher()
        r = m.match("NC4")
        assert r.matched is True
        assert r.name == "N-BUTANE"

    def test_smart_propylene_shorthand(self):
        m = ComponentMatcher()
        r = m.match("C3=")
        assert r.matched is True
        assert r.name == "PROPYLENE"

    def test_smart_meoh_methanol(self):
        m = ComponentMatcher()
        r = m.match("MeOH")
        assert r.matched is True
        assert r.name == "METHANOL"


class TestSmartMatchDisabled:
    """With smart_match=False, only exact and normalised strategies apply."""

    def test_shorthand_c1_no_match(self):
        m = ComponentMatcher(smart_match=False)
        r = m.match("C1")
        assert r.matched is False
        assert r.name == "C1"
        assert r.method == "none"

    def test_n2_no_match(self):
        m = ComponentMatcher(smart_match=False)
        r = m.match("N2")
        assert r.matched is False

    def test_canonical_still_matches_exact(self):
        m = ComponentMatcher(smart_match=False)
        r = m.match("METHANE")
        assert r.matched is True
        assert r.method == "exact"

    def test_normalised_still_works(self):
        m = ComponentMatcher(smart_match=False)
        r = m.match("NBUTANE")
        assert r.matched is True
        assert r.method == "normalised"


class TestNoMatch:
    def test_unknown_name(self):
        m = ComponentMatcher()
        r = m.match("UNKNOWNGAS")
        assert r == MatchResult(matched=False, name="UNKNOWNGAS", method="none")

    def test_none_input(self):
        m = ComponentMatcher()
        r = m.match(None)
        assert r == MatchResult(matched=False, name="", method="none")

    def test_empty_string(self):
        m = ComponentMatcher()
        r = m.match("")
        assert r == MatchResult(matched=False, name="", method="none")

    def test_whitespace_only(self):
        m = ComponentMatcher()
        r = m.match("   ")
        assert r == MatchResult(matched=False, name="", method="none")


class TestUserOverrides:
    def test_override_adds_new_mapping(self):
        m = ComponentMatcher(user_overrides={"MY_GAS": "PROPANE"})
        r = m.match("MY_GAS")
        assert r.matched is True
        assert r.name == "PROPANE"

    def test_override_replaces_default(self):
        # Redirect C1 to ETHANE instead of METHANE
        m = ComponentMatcher(user_overrides={"C1": "ETHANE"})
        r = m.match("C1")
        assert r.matched is True
        assert r.name == "ETHANE"

    def test_override_case_insensitive_key(self):
        m = ComponentMatcher(user_overrides={"my gas": "ETHANE"})
        r = m.match("MY GAS")
        assert r.matched is True
        assert r.name == "ETHANE"

    def test_no_overrides_default_unchanged(self):
        m = ComponentMatcher(user_overrides=None)
        r = m.match("C1")
        assert r.name == "METHANE"
