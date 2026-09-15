import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.extractor import enrich_domains, enrich_domain
from src.schemas import DomainResult, LLMResult, CompanyEnrichment
from src.preprocessing import PreprocessedPage


@pytest.fixture
def dummy_llm_result():
    return LLMResult(
        data=CompanyEnrichment(
            domain="example.com",
            company_overview="Sentence one. Sentence two.",
            target_audience="Devs",
            contact_points=[],
            leadership=[],
            confidence_score=0.9
        ),
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15
    )


@pytest.fixture
def mock_crawl_results():
    # Return 1 successful crawl result
    crawl_res = MagicMock()
    crawl_res.url = "https://example.com"
    crawl_res.category = "homepage"
    crawl_res.page_result.success = True
    crawl_res.page_result.html = "<html><body><h1>Hello</h1></body></html>"
    crawl_res.page_result.final_url = "https://example.com"
    return [crawl_res]


@pytest.mark.asyncio
async def test_enrich_domains_all_success(mock_crawl_results, dummy_llm_result):
    """Test that multiple domains can be processed and succeed."""
    with patch("src.extractor.BrowserManager", autospec=True) as mock_browser_cls, \
         patch("src.extractor.crawl_domain", return_value=mock_crawl_results) as mock_crawl, \
         patch("src.extractor.enrich_with_llm", return_value=dummy_llm_result) as mock_llm:
        
        mock_browser_instance = mock_browser_cls.return_value
        
        results = await enrich_domains(["example.com", "other.com"])
        
        # Ensure browser was launched and closed exactly once
        assert mock_browser_instance.launch.call_count == 1
        assert mock_browser_instance.close.call_count == 1
        
        assert len(results) == 2
        for res in results:
            assert isinstance(res, DomainResult)
            assert res.status == "success"
            assert res.data is not None
            assert res.total_tokens == 15
            assert res.pages_crawled == 1
            assert res.pages_successful == 1


@pytest.mark.asyncio
async def test_enrich_domains_one_failure_isolation(mock_crawl_results, dummy_llm_result):
    """Test that a failure in one domain doesn't stop the batch process."""
    
    # We will mock enrich_domain to raise an exception for the first domain,
    # but the second domain should still be attempted inside enrich_domains.
    # Actually, enrich_domain itself catches exceptions and returns a failed DomainResult.
    
    # So we'll make crawl_domain raise an exception for the first domain.
    async def side_effect_crawl(domain, browser):
        if domain == "bad.com":
            raise ValueError("Crawler crashed")
        return mock_crawl_results

    with patch("src.extractor.BrowserManager", autospec=True), \
         patch("src.extractor.crawl_domain", side_effect=side_effect_crawl), \
         patch("src.extractor.enrich_with_llm", return_value=dummy_llm_result):
        
        results = await enrich_domains(["bad.com", "good.com"])
        
        assert len(results) == 2
        assert results[0].domain == "bad.com"
        assert results[0].status == "failed"
        assert "Crawler crashed" in results[0].error
        
        assert results[1].domain == "good.com"
        assert results[1].status == "success"
        assert results[1].data is not None


@pytest.mark.asyncio
async def test_enrich_domain_llm_failure(mock_crawl_results):
    """Test that a failure in the LLM step produces a failed DomainResult with operational counts."""
    
    async def mock_llm_fail(*args, **kwargs):
        raise RuntimeError("LLM API is down")

    with patch("src.extractor.crawl_domain", return_value=mock_crawl_results), \
         patch("src.extractor.enrich_with_llm", side_effect=mock_llm_fail):
        
        # Test directly against enrich_domain
        result = await enrich_domain("example.com")
        
        assert result.status == "failed"
        assert result.error == "LLM Error: LLM API is down"
        assert result.pages_crawled == 1
        assert result.pages_successful == 1
        assert result.data is None
