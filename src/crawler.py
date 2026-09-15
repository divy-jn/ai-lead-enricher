"""
crawler.py -- Relevant-page discovery from a company homepage.

Given a domain, fetches the homepage with the existing BrowserManager,
parses rendered HTML with BeautifulSoup, scores every <a> link for
relevance to lead-enrichment categories (about, team, contact, pricing,
etc.), and returns the top-N links together with the fetched PageResult
for each.

This module does NOT invent URLs.  Every URL it returns was actually
found in the homepage HTML.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from src.browser import BrowserManager, PageResult
from src.config import settings
from src.utils import get_logger

logger = get_logger(__name__)


# ------------------------------------------------------------------ #
#  Category keywords and scoring                                      #
# ------------------------------------------------------------------ #

# Maps a category name to sets of keywords that appear in URL paths
# or anchor text.  Order does not matter -- we keep one URL per
# category in the final selection.
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "about":      ["about", "about-us", "who-we-are", "our-story", "company"],
    "team":       ["team", "our-team", "leadership", "people", "founders", "executives"],
    "contact":    ["contact", "contact-us", "get-in-touch", "reach-us", "support"],
    "pricing":    ["pricing", "plans", "price"],
    "careers":    ["careers", "jobs", "work-with-us", "join-us", "hiring"],
    "customers":  ["customers", "case-studies", "testimonials", "success-stories"],
    "product":    ["product", "features", "solutions", "platform", "how-it-works"],
    "partners":   ["partners", "integrations", "marketplace"],
}

# URL-path or anchor-text patterns that should be excluded regardless
# of any keyword match.
_SKIP_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r, re.IGNORECASE)
    for r in [
        r"login",
        r"log-in",
        r"signin",
        r"sign-in",
        r"signup",
        r"sign-up",
        r"register",
        r"auth",
        r"oauth",
        r"sso",
        r"account",
        r"dashboard",
        r"app\.",
        r"docs\.",
        r"blog\.",
        r"help\.",
        r"status\.",
        r"cdn\.",
        r"api\.",
    ]
]

# Domains that are clearly external social-media or CDN links.
_SOCIAL_DOMAINS = frozenset({
    "twitter.com", "x.com", "facebook.com", "linkedin.com",
    "instagram.com", "youtube.com", "github.com", "tiktok.com",
    "reddit.com", "discord.com", "discord.gg", "medium.com",
    "t.co",
})

# File-extension suffixes to ignore.
_FILE_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
    ".pdf", ".zip", ".tar", ".gz", ".mp4", ".mp3", ".woff",
    ".woff2", ".ttf", ".eot", ".css", ".js", ".xml", ".json",
})


# ------------------------------------------------------------------ #
#  Data models                                                        #
# ------------------------------------------------------------------ #

@dataclass(frozen=True)
class DiscoveredLink:
    """A single link found on the homepage, scored and categorised."""

    url: str
    category: str              # e.g. "about", "team", or "uncategorised"
    score: float               # higher = more relevant
    anchor_text: str = ""      # cleaned text from the <a> element


@dataclass(frozen=True)
class CrawlResult:
    """One page that was discovered *and* fetched."""

    url: str
    category: str
    page_result: PageResult


# ------------------------------------------------------------------ #
#  Internal helpers                                                   #
# ------------------------------------------------------------------ #

def _base_domain(url: str) -> str:
    """Return the registrable domain, e.g. 'www.postman.com' -> 'postman.com'.

    Simple heuristic: keep last two labels (or three for co.uk-style).
    Good enough for same-site filtering without pulling in tldextract.
    """
    host = urlparse(url).hostname or ""
    parts = host.split(".")
    # Handle things like co.uk, com.au, etc.
    if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "net", "edu", "gov"):
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _is_same_site(candidate_url: str, homepage_url: str) -> bool:
    """True if *candidate_url* belongs to the same registrable domain."""
    return _base_domain(candidate_url) == _base_domain(homepage_url)


def _should_skip(url: str, anchor_text: str) -> bool:
    """Return True if the URL/text matches a skip pattern."""
    combined = f"{url} {anchor_text}"
    return any(p.search(combined) for p in _SKIP_PATTERNS)


def _has_file_extension(path: str) -> bool:
    """True if the URL path ends with a known binary/file extension."""
    lower = path.lower()
    return any(lower.endswith(ext) for ext in _FILE_EXTENSIONS)


def _score_link(url: str, anchor_text: str) -> tuple[str, float]:
    """Score a link against category keywords.

    Returns (category, score).  Higher score = better match.
    Scores:
      - 3.0  keyword in URL path (strong signal)
      - 2.0  keyword in anchor text
      - 0.5  bonus for a short, focused path (e.g. /about vs /about/sub/page)
    """
    parsed = urlparse(url)
    path = parsed.path.lower().strip("/")
    text_lower = anchor_text.lower()

    best_category = "uncategorised"
    best_score = 0.0

    for category, keywords in CATEGORY_KEYWORDS.items():
        cat_score = 0.0
        for kw in keywords:
            if kw in path.split("/"):
                cat_score += 3.0
            elif kw in path:
                cat_score += 2.0
            if kw in text_lower:
                cat_score += 2.0

        # Prefer shorter, more focused paths.
        if cat_score > 0 and path.count("/") <= 1:
            cat_score += 0.5

        if cat_score > best_score:
            best_score = cat_score
            best_category = category

    return best_category, best_score


# ------------------------------------------------------------------ #
#  Public API                                                         #
# ------------------------------------------------------------------ #

def discover_links(
    homepage_html: str,
    homepage_url: str,
    max_pages: int | None = None,
) -> list[DiscoveredLink]:
    """Parse *homepage_html* and return scored, deduplicated relevant links.

    Args:
        homepage_html: Rendered HTML of the homepage.
        homepage_url:  The URL the homepage was fetched from (used to
                       resolve relative links and enforce same-site).
        max_pages:     Maximum number of links to return.  Defaults to
                       ``settings.max_crawl_pages``.

    Returns:
        A list of :class:`DiscoveredLink` sorted by score descending,
        limited to one URL per category.
    """
    if max_pages is None:
        max_pages = settings.max_crawl_pages

    soup = BeautifulSoup(homepage_html, "lxml")
    seen_urls: set[str] = set()
    scored: list[DiscoveredLink] = []

    for a_tag in soup.find_all("a", href=True):
        raw_href: str = a_tag["href"].strip()

        # Skip non-HTTP schemes.
        if raw_href.startswith(("mailto:", "javascript:", "tel:", "#", "data:")):
            continue

        # Resolve relative URLs.
        try:
            full_url = urljoin(homepage_url, raw_href)
        except Exception:
            continue

        parsed = urlparse(full_url)

        # Only http/https.
        if parsed.scheme not in ("http", "https"):
            continue

        # Strip fragments and query strings for dedup.
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        # Normalise trailing slash.
        if clean_url.endswith("/") and clean_url != f"{parsed.scheme}://{parsed.netloc}/":
            clean_url = clean_url.rstrip("/")

        # Already seen?
        if clean_url in seen_urls:
            continue

        # Skip file downloads.
        if _has_file_extension(parsed.path):
            continue

        # Same site?
        if not _is_same_site(full_url, homepage_url):
            continue

        # Skip the homepage itself.
        homepage_parsed = urlparse(homepage_url)
        homepage_clean = f"{homepage_parsed.scheme}://{homepage_parsed.netloc}{homepage_parsed.path}".rstrip("/")
        if clean_url.rstrip("/") == homepage_clean.rstrip("/"):
            continue

        anchor_text = a_tag.get_text(separator=" ", strip=True)

        # Skip login/auth/social etc.
        if _should_skip(clean_url, anchor_text):
            continue

        # Score it.
        category, score = _score_link(clean_url, anchor_text)
        if score <= 0:
            continue

        seen_urls.add(clean_url)
        scored.append(
            DiscoveredLink(
                url=clean_url,
                category=category,
                score=score,
                anchor_text=anchor_text[:120],  # truncate long text
            )
        )

    # Sort by score descending.
    scored.sort(key=lambda d: d.score, reverse=True)

    # Keep at most one URL per category (the highest-scored one).
    selected: list[DiscoveredLink] = []
    used_categories: set[str] = set()

    for link in scored:
        if link.category in used_categories:
            continue
        used_categories.add(link.category)
        selected.append(link)
        if len(selected) >= max_pages:
            break

    logger.info(
        "Discovered %d candidate links, selected %d (max %d)",
        len(scored),
        len(selected),
        max_pages,
    )
    for lnk in selected:
        logger.debug(
            "  [%s] score=%.1f  %s  (%s)",
            lnk.category,
            lnk.score,
            lnk.url,
            lnk.anchor_text[:60],
        )

    return selected


async def crawl_domain(
    domain: str,
    browser: BrowserManager,
    max_pages: int | None = None,
) -> list[CrawlResult]:
    """Discover and fetch relevant pages for *domain*.

    Steps:
        1. Fetch the homepage.
        2. Parse homepage HTML to discover relevant links.
        3. Fetch each discovered link.
        4. Return all results (homepage + subpages).

    A failed subpage does *not* stop the rest of the crawl.

    Args:
        domain:    Company domain (e.g. ``"postman.com"``).
        browser:   An already-launched :class:`BrowserManager`.
        max_pages: Max subpages to discover (excluding homepage).

    Returns:
        A list of :class:`CrawlResult` for every page fetched
        (homepage first, then discovered subpages).
    """
    homepage_url = f"https://{domain}"
    results: list[CrawlResult] = []

    # ---- 1. Fetch homepage ---- #
    logger.info("Crawling domain: %s", domain)
    homepage_result = await browser.fetch(homepage_url)
    results.append(
        CrawlResult(url=homepage_url, category="homepage", page_result=homepage_result)
    )

    if not homepage_result.success:
        logger.warning(
            "Homepage fetch failed for %s -- skipping discovery", domain
        )
        return results

    # ---- 2. Discover links ---- #
    discovered = discover_links(
        homepage_html=homepage_result.html,
        homepage_url=homepage_result.final_url,  # use post-redirect URL
        max_pages=max_pages,
    )

    if not discovered:
        logger.info("No relevant subpages discovered for %s", domain)
        return results

    # ---- 3. Fetch discovered pages ---- #
    for link in discovered:
        logger.info("Fetching [%s]: %s", link.category, link.url)
        try:
            page_result = await browser.fetch(link.url)
        except Exception as exc:
            logger.error(
                "Unexpected error fetching %s: %s", link.url, exc
            )
            page_result = PageResult(
                requested_url=link.url,
                error=f"Unexpected error: {exc}",
            )

        results.append(
            CrawlResult(
                url=link.url,
                category=link.category,
                page_result=page_result,
            )
        )

    logger.info(
        "Crawl complete for %s: %d pages fetched (%d successful)",
        domain,
        len(results),
        sum(1 for r in results if r.page_result.success),
    )
    return results
