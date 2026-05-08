"""Tests for pyphast.core.columns."""

import pytest

from pyphast.core.columns import (
    col_index_to_letter,
    col_letter_to_index,
    is_valid_col_letter,
    normalise_col_letter,
)


class TestColLetterToIndex:
    def test_single_letter_a(self):
        assert col_letter_to_index("A") == 1

    def test_single_letter_z(self):
        assert col_letter_to_index("Z") == 26

    def test_two_letter_aa(self):
        assert col_letter_to_index("AA") == 27

    def test_two_letter_az(self):
        assert col_letter_to_index("AZ") == 52

    def test_two_letter_ba(self):
        assert col_letter_to_index("BA") == 53

    def test_app_column_ei(self):
        # EI is the last scan column used in PV_SCAN_LAST_COL
        assert col_letter_to_index("EI") == 139

    def test_max_column_xfd(self):
        assert col_letter_to_index("XFD") == 16384

    def test_lowercase_input(self):
        assert col_letter_to_index("a") == 1
        assert col_letter_to_index("aa") == 27

    def test_whitespace_stripped(self):
        assert col_letter_to_index("  A  ") == 1

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            col_letter_to_index("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            col_letter_to_index("   ")

    def test_digits_raises(self):
        with pytest.raises(ValueError):
            col_letter_to_index("A1")

    def test_digits_only_raises(self):
        with pytest.raises(ValueError):
            col_letter_to_index("123")

    def test_exceeds_max_raises(self):
        # XFE = 16385, one past the Excel maximum
        with pytest.raises(ValueError):
            col_letter_to_index("XFE")


class TestColIndexToLetter:
    def test_index_1(self):
        assert col_index_to_letter(1) == "A"

    def test_index_26(self):
        assert col_index_to_letter(26) == "Z"

    def test_index_27(self):
        assert col_index_to_letter(27) == "AA"

    def test_index_52(self):
        assert col_index_to_letter(52) == "AZ"

    def test_index_53(self):
        assert col_index_to_letter(53) == "BA"

    def test_index_max(self):
        assert col_index_to_letter(16384) == "XFD"

    def test_zero_raises(self):
        with pytest.raises(ValueError):
            col_index_to_letter(0)

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            col_index_to_letter(-1)

    def test_exceeds_max_raises(self):
        with pytest.raises(ValueError):
            col_index_to_letter(16385)


class TestRoundtrip:
    @pytest.mark.parametrize("letter", ["A", "Z", "AA", "AZ", "BA", "EI", "XFD"])
    def test_letter_roundtrip(self, letter):
        assert col_index_to_letter(col_letter_to_index(letter)) == letter

    @pytest.mark.parametrize("index", [1, 26, 27, 52, 53, 139, 16384])
    def test_index_roundtrip(self, index):
        assert col_letter_to_index(col_index_to_letter(index)) == index


class TestIsValidColLetter:
    def test_valid_single(self):
        assert is_valid_col_letter("A") is True

    def test_valid_multi(self):
        assert is_valid_col_letter("EI") is True

    def test_lowercase_valid(self):
        assert is_valid_col_letter("a") is True

    def test_empty_invalid(self):
        assert is_valid_col_letter("") is False

    def test_digits_invalid(self):
        assert is_valid_col_letter("A1") is False

    def test_exceeds_max_invalid(self):
        assert is_valid_col_letter("XFE") is False


class TestNormaliseColLetter:
    def test_uppercase_unchanged(self):
        assert normalise_col_letter("A") == "A"

    def test_lowercase_uppercased(self):
        assert normalise_col_letter("ab") == "AB"

    def test_whitespace_stripped(self):
        assert normalise_col_letter("  Z  ") == "Z"

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            normalise_col_letter("A1")
