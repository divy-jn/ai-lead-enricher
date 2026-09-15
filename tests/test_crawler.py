import pytest
from unittest.mock import AsyncMock, MagicMock

from src.crawler import crawl_domain, discover_links
from src.browser import PageResult

@pytest.fixture
def mock_browser():
    browser = MagicMock()
    async def mock_fetch(url):
        return PageResult(
            requested_url=url,
            final_url=url,
            success=True,
            html="<html><body><h1>Test</h1></body></html>"
        )
    browser.fetch = AsyncMock(side_effect=mock_fetch)
    return browser


@pytest.mark.asyncio
async def test_crawl_domain_vapi_empty_homepage(mock_browser):
    async def side_effect_fetch(url):
        if url == "https://vapi.ai/sitemap.xml":
            return PageResult(
                requested_url=url,
                final_url=url,
                success=True,
                html='<?xml version="1.0"?><urlset><url><loc>https://vapi.ai/contact</loc></url></urlset>'
            )
        return PageResult(requested_url=url, final_url=url, success=True, html="<html><body></body></html>")

    mock_browser.fetch.side_effect = side_effect_fetch
    results, method, count = await crawl_domain("vapi.ai", mock_browser, max_pages=5)
    assert len(results) == 2
    assert results[1].category == "contact"
    assert method == "sitemap"
    assert count == 1


@pytest.mark.asyncio
async def test_crawl_domain_robots_fallback(mock_browser):
    async def side_effect_fetch(url):
        if url == "https://test.com/sitemap.xml":
            return PageResult(requested_url=url, final_url=url, success=False, error="404")
        if url == "https://test.com/robots.txt":
            return PageResult(
                requested_url=url,
                final_url=url,
                success=True,
                html='User-agent: *\nSitemap: https://test.com/custom_sitemap.xml'
            )
        if url == "https://test.com/custom_sitemap.xml":
            return PageResult(
                requested_url=url,
                final_url=url,
                success=True,
                html='<urlset><url><loc>https://test.com/about</loc></url></urlset>'
            )
        return PageResult(requested_url=url, final_url=url, success=True, html="<html><body></body></html>")

    mock_browser.fetch.side_effect = side_effect_fetch
    results, method, count = await crawl_domain("test.com", mock_browser, max_pages=5)
    assert len(results) == 2
    assert results[1].category == "about"
    assert method == "robots_sitemap"
    assert count == 1


def test_category_priority_sorting():
    html = '''
    <html><body>
        <a href="/pricing">Pricing</a>
        <a href="/team">Team</a>
        <a href="/about">About</a>
        <a href="/contact">Contact</a>
    </body></html>
    '''
    links = discover_links(html, "https://test.com", max_pages=5)
    assert len(links) == 4
    assert links[0].category == "leadership"
    assert links[1].category == "about"
    assert links[2].category == "contact"
    assert links[3].category == "pricing"


def test_management_substring_is_not_misclassified_as_leadership():
    """A product URL containing 'management' must not become a leadership page."""
    html = '''
    <html><body>
        <a href="/solutions/api-lifecycle-management">API Lifecycle Management</a>
        <a href="/about">About</a>
    </body></html>
    '''
    links = discover_links(html, "https://postman.com", max_pages=5)
    management_link = next(link for link in links if "api-lifecycle-management" in link.url)
    assert management_link.category != "leadership"
    assert management_link.category == "uncategorised"
