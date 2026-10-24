# ScrapeHeal-Gemma Reference

## Input

| Field | Type | Meaning |
| --- | --- | --- |
| `html_dom` | string | Page HTML, cleaned to remove scripts, styles, SVG, noscript, comments, and repeated whitespace before inference. |
| `screenshot` | PNG/JPEG or PIL image | Visual state corresponding to the HTML snapshot. Sent to Gemma 4 as an `image/png` part. |
| `broken_selector` | string | Legacy CSS selector whose result is expected to be empty or invalid. |
| `goal` | string | Fields or records the caller wants to extract. |
| `model_id` | string | One of `gemma-4-26b-a4b-it` or `gemma-4-31b-it`. |
| `thinking_level` | string | `high` or `minimal`. |

## Output JSON

| Field | Type | Meaning |
| --- | --- | --- |
| `visual_analysis` | string | Short description of the relevant visual layout. |
| `dom_mutation_diagnosis` | string | Explanation of why the old selector no longer matches. |
| `reasoning_summary` | string | Concise visual-to-DOM mapping summary. |
| `healed_row_css_selector` | string | CSS selector for repeated record containers. |
| `healed_field_selectors` | object | Field name to relative CSS selector mapping. |
| `healed_xpath` | string | Equivalent XPath expression for the row containers. |
| `confidence_score` | integer | Model-estimated confidence from 0 to 100. |
| `visual_extracted_data` | array | Records proposed directly from the visual input. |
| `patched_python_code` | string | Runnable BeautifulSoup extraction example. |
| `mermaid_diagram` | string | Mermaid flowchart describing the recovery pipeline. |
| `verification` | object | `verified`, `matched_row_count`, `deterministic_records`, and `error` from local BeautifulSoup. |
| `verified_on_dom` | boolean | True only when local selection finds rows and every matched row has at least one non-empty extracted value. |
| `attempts` | integer | 1 normally; 2 if Gemma receives one selector correction request. |
| `model` / `thinking_level` | string | Selected model and reasoning mode. |
| `latency_seconds` / `cached` | number / boolean | Elapsed runtime and whether a cached response was reused. |

`verify_healed_selectors(html_dom, row_selector, field_selectors)` returns:

```json
{
  "verified": true,
  "matched_row_count": 2,
  "deterministic_records": [{"name": "Example", "price": "$10"}],
  "error": null
}
```

`verify_broken_selector(html_dom, broken_selector)` returns a match count and an error string when BeautifulSoup rejects the CSS selector.

## Failure and recovery behavior

- Invalid or zero-match legacy selectors are reported as zero matches with the parser error retained when present.
- Model JSON must contain all documented analysis, selector, code, diagram, and visual-record fields with valid types, including an integer confidence from 0 to 100. Invalid responses raise a clear error or activate the labeled preset fallback.
- A failed first verification is sent back to Gemma once. A second failure remains visible in `verification.error`; no records are labeled verified.
- API/network/quota exceptions are shown to the caller. The dashboard supports built-in offline scenarios; the CLI mock switch is limited to runs without an API key.
- Only the model prompt DOM is capped at 15,000 characters. BeautifulSoup verifies selectors against the complete original HTML. Use a focused DOM region if the model cannot see the target records in its retained context.
- Field selectors are scoped to each row and should resolve to a single element. Missing fields return an empty string and remain visible in records.
- Live API requests have a 45-second timeout so a stalled request can activate preset fallback.
- The in-memory cache separates mock and live modes and includes the complete HTML snapshot. Failed verification and temporary API fallback results are not cached, so the next live attempt can recover.
- The dashboard clears previous verification when inputs or settings change. Custom URL HTML is fetched only when the fetch button is pressed, keeping one snapshot through both demo steps.

## Troubleshooting

- **`Set GEMINI_API_KEY`**: Add the key to `.env` or export it in the shell that launches the app.
- **HTTP 429 / quota error**: Wait before retrying. The CLI does not silently switch model families; use a built-in offline preset during a demo interruption.
- **No rows verified**: Confirm the screenshot and HTML came from the same page state, inspect the cleaned DOM, and look for repeated containers with stable attributes.
- **Selector syntax error**: Review the proposed CSS with BeautifulSoup/SoupSieve compatibility in mind. The deterministic verifier captures the exact parser error.
- **Remote page is incomplete**: Some sites need JavaScript or authentication to render the page. Supply an HTML snapshot and screenshot captured from the authenticated browser session.
