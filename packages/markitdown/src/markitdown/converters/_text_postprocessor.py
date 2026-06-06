import re
from typing import Optional


class TextPostprocessor:
    """Post-processes extracted PDF text to improve human readability."""

    # Common page number patterns (standalone lines)
    _PAGE_NUMBER_PATTERNS = [
        re.compile(r"^\d+$"),  # Just a number: "1"
        re.compile(r"^[Pp]age\s+\d+(?:\s+of\s+\d+)?$"),  # "Page 1" or "Page 1 of 5"
        re.compile(r"^-\s*\d+\s*-$"),  # "- 1 -"
        re.compile(r"^p\.\s*\d+$"),  # "p. 1"
        re.compile(r"^\d+\s*/\s*\d+$"),  # "1/5"
    ]

    # Hyphen at line-end followed by lowercase continuation (word-break hyphenation)
    _HYPHEN_BREAK = re.compile(r"(?<=[a-z])-\n\s*(?=[a-z])")

    def remove_page_headers_footers(
        self, text: str, page_texts: Optional[list] = None
    ) -> str:
        """Remove common PDF headers/footers from extracted text.

        When page_texts is provided (list of per-page strings), uses cross-page
        frequency analysis to identify repeated headers/footers and removes them
        from text.  Falls back to page-number-only removal when page context is
        not available.
        """
        if page_texts and len(page_texts) >= 2:
            patterns = self._find_header_footer_patterns(page_texts)
            text = self._remove_line_patterns(text, patterns)
        # Always strip standalone page numbers regardless of page context
        text = self._remove_isolated_page_numbers(text)
        return text

    def _find_header_footer_patterns(self, page_texts: list) -> set:
        """Identify lines that appear repeatedly at the top/bottom of pages."""
        top_counts: dict = {}
        bottom_counts: dict = {}

        for page_text in page_texts:
            lines = [ln.strip() for ln in page_text.split("\n") if ln.strip()]
            if not lines:
                continue
            for line in lines[:3]:
                if 0 < len(line) < 120:
                    top_counts[line] = top_counts.get(line, 0) + 1
            for line in lines[-3:]:
                if 0 < len(line) < 120:
                    bottom_counts[line] = bottom_counts.get(line, 0) + 1

        n = len(page_texts)
        threshold = max(2, n * 0.5)

        candidates: set = set()
        for counts in (top_counts, bottom_counts):
            for line, count in counts.items():
                if count >= threshold and self._is_header_footer_candidate(line):
                    candidates.add(line)

        return candidates

    def _is_header_footer_candidate(self, line: str) -> bool:
        """Return True if the line looks like a header or footer."""
        if len(line) > 80:
            return False
        # Explicit page-number pattern
        for pat in self._PAGE_NUMBER_PATTERNS:
            if pat.match(line):
                return True
        # Mostly non-alphabetic content (e.g., "| Page 1 |", "--- 2 ---")
        non_alpha = sum(1 for c in line if not c.isalpha())
        if len(line) > 0 and non_alpha / len(line) > 0.6:
            return True
        # Short lines (< 50 chars) are plausible headers/footers
        return len(line) < 50

    def _remove_line_patterns(self, text: str, patterns: set) -> str:
        """Remove lines whose stripped content is in *patterns*."""
        if not patterns:
            return text
        lines = text.split("\n")
        return "\n".join(ln for ln in lines if ln.strip() not in patterns)

    def _remove_isolated_page_numbers(self, text: str) -> str:
        """Remove standalone page-number lines that are surrounded by blank lines."""
        lines = text.split("\n")
        result = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if any(p.match(stripped) for p in self._PAGE_NUMBER_PATTERNS):
                prev_blank = i == 0 or not lines[i - 1].strip()
                next_blank = i >= len(lines) - 1 or not lines[i + 1].strip()
                if prev_blank and next_blank:
                    continue  # drop the page number
            result.append(line)
        return "\n".join(result)

    def rejoin_hyphenated_words(self, text: str) -> str:
        """Rejoin words that were hyphenated at line boundaries.

        Detects the pattern  <lowercase>-\\n<whitespace><lowercase>  which
        indicates PDF line-break hyphenation (not an intentional compound
        hyphen), and removes the break so the word reads as one token.
        """
        return self._HYPHEN_BREAK.sub("", text)

    def normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace while preserving meaningful structure.

        - Normalise mixed line endings to \\n
        - Collapse 3+ consecutive blank lines to 2
        - Collapse multiple internal spaces to one (preserves leading indent)
        - Skips normalisation inside fenced code blocks
        """
        # Normalise line endings first
        text = re.sub(r"\r\n", "\n", text)
        text = re.sub(r"\r", "\n", text)
        # pdfminer uses \x0c (form feed) as a page separator; treat as paragraph break
        text = re.sub(r"\x0c", "\n\n", text)

        lines = text.split("\n")
        result = []
        in_code_block = False

        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block

            if in_code_block or line.strip().startswith("```"):
                result.append(line)
                continue

            if not line.strip():
                result.append("")
                continue

            # Preserve leading indentation; collapse internal runs of spaces
            stripped = line.lstrip()
            indent = line[: len(line) - len(stripped)]
            stripped = re.sub(r" {2,}", " ", stripped)
            result.append(indent + stripped)

        # Re-join and collapse excessive blank lines
        text = "\n".join(result)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text

    def detect_and_mark_headings(self, text: str) -> str:
        """Auto-detect probable headings and promote them to Markdown syntax.

        Uses conservative heuristics to minimise false positives:
        - ALL-CAPS lines (2+ words, ≤ 80 chars) surrounded by blank lines
        - Explicit "Chapter N" / "Section N" patterns
        - Dotted-number sections like "1.2 Title" (≥ 2 content words, ≤ 80 chars)

        Leaves existing Markdown headings and table rows untouched.
        """
        lines = text.split("\n")
        result = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Preserve already-formatted headings and table rows
            if stripped.startswith("#") or stripped.startswith("|"):
                result.append(line)
                continue

            if not stripped:
                result.append(line)
                continue

            prev_blank = i == 0 or not lines[i - 1].strip()
            next_blank = i >= len(lines) - 1 or not lines[i + 1].strip()

            level = self._heading_level(stripped, prev_blank, next_blank)
            if level is not None:
                result.append("#" * level + " " + stripped)
            else:
                result.append(line)

        return "\n".join(result)

    def _heading_level(
        self, stripped: str, prev_blank: bool, next_blank: bool
    ) -> Optional[int]:
        """Return a Markdown heading level (1-4) or None."""
        words = stripped.split()

        # Minimum word count and maximum length guards
        if len(words) < 2 or len(stripped) > 120:
            return None

        # Skip Markdown list items
        if re.match(r"^[-*+]\s", stripped):
            return None

        # Explicit chapter / section label
        if re.match(r"^(?:CHAPTER|Chapter|SECTION|Section)\s+\d+", stripped):
            return 2

        # Dotted-number section (e.g. "1.2 Title Words") – only surrounded by blanks
        if prev_blank and next_blank:
            num_match = re.match(r"^(\d+(?:\.\d+)+)\s+[A-Z]", stripped)
            if num_match and len(words) >= 3 and len(stripped) < 80:
                depth = len(num_match.group(1).split("."))
                return min(depth + 1, 4)

        # ALL-CAPS line surrounded by blank lines
        if (
            stripped.isupper()
            and prev_blank
            and next_blank
            and 5 <= len(stripped) <= 80
            and len(words) >= 2
        ):
            return 1 if len(stripped) > 40 else 2

        return None

    def fix_text_alignment_issues(self, text: str) -> str:
        """Placeholder for multi-column reflow (requires coordinate data).

        Without bounding-box information this cannot reliably reorder text;
        the method is provided as an extension point.
        """
        return text

    def process(self, text: str, page_texts: Optional[list] = None) -> str:
        """Apply the full human-friendly post-processing pipeline.

        Pipeline order:
          remove_page_headers_footers → rejoin_hyphenated_words
          → normalize_whitespace → detect_and_mark_headings
        """
        text = self.remove_page_headers_footers(text, page_texts=page_texts)
        text = self.rejoin_hyphenated_words(text)
        text = self.normalize_whitespace(text)
        text = self.detect_and_mark_headings(text)
        return text
