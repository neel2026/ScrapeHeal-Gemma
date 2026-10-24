---
name: scrape-heal
description: Visually inspects webpages using open-weight Gemma 4 multimodal vision (gemma-4-26b-a4b-it / gemma-4-31b-it) alongside HTML DOM to diagnose broken CSS or XPath selectors, self-heal web scrapers with live BeautifulSoup verification, and extract structured JSON. Use when building scrapers, fixing broken selectors, or extracting data from mutated layouts.
license: Apache-2.0
compatibility: Requires Python 3.10+, google-genai, beautifulsoup4, pillow, requests, and GEMMA_API_KEY_1 from Google AI Studio.
metadata:
  author: ScrapeHeal-Gemma contributors
  version: "1.0.0"
  open_weight_models: "gemma-4-26b-a4b-it, gemma-4-31b-it"
  model_license: Apache-2.0
---

# ScrapeHeal-Gemma

Use this skill when a scraper stops finding records after a website redesign, when a table or list has moved to a card/grid layout, or when an agent needs to extract visible structured data and verify the replacement selectors against the actual DOM.

## What it does

ScrapeHeal-Gemma sends a webpage screenshot and a cleaned HTML DOM to an allowed Gemma 4 model. Gemma proposes a row selector, relative field selectors, an XPath equivalent, and a runnable BeautifulSoup example. The local engine runs those CSS selectors against the submitted HTML and returns the extracted records only with an explicit verification result. If the first proposed selector extracts no rows or values, it asks Gemma once to correct the proposal using the verification error.

## Run the CLI

Run commands from the repository root. Install dependencies with `python -m pip install -r requirements.txt`. Set `GEMMA_API_KEY_1` and optionally `GEMMA_API_KEY_2` in `.env` for live inference. If a request using the first key fails, the CLI tries the second.

Built-in deterministic demo:

```bash
python scrape-heal/scripts/heal_scraper.py --preset football_league --offline-mock
python scrape-heal/scripts/heal_scraper.py --preset cloud_gpu --offline-mock --output result.json
python scrape-heal/scripts/heal_scraper.py --preset industrial_b2b --offline-mock --model gemma-4-31b-it --thinking-level minimal
```

Live custom page (the screenshot must correspond to the supplied HTML):

```bash
python scrape-heal/scripts/heal_scraper.py --url https://example.com/catalog --screenshot page.png --broken-selector 'table.old-catalog tr' --goal 'Extract product name and price' --model gemma-4-26b-a4b-it --thinking-level high --output healed.json
python scrape-heal/scripts/heal_scraper.py --html-file page.html --screenshot page.png --broken-selector 'ul.products li' --goal 'Extract product name and stock' --output healed.json
```

Arguments: `--preset`, `--url`, `--html-file`, `--screenshot`, `--broken-selector`, `--goal`, `--model`, `--thinking-level`, `--output`, and `--offline-mock`. `--url` and `--html-file` require `--screenshot`; screenshots are not fabricated for custom webpages. `--offline-mock` explicitly forces deterministic local output for a built-in preset, even when API keys are configured; it is intended for CI and reliable demos.

## Agent workflow

1. Capture a screenshot of the current webpage and save the corresponding HTML. Remove credentials, personal data, and irrelevant DOM content before sharing either input.
2. Run the CLI with the broken selector and a concise extraction goal. Use `--preset` to demonstrate the pipeline offline.
3. Read `verified_on_dom`, `verification.matched_row_count`, and `verification.deterministic_records` in the JSON response. Do not ship selectors with `verified_on_dom: false`.
4. Review the generated selectors and patched code before integrating them into a production scraper.

## JSON contract and troubleshooting

See [references/REFERENCE.md](references/REFERENCE.md) for the full input/output schema, selector semantics, retry behavior, and troubleshooting notes. Model output is a proposal: only the local BeautifulSoup verification establishes that selectors work against the supplied HTML.
