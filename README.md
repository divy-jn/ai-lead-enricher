# AI Lead Enricher

An autonomous Python agent that turns company domains into structured lead intelligence. It uses Playwright to browse public websites, discovers relevant pages, preprocesses rendered HTML into clean text, extracts deterministic signals such as public emails, and uses an LLM for evidence-based structured enrichment.

## What it does

Input one or more company domains:

```text
postman.com
supabase.com
vapi.ai
```

The pipeline then runs:

```text
Domain
  ↓
Playwright browser
  ↓
Relevant page discovery
  ↓
HTML preprocessing
  ↓
Deterministic email / LinkedIn extraction
  ↓
Grouped evidence
  ↓
LLM structured extraction
  ↓
Pydantic validation
  ↓
Confidence scoring
  ↓
output/output.json
```

## Features

- **Browser Automation** — Playwright with a reusable Chromium browser, isolated page contexts, timeouts, and graceful navigation failures.
- **Targeted Page Discovery** — prioritizes company/about, leadership/team, contact/support, press, pricing, careers, customers, partners, and legal pages while keeping a bounded crawl budget.
- **Sitemap Fallback** — can fall back to `sitemap.xml` or a sitemap referenced from `robots.txt` when homepage discovery is weak.
- **Smart Preprocessing** — removes scripts, styles, media, hidden elements, and repeated boilerplate before sending content to the LLM.
- **Deterministic Signals** — extracts public emails and LinkedIn URLs from the fetched HTML before LLM processing.
- **Evidence-Based LLM Extraction** — sends categorized clean evidence and instructs the model not to invent names, roles, emails, or LinkedIn URLs.
- **Structured Validation** — Pydantic validates the generated schema, including the two-sentence company overview and leadership name rules.
- **Email Protection** — LLM-returned emails are checked against deterministically discovered emails before they are accepted.
- **Source Traceability** — output includes successfully fetched source URLs and category-specific source URL lists.
- **Confidence Scoring** — confidence is computed deterministically from available evidence and crawl quality.
- **Resilient Batch Processing** — one domain can fail without stopping the remaining domains.
- **Token Tracking** — prompt, completion, and total token counts are captured per domain.
- **Simple Demo UI** — dependency-free HTML/CSS/JavaScript dashboard under `ui/` for the Loom demonstration.

## Output

Each domain produces structured data including:

| Field | Description |
|---|---|
| `company_overview` | Exactly 2 sentences describing the company from supplied evidence |
| `target_audience` | Company ICP / primary audience |
| `primary_generic_contacts` | General public contacts such as `info@`, `sales@`, or `support@` |
| `other_public_contacts` | Other public administrative/compliance contacts |
| `contact_points` | Deduplicated union of contact lists |
| `leadership` | Name, role/title, LinkedIn URL when explicitly supported |
| `confidence_score` | Deterministic 0.0–1.0 evidence-aware confidence |
| `source_urls` | Successfully fetched pages supplied as enrichment evidence |
| `company_source_urls` | Pages categorized as company/about evidence |
| `contact_source_urls` | Pages categorized as contact/support evidence |
| `leadership_source_urls` | Pages categorized as leadership/team evidence |
| `discovery_method` | `homepage_links`, `sitemap`, `robots_sitemap`, or `none` |
| `pages_discovered` | Number of selected subpages |
| `pages_crawled` | Number of pages attempted |
| `pages_successful` | Number of successful page fetches |
| `pages_failed` | Number of failed page fetches |
| `prompt_tokens` | Tokens used in the LLM prompt |
| `completion_tokens` | Tokens used in the LLM response |
| `total_tokens` | Total LLM tokens for the domain |

A sample run is stored in `output/output.json`.

## Setup

### 1. Create a virtual environment

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Playwright Chromium

```bash
playwright install chromium
```

### 4. Configure the LLM

Copy the example environment file:

```bash
copy .env.example .env
```

or on macOS/Linux:

```bash
cp .env.example .env
```

Then set the required `LLM_API_KEY` in `.env` and keep the key out of Git.

The current implementation uses the Ollama OpenAI-compatible API by default. The model and endpoint can be changed through the environment-backed settings in `src/config.py`.

## Usage

Run the default three test domains:

```bash
python -m src.main postman.com supabase.com vapi.ai
```

Run a single company:

```bash
python -m src.main postman.com
```

The generated result is written to:

```text
output/output.json
```

## Demo UI

The repository also contains a simple dependency-free frontend for demos:

```text
ui/
├── index.html
├── style.css
└── script.js
```

From the repository root:

```bash
python -m http.server 8000
```

Open:

```text
http://localhost:8000/ui/
```

The UI has a Demo Mode for the Loom and renders the sample enrichment JSON, including contacts, leadership, confidence, agent metadata, and source URLs.

## Testing

Run the test suite with:

```bash
pytest -q
```

The tests cover browser/crawler behavior, preprocessing, structured LLM handling, validation, retries, and batch failure isolation.

## Project Structure

```text
src/
├── main.py            # CLI entry point and JSON output
├── config.py          # Environment-backed settings
├── browser.py         # Playwright browser lifecycle and page fetching
├── crawler.py         # Relevant page discovery and sitemap fallback
├── preprocessing.py   # HTML cleaning + deterministic signal extraction
├── llm.py             # LLM prompts, structured output, retries, validation
├── extractor.py       # End-to-end enrichment orchestration
├── schemas.py         # Pydantic output models and validation
├── search.py          # Optional LinkedIn verification interface
└── utils.py           # Logging and shared helpers

ui/
├── index.html         # Demo dashboard markup
├── style.css          # Dashboard styling
└── script.js          # Demo workflow and JSON rendering

tests/
├── test_crawler.py
├── test_extractor.py
├── test_llm.py
└── test_preprocessing.py

output/
└── output.json        # Sample generated enrichment output
```

## Design Notes

The workflow uses lightweight custom Python orchestration rather than an agent framework. The process is intentionally bounded: page discovery and deterministic extraction happen before the LLM call, and the LLM is used for semantic synthesis and structured output rather than unrestricted web browsing.

The optional `src/search.py` module is an extension point for external LinkedIn verification. The core pipeline does not depend on an external search provider.

## Test Domains

- `postman.com`
- `supabase.com`
- `vapi.ai`

## License

MIT
