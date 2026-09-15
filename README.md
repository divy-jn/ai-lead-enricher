# Autonomous Lead Enrichment Agent

An AI-powered agent that accepts company domains, crawls their public websites using Playwright, preprocesses the content, and uses an LLM to produce structured lead enrichment data.

## Features

- **Browser Automation**: Uses Playwright to render JS-heavy pages
- **Smart Preprocessing**: Strips boilerplate HTML, extracts only useful text via BeautifulSoup
- **LLM-Powered Extraction**: Sends clean text to an LLM for structured analysis
- **Pydantic Output**: Returns validated, typed enrichment data
- **Resilient**: Handles timeouts, 404s, bot blocks, and LLM failures gracefully

## Output Fields

| Field                      | Description                                         |
|----------------------------|-----------------------------------------------------|
| `company_overview`         | Exactly 2 concise sentences about the company       |
| `target_audience`          | Who the company serves                              |
| `primary_generic_contacts` | General contact emails (e.g., info@, sales@)        |
| `other_public_contacts`    | Compliance, legal, or specialized public emails     |
| `contact_points`           | Union of the above two lists                        |
| `leadership`               | Name, role/title, LinkedIn URL (if discoverable)    |
| `confidence_score`         | 0.0–1.0 confidence in the extracted data            |
| `discovery_method`         | Method used to find pages (`homepage_links`, `sitemap`, etc.) |
| `pages_discovered`         | Number of subpages discovered                       |

## Prerequisites

- Python 3.10+
- `pip`

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install Playwright browsers
playwright install chromium

# 4. Configure environment
cp .env.example .env
# Edit .env with your specific LLM API key (e.g., from OpenAI/Ollama)
```

## Usage

Run the enrichment pipeline on a set of domains:
```bash
python -m src.main postman.com supabase.com vapi.ai
```

You can also run it on a single domain:
```bash
python -m src.main postman.com
```

The output will be saved as JSON in `output/output.json`.

## Testing

To run the automated tests:
```bash
pytest
```

## Project Structure

```
src/
├── main.py            # CLI entry point and orchestration
├── config.py          # Settings and environment config
├── browser.py         # Playwright browser management
├── crawler.py         # Page discovery and navigation logic
├── preprocessing.py   # HTML cleaning and text extraction
├── llm.py             # LLM API interaction
├── extractor.py       # Orchestrates crawl → preprocess → LLM pipeline
├── schemas.py         # Pydantic models for structured output
└── utils.py           # Shared helpers (logging, retries, etc.)
```

## Test Domains

- `postman.com`
- `supabase.com`
- `vapi.ai`

## License

MIT
