"""
preprocessing.py — HTML cleaning and text extraction.

Uses BeautifulSoup to strip boilerplate (nav, footer, scripts, styles),
extract meaningful text, and prepare clean content for the LLM.
"""

from src.utils import get_logger

logger = get_logger(__name__)

# HTML tags that typically contain boilerplate, not useful content.
TAGS_TO_REMOVE = [
    "script",
    "style",
    "nav",
    "footer",
    "header",
    "noscript",
    "iframe",
    "svg",
    "img",
]


def clean_html(raw_html: str) -> str:
    """Strip boilerplate HTML and extract readable text.

    Args:
        raw_html: The raw HTML string from a rendered page.

    Returns:
        Cleaned, readable text suitable for LLM consumption.

    TODO: Implement in Phase 2.
    """
    raise NotImplementedError("HTML cleaning will be implemented in Phase 2")


def extract_emails(text: str) -> list[str]:
    """Extract email addresses from text content.

    Args:
        text: Plain text to search for email patterns.

    Returns:
        A deduplicated list of email addresses found.

    TODO: Implement in Phase 2.
    """
    raise NotImplementedError("Email extraction will be implemented in Phase 2")
