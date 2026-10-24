# ScrapeHeal-Gemma

**A multimodal self-healing web scraper and reusable Agent Skill.** When a website replaces a legacy table with a modern card or grid layout, ScrapeHeal-Gemma compares a screenshot with the changed DOM, asks Gemma 4 to propose new selectors, and verifies those selectors against the HTML using BeautifulSoup before reporting extracted rows.

## How it works

```mermaid
flowchart LR
  A[Webpage screenshot] --> C[Gemma 4 multimodal diagnosis]
  B[Cleaned HTML DOM] --> C
  C --> D[Proposed CSS fields and XPath]
  D --> E[BeautifulSoup local verification]
  E -->|0 rows or empty data| F[One correction request]
  F --> E
  E -->|Verified| G[Deterministic JSON records]
```

The dashboard provides a visual judge demo and an offline preset mode. The CLI returns the same JSON contract for agent workflows. The model's output is never treated as verified until the local DOM check succeeds.

## Open-Weight AI Model & License Compliance

- **Models used:** Google Gemma 4 `gemma-4-26b-a4b-it` and `gemma-4-31b-it`, called through the official `google-genai` Python SDK and Google AI Studio API.
- **Model license:** Apache License 2.0 ([license text](https://www.apache.org/licenses/LICENSE-2.0)); see Google's [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4) and [Gemma license information](https://ai.google.dev/gemma/apache_2).
- **Google Gemma terms:** [Gemma Terms of Use](https://ai.google.dev/gemma/terms).
- **Agent Skill Specification:** The `scrape-heal/SKILL.md` follows [agentskills.io/specification](https://agentskills.io/specification).
- **Repository license:** [Apache-2.0](LICENSE).

## Quickstart: Streamlit dashboard

```bash
# Use Python 3.10 or newer.
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# Add keys as GEMMA_API_KEY_1 and GEMMA_API_KEY_2 in .env for live inference.
streamlit run app.py
```

Choose one of the three built-in scenarios and press the two pipeline buttons in order. With no API key, presets use deterministic offline responses and still run BeautifulSoup verification. For a custom page, provide its HTML or URL, a matching screenshot, the old selector, and an extraction goal. The app reads `GEMMA_API_KEY_1` and `GEMMA_API_KEY_2` from `.env`; if a request with the first key fails, it tries the second. The Streamlit UI does not request keys.

## Quickstart: CLI Agent Skill

```bash
python -m pip install -r requirements.txt
python scrape-heal/scripts/heal_scraper.py \
  --preset football_league \
  --offline-mock \
  --output healed-results.json
```

Live custom page example:

```bash
# Configure GEMMA_API_KEY_1 (and optionally GEMMA_API_KEY_2) in .env.
python scrape-heal/scripts/heal_scraper.py \
  --html-file page.html \
  --screenshot page.png \
  --broken-selector 'table.legacy tbody tr' \
  --goal 'Extract product name, price, and stock' \
  --model gemma-4-26b-a4b-it \
  --thinking-level high \
  --output healed-results.json
```

The CLI also accepts `--url` with `--screenshot`, `--preset`, `--model`, `--thinking-level`, and `--output`. Read the [Agent Skill](scrape-heal/SKILL.md) and its [reference](scrape-heal/references/REFERENCE.md) for all arguments, JSON fields, and recovery behavior.

## Demo scenarios

| Preset | Broken legacy selector | Modern layout |
| --- | --- | --- |
| `football_league` | `table.league-standings-v1 tbody tr` | Isthmian Premier club standing cards |
| `cloud_gpu` | `table#gpu-pricing-legacy tr.instance-row` | GPU spot marketplace article cards |
| `industrial_b2b` | `ul.product-catalog-old li.item-box` | Industrial equipment cards with INR pricing |

## Development checks

```bash
python -m unittest discover -s tests -v
```

The smoke suite checks generated screenshots and mutated DOMs, zero-match legacy selectors, deterministic local extraction, DOM cleaning, and the Agent Skill frontmatter.
