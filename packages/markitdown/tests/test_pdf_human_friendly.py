#!/usr/bin/env python3 -m pytest
"""Integration tests for PDF human-friendly conversion mode."""

import os
import pytest

from markitdown import MarkItDown

TEST_FILES_DIR = os.path.join(os.path.dirname(__file__), "test_files")


def _pdf(name: str) -> str:
    return os.path.join(TEST_FILES_DIR, name)


def _skip_if_missing(path: str):
    if not os.path.exists(path):
        pytest.skip(f"Test file not found: {path}")


# ---------------------------------------------------------------------------
# Backward-compatibility: default mode must be identical to explicit False
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Verify that human_friendly=False (default) never changes existing output."""

    def test_default_equals_explicit_false_academic(self):
        pdf = _pdf("test.pdf")
        _skip_if_missing(pdf)

        md = MarkItDown()
        md_explicit = MarkItDown(human_friendly=False)

        default_out = md.convert(pdf).markdown
        explicit_out = md_explicit.convert(pdf).markdown

        assert default_out == explicit_out

    def test_default_equals_explicit_false_borderless_table(self):
        pdf = _pdf("SPARSE-2024-INV-1234_borderless_table.pdf")
        _skip_if_missing(pdf)

        md = MarkItDown()
        md_explicit = MarkItDown(human_friendly=False)

        assert md.convert(pdf).markdown == md_explicit.convert(pdf).markdown

    def test_convert_kwarg_false_equals_default(self):
        pdf = _pdf("test.pdf")
        _skip_if_missing(pdf)

        md = MarkItDown()
        default_out = md.convert(pdf).markdown
        kwarg_out = md.convert(pdf, human_friendly=False).markdown

        assert default_out == kwarg_out


# ---------------------------------------------------------------------------
# human_friendly=True – smoke tests (content preserved, runs without error)
# ---------------------------------------------------------------------------


class TestHumanFriendlySmoke:
    """human_friendly=True must not crash and must preserve meaningful content."""

    @pytest.fixture
    def md_hf(self):
        return MarkItDown(human_friendly=True)

    def test_academic_pdf_produces_output(self, md_hf):
        pdf = _pdf("test.pdf")
        _skip_if_missing(pdf)

        result = md_hf.convert(pdf)
        assert result is not None
        assert result.markdown.strip() != ""

    def test_academic_pdf_retains_key_content(self, md_hf):
        pdf = _pdf("test.pdf")
        _skip_if_missing(pdf)

        text = md_hf.convert(pdf).markdown
        for phrase in ("Introduction", "agents", "reasoning"):
            assert phrase.lower() in text.lower(), f"Expected '{phrase}' in output"

    def test_borderless_table_retains_key_content(self, md_hf):
        pdf = _pdf("SPARSE-2024-INV-1234_borderless_table.pdf")
        _skip_if_missing(pdf)

        text = md_hf.convert(pdf).markdown
        assert "SKU-8847" in text
        assert "Variance Analysis" in text

    def test_receipt_retains_key_content(self, md_hf):
        pdf = _pdf("RECEIPT-2024-TXN-98765_retail_purchase.pdf")
        _skip_if_missing(pdf)

        text = md_hf.convert(pdf).markdown
        assert "TECHMART ELECTRONICS" in text
        assert "$821.14" in text

    def test_multipage_invoice_retains_key_content(self, md_hf):
        pdf = _pdf("REPAIR-2022-INV-001_multipage.pdf")
        _skip_if_missing(pdf)

        text = md_hf.convert(pdf).markdown
        assert "ZAVA AUTO REPAIR" in text
        assert "Gabriel Diaz" in text
        assert "GRAND TOTAL" in text

    def test_scanned_pdf_returns_empty(self, md_hf):
        pdf = _pdf("MEDRPT-2024-PAT-3847_medical_report_scan.pdf")
        _skip_if_missing(pdf)

        result = md_hf.convert(pdf)
        assert result is not None
        assert result.markdown.strip() == ""

    def test_no_excessive_extra_blank_lines(self, md_hf):
        pdf = _pdf("test.pdf")
        _skip_if_missing(pdf)

        text = md_hf.convert(pdf).markdown
        # normalize_whitespace should prevent runs of 3+ blank lines
        assert "\n\n\n" not in text

    def test_no_extra_spaces_within_lines(self, md_hf):
        pdf = _pdf("test.pdf")
        _skip_if_missing(pdf)

        text = md_hf.convert(pdf).markdown
        lines = text.split("\n")
        for line in lines:
            stripped = line.lstrip()
            if stripped:
                assert "  " not in stripped, (
                    f"Double space found in line: {repr(line)}"
                )


# ---------------------------------------------------------------------------
# human_friendly=True via per-call kwarg (instance has human_friendly=False)
# ---------------------------------------------------------------------------


class TestHumanFriendlyPerCallKwarg:
    def test_per_call_kwarg_enables_human_friendly(self):
        pdf = _pdf("test.pdf")
        _skip_if_missing(pdf)

        md = MarkItDown()  # default human_friendly=False
        result = md.convert(pdf, human_friendly=True)
        assert result.markdown.strip() != ""

    def test_per_call_kwarg_overrides_instance_setting(self):
        pdf = _pdf("test.pdf")
        _skip_if_missing(pdf)

        md_hf = MarkItDown(human_friendly=True)
        # Override at call site to disable
        result = md_hf.convert(pdf, human_friendly=False)
        default_result = MarkItDown().convert(pdf)

        assert result.markdown == default_result.markdown


# ---------------------------------------------------------------------------
# Heading detection in human_friendly mode
# ---------------------------------------------------------------------------


class TestHeadingDetection:
    """When human_friendly=True, ALL-CAPS section titles should get # prefixes."""

    @pytest.fixture
    def md_hf(self):
        return MarkItDown(human_friendly=True)

    def test_academic_pdf_may_have_headings(self, md_hf):
        pdf = _pdf("test.pdf")
        _skip_if_missing(pdf)

        text = md_hf.convert(pdf).markdown
        # The academic PDF has an "Introduction" section; if it's all-caps in
        # the PDF it should be promoted.  We just verify the output is valid
        # markdown (heading markers use # followed by a space).
        for line in text.split("\n"):
            if line.startswith("#"):
                # Every heading must have a space after the #s
                assert re.match(
                    r"^#{1,6} \S", line
                ), f"Malformed heading line: {repr(line)}"

    def test_no_pipe_rows_turned_into_headings(self, md_hf):
        pdf = _pdf("SPARSE-2024-INV-1234_borderless_table.pdf")
        _skip_if_missing(pdf)

        text = md_hf.convert(pdf).markdown
        for line in text.split("\n"):
            # No line that starts with | should also start with #
            if line.strip().startswith("|"):
                assert not line.startswith("#"), (
                    f"Table row was incorrectly marked as heading: {repr(line)}"
                )


import re  # noqa: E402 – used by TestHeadingDetection above
