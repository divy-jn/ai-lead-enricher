import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.crawler import crawl_domain, discover_links, discover_sitemap_links
from src.browser import PageResult

@pytest.fixture
def mock_browser():
    browser = MagicMock()
    # By default, mock fetch returns success but no links
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
    """Test that a homepage with 0 candidate links triggers the sitemap fallback."""
    # The browser's default mock_fetch has no <a> tags, so 0 links discovered
    # Then it will try /sitemap.xml and we can mock its response to have <loc> tags
    
    async def side_effect_fetch(url):
        if url == "https://vapi.ai/sitemap.xml":
            return PageResult(
                requested_url=url,
                final_url=url,
                success=True,
                html='<?xml version="1.0" encoding="UTF-8"?><urlset><url><loc>https://vapi.ai/contact</loc></url></urlset>'
            )
        return PageResult(requested_url=url, final_url=url, success=True, html="<html><body></body></html>")

    mock_browser.fetch.side_effect = side_effect_fetch

    results, method, count = await crawl_domain("vapi.ai", mock_browser, max_pages=5)
    
    # Homepage + the 1 discovered contact page
    assert len(results) == 2
    assert results[1].category == "contact"
    assert method == "sitemap"
    assert count == 1


@pytest.mark.asyncio
async def test_crawl_domain_robots_fallback(mock_browser):
    """Test fallback to robots.txt if sitemap.xml is missing."""
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
    """Test that links are properly prioritized based on category weights."""
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
    # Highest priority should be 'about' (weight 100)
    assert links[0].category == "about"
    # Second should be 'team' (weight 90)
    assert links[1].category == "team"
    # Third should be 'contact' (weight 80)
    assert links[2].category == "contact"
    # Fourth should be 'pricing' (weight 70)
    assert links[3].category == "pricing"
