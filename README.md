# Autonomous Lead Enrichment Agent

An AI-powered agent that accepts company domains, crawls their public websites using Playwright, preprocesses the content, and uses an LLM to produce structured lead enrichment data.

## Features

- **Browser Automation**: Uses Playwright to render JS-heavy pages
- **Smart Preprocessing**: Strips boilerplate HTML, extracts only useful text via BeautifulSoup
- **LLM-Powered Extraction**: Sends clean text to an LLM for structured analysis
- **Pydantic Output**: Returns validated, typed enrichment data
- **Resilient**: Handles timeouts, 404s, bot blocks, and LLM failures gracefully

## Output Fields

| Field              | Description                                         |
|--------------------|-----------------------------------------------------|
| `company_overview` | Exactly 2 concise sentences about the company       |
| `target_audience`  | Who the company serves                              |
| `contact_points`   | Generic/public emails found on the site             |
| `leadership`       | Name, role/title, LinkedIn URL (if discoverable)    |
| `confidence_score` | 0.0–1.0 confidence in the extracted data            |

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
# Edit .env with your OpenAI API key
```

## Usage

```bash
python -m src.main postman.com supabase.com vapi.ai
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
