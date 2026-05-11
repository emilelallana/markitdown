#!/usr/bin/env python3 -m pytest
"""Unit tests for the TextPostprocessor class."""

import pytest
from markitdown.converters._text_postprocessor import TextPostprocessor


@pytest.fixture
def pp():
    return TextPostprocessor()


# ---------------------------------------------------------------------------
# remove_page_headers_footers
# ---------------------------------------------------------------------------


class TestRemovePageHeadersFooters:
    def test_removes_page_numbers_when_isolated(self, pp):
        text = "Paragraph one.\n\n1\n\nParagraph two."
        result = pp.remove_page_headers_footers(text)
        assert "1" not in result.split("\n") or "Paragraph one." in result
        # The standalone "1" surrounded by blank lines should be removed
        lines = [ln.strip() for ln in result.split("\n") if ln.strip()]
        assert "1" not in lines

    def test_keeps_page_numbers_not_isolated(self, pp):
        text = "There are 3 items:\n1\n2\n3"
        result = pp.remove_page_headers_footers(text)
        # Numbers embedded in content should not be removed (not surrounded by blanks)
        assert "3" in result

    def test_removes_page_N_of_M_pattern(self, pp):
        text = "Body text.\n\nPage 2 of 10\n\nMore body."
        result = pp.remove_page_headers_footers(text)
        assert "Page 2 of 10" not in result
        assert "Body text." in result

    def test_removes_repeated_header_across_pages(self, pp):
        page_texts = [
            "Company Annual Report\nSome content on page one.\nFooter line",
            "Company Annual Report\nSome content on page two.\nFooter line",
            "Company Annual Report\nSome content on page three.\nFooter line",
        ]
        combined = "\n\n".join(page_texts)
        result = pp.remove_page_headers_footers(combined, page_texts=page_texts)
        assert "Some content on page one." in result
        # Repeated short header should be removed
        # (appears in top line of every page)
        header_count = result.count("Company Annual Report")
        # Should appear fewer times than in original (3 times)
        assert header_count < 3

    def test_does_not_remove_non_repeated_header(self, pp):
        page_texts = [
            "Section One\nLong content of page one that is important.",
            "Different Header\nLong content of page two.",
        ]
        combined = "\n\n".join(page_texts)
        result = pp.remove_page_headers_footers(combined, page_texts=page_texts)
        # Neither header repeats → both kept
        assert "Section One" in result
        assert "Different Header" in result

    def test_idempotent(self, pp):
        text = "Body.\n\n5\n\nMore body."
        first = pp.remove_page_headers_footers(text)
        second = pp.remove_page_headers_footers(first)
        assert first == second

    def test_empty_text(self, pp):
        assert pp.remove_page_headers_footers("") == ""

    def test_no_page_numbers(self, pp):
        text = "Just a regular paragraph with no page numbers."
        result = pp.remove_page_headers_footers(text)
        assert result == text

    def test_dash_page_number_pattern(self, pp):
        text = "Intro.\n\n- 3 -\n\nConclusion."
        result = pp.remove_page_headers_footers(text)
        assert "- 3 -" not in result

    def test_p_dot_page_number_pattern(self, pp):
        text = "Start.\n\np. 7\n\nEnd."
        result = pp.remove_page_headers_footers(text)
        assert "p. 7" not in result


# ---------------------------------------------------------------------------
# rejoin_hyphenated_words
# ---------------------------------------------------------------------------


class TestRejoinHyphenatedWords:
    def test_basic_hyphen_break(self, pp):
        text = "This is amaz-\ning text."
        result = pp.rejoin_hyphenated_words(text)
        assert "amazing" in result

    def test_hyphen_break_with_leading_whitespace(self, pp):
        text = "word hyphen-\n  continuation here."
        result = pp.rejoin_hyphenated_words(text)
        assert "hyphencontinuation" in result

    def test_no_change_same_line_hyphen(self, pp):
        text = "state-of-the-art solution"
        result = pp.rejoin_hyphenated_words(text)
        assert result == text

    def test_no_change_uppercase_before_hyphen(self, pp):
        # Uppercase letter before hyphen → do not rejoin
        text = "NASA-\nfunded project"
        result = pp.rejoin_hyphenated_words(text)
        # 'A' is uppercase, pattern requires lowercase before hyphen
        assert "NASA-\nfunded" in result

    def test_multiple_breaks_in_text(self, pp):
        text = "first hyphen-\nbreak and sec-\nond break."
        result = pp.rejoin_hyphenated_words(text)
        assert "hyphenbreak" in result
        assert "second" in result

    def test_idempotent(self, pp):
        text = "word-\ncontinuation."
        first = pp.rejoin_hyphenated_words(text)
        second = pp.rejoin_hyphenated_words(first)
        assert first == second

    def test_empty_text(self, pp):
        assert pp.rejoin_hyphenated_words("") == ""

    def test_no_hyphen_breaks(self, pp):
        text = "No hyphenation at all in this text.\nJust a normal new line."
        result = pp.rejoin_hyphenated_words(text)
        assert result == text


# ---------------------------------------------------------------------------
# normalize_whitespace
# ---------------------------------------------------------------------------


class TestNormalizeWhitespace:
    def test_collapses_multiple_blank_lines(self, pp):
        text = "Para one.\n\n\n\nPara two."
        result = pp.normalize_whitespace(text)
        assert "\n\n\n" not in result
        assert "Para one." in result
        assert "Para two." in result

    def test_collapses_internal_spaces(self, pp):
        text = "Word  with   multiple   spaces."
        result = pp.normalize_whitespace(text)
        assert "  " not in result
        assert "Word with multiple spaces." in result

    def test_preserves_leading_indentation(self, pp):
        text = "    indented line"
        result = pp.normalize_whitespace(text)
        assert result.startswith("    ")

    def test_normalises_crlf(self, pp):
        text = "Line one\r\nLine two\r\nLine three"
        result = pp.normalize_whitespace(text)
        assert "\r" not in result
        assert "Line one" in result

    def test_normalises_bare_cr(self, pp):
        text = "Line one\rLine two"
        result = pp.normalize_whitespace(text)
        assert "\r" not in result

    def test_preserves_code_block_content(self, pp):
        text = "Before\n```\n  code  with   spaces\n```\nAfter"
        result = pp.normalize_whitespace(text)
        assert "  code  with   spaces" in result

    def test_exactly_two_blank_lines_preserved(self, pp):
        text = "Para one.\n\nPara two."
        result = pp.normalize_whitespace(text)
        assert result == "Para one.\n\nPara two."

    def test_idempotent(self, pp):
        text = "Para one.\n\n\n\nPara   two.\n\nPara three."
        first = pp.normalize_whitespace(text)
        second = pp.normalize_whitespace(first)
        assert first == second

    def test_empty_text(self, pp):
        assert pp.normalize_whitespace("") == ""


# ---------------------------------------------------------------------------
# detect_and_mark_headings
# ---------------------------------------------------------------------------


class TestDetectAndMarkHeadings:
    def test_all_caps_heading_marked(self, pp):
        text = "\nINTRODUCTION AND BACKGROUND\n\nBody paragraph follows here."
        result = pp.detect_and_mark_headings(text)
        assert "## INTRODUCTION AND BACKGROUND" in result

    def test_long_all_caps_heading_is_h1(self, pp):
        text = "\nINTRODUCTION AND BACKGROUND METHODS\n\nBody."
        result = pp.detect_and_mark_headings(text)
        assert "# INTRODUCTION AND BACKGROUND METHODS" in result

    def test_chapter_heading_marked(self, pp):
        text = "Chapter 3\n\nContent here."
        result = pp.detect_and_mark_headings(text)
        assert "## Chapter 3" in result

    def test_section_heading_marked(self, pp):
        text = "Section 2\n\nContent here."
        result = pp.detect_and_mark_headings(text)
        assert "## Section 2" in result

    def test_dotted_section_heading(self, pp):
        text = "\n1.2 Background Information Here\n\nBody paragraph."
        result = pp.detect_and_mark_headings(text)
        assert "### 1.2 Background Information Here" in result

    def test_single_word_not_marked(self, pp):
        text = "\nIntroduction\n\nBody paragraph."
        result = pp.detect_and_mark_headings(text)
        assert "## Introduction" not in result
        assert "# Introduction" not in result

    def test_existing_heading_preserved(self, pp):
        text = "## Already a heading\n\nBody."
        result = pp.detect_and_mark_headings(text)
        assert "## Already a heading" in result
        assert "### Already a heading" not in result

    def test_table_row_not_marked(self, pp):
        text = "| Header | Data |\n|--------|------|\n| val | val |"
        result = pp.detect_and_mark_headings(text)
        assert "# |" not in result
        assert "## |" not in result

    def test_list_item_not_marked(self, pp):
        text = "- First list item here\n- Second list item"
        result = pp.detect_and_mark_headings(text)
        assert "#" not in result

    def test_all_caps_without_blank_lines_not_marked(self, pp):
        # ALL CAPS but NOT surrounded by blank lines → not a heading
        text = "Normal text.\nFOLLOWED BY ALL CAPS LINE\nMore normal text."
        result = pp.detect_and_mark_headings(text)
        assert "# FOLLOWED" not in result
        assert "## FOLLOWED" not in result

    def test_very_long_line_not_marked(self, pp):
        long_line = "A" * 121
        text = f"\n{long_line}\n\nBody."
        result = pp.detect_and_mark_headings(text)
        assert "#" not in result

    def test_idempotent(self, pp):
        text = "\nMETHODS AND RESULTS\n\nSome body text here and there."
        first = pp.detect_and_mark_headings(text)
        second = pp.detect_and_mark_headings(first)
        assert first == second

    def test_empty_text(self, pp):
        assert pp.detect_and_mark_headings("") == ""


# ---------------------------------------------------------------------------
# process (full pipeline)
# ---------------------------------------------------------------------------


class TestProcess:
    def test_full_pipeline_runs(self, pp):
        text = (
            "COMPANY ANNUAL REPORT\n\n"
            "This is the introduc-\n"
            "tion section.\n\n"
            "1\n\n"
            "METHODS AND MATERIALS\n\n"
            "Body   text  with   extra  spaces."
        )
        result = pp.process(text)
        assert "introduction" in result.lower()  # hyphen rejoined
        assert "  " not in result  # spaces normalised
        # Standalone "1" removed (page number)
        assert "\n1\n" not in result or "1" not in [
            ln.strip() for ln in result.split("\n") if ln.strip() == "1"
        ]

    def test_backward_compatible_with_no_changes_needed(self, pp):
        text = "A simple paragraph with no issues whatsoever."
        result = pp.process(text)
        # Should return equivalent content (may differ in trailing whitespace)
        assert "A simple paragraph with no issues whatsoever." in result

    def test_idempotent_full_pipeline(self, pp):
        text = "SOME HEADING\n\nBody text with hyphen-\nbreak and  extra  spaces.\n\n7\n\nMore text."
        first = pp.process(text)
        second = pp.process(first)
        assert first == second

    def test_page_texts_provided(self, pp):
        page_texts = [
            "My Document Title\nPage content one.\n1",
            "My Document Title\nPage content two.\n2",
            "My Document Title\nPage content three.\n3",
        ]
        combined = "\n\n".join(page_texts)
        result = pp.process(combined, page_texts=page_texts)
        assert "Page content one." in result
        assert "Page content two." in result
