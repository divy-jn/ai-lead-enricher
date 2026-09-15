import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from openai import APIError, APITimeoutError, RateLimitError
import httpx

from src.llm import enrich_with_llm
from src.schemas import CompanyEnrichment, LeadershipEntry
from src.preprocessing import PreprocessedPage


@pytest.fixture
def dummy_pages():
    return [
        PreprocessedPage(
            url="https://postman.com",
            category="homepage",
            text="Postman is an API platform. We serve developers.",
            original_html_chars=100,
            cleaned_text_chars=50,
            reduction_percentage=50.0,
            emails={"info@postman.com"},
            linkedin_urls={"https://linkedin.com/company/postman"}
        )
    ]


@pytest.mark.asyncio
async def test_llm_valid_json(dummy_pages):
    """Test standard valid JSON extraction."""
    mock_client_instance = AsyncMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content='{"domain": "postman.com", "company_overview": "API Platform. Second sentence.", "target_audience": "Developers", "contact_points": ["info@postman.com"], "leadership": [], "confidence_score": 0.9}'))
    ]
    mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    mock_client_instance.chat.completions.create.return_value = mock_response

    with patch('src.llm.AsyncOpenAI', return_value=mock_client_instance):
        result = await enrich_with_llm("postman.com", dummy_pages)
        
        assert result.data.domain == "postman.com"
        assert result.data.target_audience == "Developers"
        assert result.total_tokens == 15
        
        # Verify it only took 1 attempt
        assert mock_client_instance.chat.completions.create.call_count == 1


@pytest.mark.asyncio
async def test_llm_validation_failure_then_retry_success(dummy_pages):
    """Test that it retries when Pydantic validation fails, and succeeds on the second try."""
    mock_client_instance = AsyncMock()
    
    # First response is missing required 'confidence_score'
    invalid_response = MagicMock()
    invalid_response.choices = [
        MagicMock(message=MagicMock(content='{"domain": "postman.com", "company_overview": "A. B.", "target_audience": "Devs"}'))
    ]
    
    # Second response is valid
    valid_response = MagicMock()
    valid_response.choices = [
        MagicMock(message=MagicMock(content='{"domain": "postman.com", "company_overview": "A. B.", "target_audience": "Devs", "contact_points": [], "leadership": [], "confidence_score": 0.9}'))
    ]
    
    mock_client_instance.chat.completions.create.side_effect = [invalid_response, valid_response]

    with patch('src.llm.AsyncOpenAI', return_value=mock_client_instance):
        result = await enrich_with_llm("postman.com", dummy_pages)
        
        assert result.data.confidence_score == 0.9
        assert mock_client_instance.chat.completions.create.call_count == 2


@pytest.mark.asyncio
async def test_llm_invalid_json_then_success(dummy_pages):
    """Test that it retries when JSON parsing fails."""
    mock_client_instance = AsyncMock()
    
    bad_json_response = MagicMock()
    bad_json_response.choices = [
        MagicMock(message=MagicMock(content='{ this is not valid json'))
    ]
    
    valid_response = MagicMock()
    valid_response.choices = [
        MagicMock(message=MagicMock(content='{"domain": "postman.com", "company_overview": "A. B.", "target_audience": "Devs", "contact_points": [], "leadership": [], "confidence_score": 0.9}'))
    ]
    
    mock_client_instance.chat.completions.create.side_effect = [bad_json_response, valid_response]

    with patch('src.llm.AsyncOpenAI', return_value=mock_client_instance):
        result = await enrich_with_llm("postman.com", dummy_pages)
        assert mock_client_instance.chat.completions.create.call_count == 2


@pytest.mark.asyncio
async def test_llm_rate_limit_retry(dummy_pages):
    """Test retries on transient API errors (RateLimitError)."""
    mock_client_instance = AsyncMock()
    
    req = httpx.Request("POST", "https://ollama.com/v1/chat/completions")
    rate_limit_error = RateLimitError("Rate limit exceeded", response=httpx.Response(429, request=req), body={})
    
    valid_response = MagicMock()
    valid_response.choices = [
        MagicMock(message=MagicMock(content='{"domain": "postman.com", "company_overview": "A. B.", "target_audience": "Devs", "contact_points": [], "leadership": [], "confidence_score": 0.9}'))
    ]
    
    mock_client_instance.chat.completions.create.side_effect = [rate_limit_error, valid_response]

    with patch('src.llm.AsyncOpenAI', return_value=mock_client_instance), \
         patch('src.llm.asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        
        result = await enrich_with_llm("postman.com", dummy_pages)
        assert mock_client_instance.chat.completions.create.call_count == 2
        mock_sleep.assert_called_once_with(2)  # Exponential backoff for attempt 1 -> 2^1


@pytest.mark.asyncio
async def test_llm_timeout_exhaustion(dummy_pages):
    """Test that it raises RuntimeError if it exhausts retries due to timeout."""
    mock_client_instance = AsyncMock()
    
    req = httpx.Request("POST", "https://ollama.com/v1/chat/completions")
    timeout_error = APITimeoutError(req)
    
    mock_client_instance.chat.completions.create.side_effect = timeout_error

    with patch('src.llm.AsyncOpenAI', return_value=mock_client_instance), \
         patch('src.llm.asyncio.sleep', new_callable=AsyncMock):
        
        with pytest.raises(RuntimeError, match="LLM extraction failed"):
            await enrich_with_llm("postman.com", dummy_pages)
            
        assert mock_client_instance.chat.completions.create.call_count == 3  # Based on settings.llm_max_retries = 3
