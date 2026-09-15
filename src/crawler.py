"""
crawler.py -- Relevant-page discovery from a company homepage.
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

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "about": ["about", "about-us", "who-we-are", "our-story", "company", "our-company"],
    "leadership": ["leadership", "management", "founders", "executives", "board", "team", "our-team", "people"],
    "contact": ["contact", "contact-us", "get-in-touch", "reach-us", "support", "help"],
    "press": ["press", "news", "media", "newsroom"],
    "pricing": ["pricing", "plans", "price"],
    "careers": ["careers", "jobs", "work-with-us", "join-us", "hiring"],
    "customers": ["customers", "case-studies", "testimonials", "success-stories"],
    "product": ["product", "features", "solutions", "platform", "how-it-works"],
    "partners": ["partners", "integrations", "marketplace"],
    "legal": ["legal", "privacy", "security", "terms", "policy"],
}

CATEGORY_WEIGHTS: dict[str, float] = {
    "leadership": 120.0,
    "about": 100.0,
    "contact": 90.0,
    "press": 80.0,
    "pricing": 70.0,
    "product": 60.0,
    "careers": 50.0,
    "customers": 50.0,
    "partners": 50.0,
    "legal": 40.0,
}

CATEGORY_LIMITS: dict[str, int] = {
    "leadership": 3,
    "contact": 2,
    "about": 2,
}

_SKIP_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r, re.IGNORECASE)
    for r in [
        r"login", r"log-in", r"signin", r"sign-in", r"signup", r"sign-up",
        r"register", r"auth", r"oauth", r"sso", r"account", r"dashboard",
        r"\bapp\.", r"\bdocs\.", r"\bblog\.", r"\bhelp\.", r"\bstatus\.",
        r"\bcdn\.", r"\bapi\.",
    ]
]

_FILE_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
    ".pdf", ".zip", ".tar", ".gz", ".mp4", ".mp3", ".woff", ".woff2",
    ".ttf", ".eot", ".css", ".js", ".xml", ".json",
})


@dataclass(frozen=True)
class DiscoveredLink:
    url: str
    category: str
    score: float
    anchor_text: str = ""


@dataclass(frozen=True)
class CrawlResult:
    url: str
    category: str
    page_result: PageResult


def _base_domain(url: str) -> str:
    host = urlparse(url).hostname or ""
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "net", "edu", "gov"):
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _is_same_site(candidate_url: str, homepage_url: str) -> bool:
    return _base_domain(candidate_url) == _base_domain(homepage_url)


def _should_skip(url: str, anchor_text: str) -> bool:
    combined = f"{url} {anchor_text}"
    return any(p.search(combined) for p in _SKIP_PATTERNS)


def _has_file_extension(path: str) -> bool:
    lower = path.lower()
    return any(lower.endswith(ext) for ext in _FILE_EXTENSIONS)


def _keyword_in_text(keyword: str, text: str) -> bool:
    """Match a keyword as a phrase/word, not as an arbitrary substring."""
    return re.search(rf"(?<![\w-]){re.escape(keyword)}(?![\w-])", text) is not None


def _score_link(url: str, anchor_text: str) -> tuple[str, float]:
    """Score links using exact path segments and bounded anchor-text matches."""
    parsed = urlparse(url)
    path = parsed.path.lower().strip("/")
    path_segments = [segment for segment in path.split("/") if segment]
    text_lower = anchor_text.lower()

    best_category = "uncategorised"
    best_score = 0.0

    for category, keywords in CATEGORY_KEYWORDS.items():
        cat_score = 0.0
        for kw in keywords:
            # Strong signal: the whole path segment is the keyword.
            if kw in path_segments:
                cat_score += 3.0

            # Anchor text signal: require a bounded phrase/word match.
            if _keyword_in_text(kw, text_lower):
                cat_score += 2.0

        if cat_score > 0:
            if len(path_segments) <= 1:
                cat_score += 0.5
            cat_score += CATEGORY_WEIGHTS.get(category, 0.0)

            if cat_score > best_score:
                best_score = cat_score
                best_category = category

    return best_category, best_score


def _select_links(scored: list[DiscoveredLink], max_pages: int) -> list[DiscoveredLink]:
    """Select high-value links while allowing multiple high-value pages."""
    selected: list[DiscoveredLink] = []
    category_counts: dict[str, int] = {}

    for link in sorted(scored, key=lambda d: d.score, reverse=True):
        limit = CATEGORY_LIMITS.get(link.category, 1)
        count = category_counts.get(link.category, 0)
        if count >= limit:
            continue
        category_counts[link.category] = count + 1
        selected.append(link)
        if len(selected) >= max_pages:
            break

    return selected


def discover_links(
    homepage_html: str,
    homepage_url: str,
    max_pages: int | None = None,
) -> list[DiscoveredLink]:
    """Parse homepage HTML and return scored, deduplicated relevant links."""
    if max_pages is None:
        max_pages = settings.max_crawl_pages

    soup = BeautifulSoup(homepage_html, "lxml")
    seen_urls: set[str] = set()
    scored: list[DiscoveredLink] = []

    for a_tag in soup.find_all("a", href=True):
        raw_href = a_tag["href"].strip()
        if raw_href.startswith(("mailto:", "javascript:", "tel:", "#", "data:")):
            continue

        try:
            full_url = urljoin(homepage_url, raw_href)
        except Exception:
            continue

        parsed = urlparse(full_url)
        if parsed.scheme not in ("http", "https"):
            continue

        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if clean_url.endswith("/") and clean_url != f"{parsed.scheme}://{parsed.netloc}/":
            clean_url = clean_url.rstrip("/")

        if clean_url in seen_urls:
            continue
        if _has_file_extension(parsed.path):
            continue
        if not _is_same_site(full_url, homepage_url):
            continue

        homepage_parsed = urlparse(homepage_url)
        homepage_clean = f"{homepage_parsed.scheme}://{homepage_parsed.netloc}{homepage_parsed.path}".rstrip("/")
        if clean_url.rstrip("/") == homepage_clean.rstrip("/"):
            continue

        anchor_text = a_tag.get_text(separator=" ", strip=True)
        if _should_skip(clean_url, anchor_text):
            continue

        category, score = _score_link(clean_url, anchor_text)
        if score <= 0:
            continue

        seen_urls.add(clean_url)
        scored.append(DiscoveredLink(clean_url, category, score, anchor_text[:120]))

    selected = _select_links(scored, max_pages)
    logger.info("Discovered %d candidate links, selected %d (max %d)", len(scored), len(selected), max_pages)
    for link in selected:
        logger.debug("  [%s] score=%.1f %s (%s)", link.category, link.score, link.url, link.anchor_text[:60])
    return selected


async def discover_sitemap_links(
    domain: str,
    browser: BrowserManager,
    max_pages: int,
) -> tuple[list[DiscoveredLink], str]:
    """Try sitemap.xml or robots.txt sitemap discovery."""

    async def try_sitemap(url: str) -> list[DiscoveredLink]:
        logger.info("Attempting sitemap discovery at %s", url)
        res = await browser.fetch(url)
        if not res.success or not res.html:
            return []

        loc_urls = re.findall(r"<loc>\s*(.*?)\s*</loc>", res.html, flags=re.IGNORECASE)
        if not loc_urls:
            return []

        seen_urls: set[str] = set()
        scored: list[DiscoveredLink] = []
        homepage_url = f"https://{domain}"

        for loc_url in loc_urls:
            if not loc_url.startswith("http") or not _is_same_site(loc_url, homepage_url):
                continue

            parsed = urlparse(loc_url)
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if clean_url.endswith("/") and clean_url != f"{parsed.scheme}://{parsed.netloc}/":
                clean_url = clean_url.rstrip("/")

            if clean_url in seen_urls:
                continue
            if clean_url.rstrip("/") == homepage_url.rstrip("/"):
                continue
            if _has_file_extension(parsed.path) or _should_skip(clean_url, ""):
                continue

            category, score = _score_link(clean_url, "")
            if score <= 0:
                continue

            seen_urls.add(clean_url)
            scored.append(DiscoveredLink(clean_url, category, score, "[sitemap]"))

        return _select_links(scored, max_pages)

    links = await try_sitemap(f"https://{domain}/sitemap.xml")
    if links:
        return links, "sitemap"

    logger.info("Attempting robots.txt discovery at https://%s/robots.txt", domain)
    res = await browser.fetch(f"https://{domain}/robots.txt")
    if res.success and res.html:
        soup = BeautifulSoup(res.html, "html.parser")
        text = soup.get_text("\n")
        for line in text.splitlines():
            if line.strip().lower().startswith("sitemap:"):
                sitemap_url = line.split(":", 1)[1].strip()
                links = await try_sitemap(sitemap_url)
                if links:
                    return links, "robots_sitemap"

    return [], "none"


async def crawl_domain(
    domain: str,
    browser: BrowserManager,
    max_pages: int | None = None,
) -> tuple[list[CrawlResult], str, int]:
    """Fetch homepage, discover relevant pages, optionally use sitemap fallback, and fetch subpages."""
    if max_pages is None:
        max_pages = settings.max_crawl_pages

    homepage_url = f"https://{domain}"
    results: list[CrawlResult] = []
    discovery_method = "homepage_links"

    logger.info("Crawling domain: %s", domain)
    homepage_result = await browser.fetch(homepage_url)
    results.append(CrawlResult(homepage_url, "homepage", homepage_result))

    if not homepage_result.success:
        logger.warning("Homepage fetch failed for %s -- skipping discovery", domain)
        return results, "none", 0

    discovered = discover_links(
        homepage_html=homepage_result.html,
        homepage_url=homepage_result.final_url,
        max_pages=max_pages,
    )

    discovered_categories = {link.category for link in discovered}
    coverage_weak = (
        len(discovered) < 2
        or ("about" not in discovered_categories and "contact" not in discovered_categories)
    )

    if coverage_weak:
        logger.info("Coverage from homepage is weak. Attempting fallback discovery.")
        fallback_links, fallback_method = await discover_sitemap_links(domain, browser, max_pages)
        if fallback_links:
            existing_urls = {link.url for link in discovered}
            for link in fallback_links:
                if link.url not in existing_urls:
                    discovered.append(link)

            discovery_method = fallback_method
            discovered = _select_links(discovered, max_pages)

    pages_discovered = len(discovered)
    for link in discovered:
        logger.info("Fetching [%s]: %s", link.category, link.url)
        try:
            page_result = await browser.fetch(link.url)
        except Exception as exc:
            logger.error("Unexpected error fetching %s: %s", link.url, exc)
            page_result = PageResult(requested_url=link.url, error=f"Unexpected error: {exc}")

        results.append(CrawlResult(link.url, link.category, page_result))

    logger.info(
        "Crawl complete for %s: %d pages fetched (%d successful)",
        domain,
        len(results),
        sum(1 for r in results if r.page_result.success),
    )
    return results, discovery_method, pages_discovered
