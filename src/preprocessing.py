"""
preprocessing.py -- HTML cleaning and text extraction for LLM consumption.

Converts rendered HTML into clean, compact, LLM-friendly text.
Deterministic -- no LLM calls happen here.

Pipeline:
    raw HTML
    -> remove non-content tags (script, style, svg, ...)
    -> reduce nav/footer boilerplate
    -> extract visible text preserving heading structure
    -> normalise whitespace
    -> extract emails & LinkedIn URLs from both HTML and text
    -> truncate to configurable max length
    -> wrap in PreprocessedPage with metadata
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from src.config import settings
from src.utils import get_logger

logger = get_logger(__name__)

# ------------------------------------------------------------------ #
#  Constants                                                          #
# ------------------------------------------------------------------ #

# Tags whose entire subtree is removed (never contain useful body text).
TAGS_TO_DECOMPOSE: list[str] = [
    "script",
    "style",
    "noscript",
    "iframe",
    "svg",
    "canvas",
    "template",
    "object",
    "embed",
    "applet",
    "video",
    "audio",
    "source",
    "picture",
    "map",
    "form",        # forms are rarely useful text
]

# Tags that are likely boilerplate navigation / chrome.
# We keep them but strip their text if they dominate the page.
BOILERPLATE_TAGS: list[str] = [
    "nav",
    "footer",
    "header",
]

# Heading tags that we want to preserve as structural markers.
HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})

# ------------------------------------------------------------------ #
#  Regex patterns                                                     #
# ------------------------------------------------------------------ #

# Robust email regex: standard addr-spec per RFC 5321 (simplified).
_EMAIL_RE = re.compile(
    r"""
    \b
    [A-Za-z0-9._%+\-]+        # local part
    @
    [A-Za-z0-9.\-]+           # domain
    \.
    [A-Za-z]{2,}              # TLD
    \b
    """,
    re.VERBOSE,
)

# LinkedIn profile URLs.
_LINKEDIN_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/(?:in|company)/[A-Za-z0-9_\-]+/?",
    re.IGNORECASE,
)

# Whitespace normalization helpers.
_MULTI_SPACE = re.compile(r"[ \t]+")            # multiple horiz. spaces
_MULTI_NEWLINE = re.compile(r"\n{3,}")           # 3+ blank lines -> 2
_TRAILING_WS = re.compile(r"[ \t]+$", re.M)     # trailing whitespace per line

# Emails to exclude (images, assets, false positives).
_EMAIL_EXCLUDE = re.compile(
    r"""
    \.(?:png|jpg|jpeg|gif|svg|webp|ico|css|js|woff|woff2|ttf|eot)$  |
    ^(?:noreply|no-reply|mailer-daemon|postmaster)@                  |
    @(?:example\.com|test\.com|localhost)$                            |
    @.*\.(?:png|jpg|svg)$
    """,
    re.VERBOSE | re.IGNORECASE,
)


# ------------------------------------------------------------------ #
#  Data model                                                         #
# ------------------------------------------------------------------ #

@dataclass(frozen=True)
class PreprocessedPage:
    """Clean text extracted from a single page, ready for LLM consumption."""

    url: str
    category: str
    text: str
    emails: list[str] = field(default_factory=list)
    linkedin_urls: list[str] = field(default_factory=list)
    original_html_chars: int = 0
    cleaned_text_chars: int = 0
    reduction_percentage: float = 0.0


# ------------------------------------------------------------------ #
#  Internal helpers                                                   #
# ------------------------------------------------------------------ #

def _remove_comments(soup: BeautifulSoup) -> None:
    """Remove all HTML comments in-place."""
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()


def _decompose_tags(soup: BeautifulSoup, tags: list[str]) -> None:
    """Remove entire subtrees for the given tag names."""
    for tag_name in tags:
        for el in soup.find_all(tag_name):
            el.decompose()


def _reduce_boilerplate(soup: BeautifulSoup) -> None:
    """Reduce nav/footer/header boilerplate.

    Strategy: for each boilerplate container, keep it only if it contains
    substantial text (>150 chars after stripping).  Tiny nav bars and
    cookie banners get removed; a footer with company info stays.
    """
    for tag_name in BOILERPLATE_TAGS:
        for el in soup.find_all(tag_name):
            text = el.get_text(separator=" ", strip=True)
            if len(text) < 150:
                el.decompose()


def _remove_hidden_elements(soup: BeautifulSoup) -> None:
    """Remove elements with display:none or visibility:hidden inline styles."""
    for el in soup.find_all(style=True):
        style: str = el.get("style", "")
        if "display:none" in style.replace(" ", "") or \
           "visibility:hidden" in style.replace(" ", ""):
            el.decompose()


def _extract_text_with_structure(soup: BeautifulSoup) -> str:
    """Walk the DOM and extract text preserving heading structure.

    Headings get a Markdown-style prefix (## Heading) so the LLM
    can understand document structure.
    """
    lines: list[str] = []

    for el in soup.descendants:
        if isinstance(el, NavigableString):
            parent = el.parent
            if parent is None or parent.name in TAGS_TO_DECOMPOSE:
                continue
            text = str(el).strip()
            if text:
                lines.append(text)

        elif isinstance(el, Tag):
            if el.name in HEADING_TAGS:
                level = int(el.name[1])
                heading_text = el.get_text(separator=" ", strip=True)
                if heading_text:
                    prefix = "#" * min(level, 4)
                    lines.append(f"\n{prefix} {heading_text}\n")
                    # Prevent descendants from double-emitting.
                    el.clear()

            elif el.name in ("p", "div", "section", "article", "li", "td", "blockquote"):
                # Insert a newline before block elements for readability.
                if lines and not lines[-1].endswith("\n"):
                    lines.append("\n")

            elif el.name == "br":
                lines.append("\n")

    return "\n".join(lines)


def _normalise_whitespace(text: str) -> str:
    """Collapse excessive whitespace while keeping intentional line breaks."""
    text = _MULTI_SPACE.sub(" ", text)
    text = _TRAILING_WS.sub("", text)
    text = _MULTI_NEWLINE.sub("\n\n", text)
    return text.strip()


def _dedup_lines(text: str, min_occurrences: int = 3) -> str:
    """Remove lines that appear too many times (repeated boilerplate).

    A line must appear >= min_occurrences and be longer than 10 chars
    to be considered boilerplate and removed.
    """
    lines = text.split("\n")
    counts: dict[str, int] = {}
    for line in lines:
        stripped = line.strip()
        if len(stripped) > 10:
            counts[stripped] = counts.get(stripped, 0) + 1

    boilerplate = {line for line, cnt in counts.items() if cnt >= min_occurrences}
    if boilerplate:
        logger.debug("Removing %d repeated boilerplate lines", len(boilerplate))

    cleaned = [
        line for line in lines
        if line.strip() not in boilerplate
    ]
    return "\n".join(cleaned)


def _truncate_text(text: str, max_chars: int) -> str:
    """Truncate to *max_chars* preferring to keep the beginning.

    If truncation is needed, keep ~80% from the start and ~20% from the
    end, separated by a marker.
    """
    if len(text) <= max_chars:
        return text

    head_budget = int(max_chars * 0.80)
    tail_budget = max_chars - head_budget - 50  # 50 for the separator

    head = text[:head_budget]
    tail = text[-tail_budget:] if tail_budget > 0 else ""

    marker = "\n\n[... content truncated for length ...]\n\n"
    return head + marker + tail


# ------------------------------------------------------------------ #
#  Extraction helpers                                                 #
# ------------------------------------------------------------------ #

def extract_emails(text: str) -> list[str]:
    """Find all email addresses in *text*, deduplicated.

    Filters out image-like false positives and common noreply addresses.
    """
    raw = _EMAIL_RE.findall(text)
    seen: set[str] = set()
    result: list[str] = []
    for email in raw:
        lower = email.lower()
        if lower in seen:
            continue
        if _EMAIL_EXCLUDE.search(lower):
            continue
        # Skip unicode/HTML-escaping artifacts (e.g. u003einfo@postman.com)
        if "u00" in lower or "x22" in lower or "\\u" in lower:
            continue
        seen.add(lower)
        result.append(email)
    return result


def extract_linkedin_urls(html: str) -> list[str]:
    """Find all LinkedIn profile/company URLs in *html*, deduplicated."""
    raw = _LINKEDIN_RE.findall(html)
    seen: set[str] = set()
    result: list[str] = []
    for url in raw:
        # Normalise trailing slash.
        normalised = url.rstrip("/")
        if normalised in seen:
            continue
        seen.add(normalised)
        result.append(normalised)
    return result


# ------------------------------------------------------------------ #
#  Public API                                                         #
# ------------------------------------------------------------------ #

def clean_html(raw_html: str, max_text_chars: int | None = None) -> str:
    """Convert raw HTML into clean, LLM-friendly text.

    Args:
        raw_html:       The rendered HTML from a page.
        max_text_chars:  Maximum output text length.  Defaults to
                        ``settings.max_text_chars``.

    Returns:
        Cleaned plain text with Markdown-style headings.
    """
    if max_text_chars is None:
        max_text_chars = settings.max_text_chars

    if not raw_html or not raw_html.strip():
        return ""

    soup = BeautifulSoup(raw_html, "lxml")

    # Step 1: Remove comments.
    _remove_comments(soup)

    # Step 2: Decompose non-content tags.
    _decompose_tags(soup, TAGS_TO_DECOMPOSE)

    # Step 3: Remove hidden elements.
    _remove_hidden_elements(soup)

    # Step 4: Reduce nav/footer boilerplate.
    _reduce_boilerplate(soup)

    # Step 5: Remove common UI detritus (buttons, icons, etc.).
    for el in soup.find_all(attrs={"aria-hidden": "true"}):
        el.decompose()

    # Step 6: Extract text with structure.
    text = _extract_text_with_structure(soup)

    # Step 7: Normalise whitespace.
    text = _normalise_whitespace(text)

    # Step 8: Deduplicate repeated lines.
    text = _dedup_lines(text)

    # Step 9: Re-normalise after dedup.
    text = _normalise_whitespace(text)

    # Step 10: Truncate if needed.
    text = _truncate_text(text, max_text_chars)

    return text


def preprocess_page(
    url: str,
    category: str,
    raw_html: str,
    max_text_chars: int | None = None,
) -> PreprocessedPage:
    """Full preprocessing pipeline for a single page.

    Extracts clean text, emails, and LinkedIn URLs, and computes
    reduction metadata.

    Args:
        url:           The page URL.
        category:      The category assigned by the crawler.
        raw_html:      Rendered HTML content.
        max_text_chars: Max output text length.

    Returns:
        A :class:`PreprocessedPage` with all fields populated.
    """
    original_chars = len(raw_html)

    # Clean text.
    text = clean_html(raw_html, max_text_chars=max_text_chars)
    cleaned_chars = len(text)

    # Extract emails from both the raw HTML (catches mailto: hrefs) and
    # the cleaned text.
    emails = extract_emails(raw_html + "\n" + text)

    # Extract LinkedIn URLs from raw HTML (they're in href attributes).
    linkedin_urls = extract_linkedin_urls(raw_html)

    # Reduction percentage.
    reduction = (
        ((original_chars - cleaned_chars) / original_chars * 100)
        if original_chars > 0
        else 0.0
    )

    logger.info(
        "Preprocessed %s: %d -> %d chars (%.1f%% reduction), "
        "%d emails, %d LinkedIn URLs",
        url, original_chars, cleaned_chars, reduction,
        len(emails), len(linkedin_urls),
    )

    return PreprocessedPage(
        url=url,
        category=category,
        text=text,
        emails=emails,
        linkedin_urls=linkedin_urls,
        original_html_chars=original_chars,
        cleaned_text_chars=cleaned_chars,
        reduction_percentage=round(reduction, 1),
    )
