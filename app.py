"""Streamlit judge dashboard for the ScrapeHeal-Gemma demo."""

from __future__ import annotations

import json
import hashlib
import sys
from html import escape
from pathlib import Path

import streamlit as st
from PIL import Image

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scrape-heal"))

from scripts.heal_scraper import ALLOWED_MODELS, configured_api_keys, heal_scraper_with_gemma4, verify_broken_selector
from scripts.live_examples import BOOKS_TO_SCRAPE_URL, fetch_books_to_scrape
from scripts.presets import build_preset


st.set_page_config(page_title="ScrapeHeal-Gemma", page_icon="🩹", layout="wide")
st.markdown(
    """
    <style>
    .stApp { background: radial-gradient(ellipse at 12% 0%, #1b2945 0, #0b1020 43%, #080d18 100%); color: #edf3ff; }
    [data-testid="stHeader"] { background: transparent; }
    .hero { padding: 1.1rem 1.4rem; margin-bottom: 1rem; border: 1px solid #2a3954; border-radius: 18px; background: linear-gradient(105deg,#151f33,#10192b 58%,#122c32); }
    .eyebrow { color:#62e2c1; letter-spacing:.14em; font-size:.72rem; font-weight:800; }
    .hero h1 { margin:.15rem 0 .25rem; font-size:2.25rem; color:#f5f7ff; }
    .hero p { color:#9cacc8; margin:.1rem 0 .7rem; }
    .badge { display:inline-block; padding:.32rem .6rem; border:1px solid #344660; border-radius:999px; color:#bfd1e9; font-size:.75rem; margin:.15rem .28rem .1rem 0; background:#18243a; }
    .green { color:#5ce0b6 !important; border-color:#22795f !important; background:#102c28 !important; }
    .redtrace { border:1px solid #873a4b; background:#2a1521; color:#ffb2bc; padding:.85rem 1rem; border-radius:12px; font-family:monospace; }
    .pane { border:1px solid #27364f; background:#111a2b; padding:1rem; border-radius:15px; }
    .stButton button { border-radius:10px; font-weight:700; }
    div[data-testid="stMetric"] { background:#111a2b; border:1px solid #283850; padding:.7rem; border-radius:12px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <section class="hero">
      <div class="eyebrow">MULTIMODAL SCRAPER RECOVERY · HACKTOBERFEST 2026</div>
      <h1>🩹 ScrapeHeal-Gemma</h1>
      <p>When a site changes its layout, Gemma 4 maps the screenshot to the new DOM, proposes selectors, and lets BeautifulSoup prove them locally.</p>
      <span class="badge">Open-Weight Model: Google Gemma 4 (gemma-4-26b-a4b-it / gemma-4-31b-it)</span>
      <span class="badge">Model License: Apache 2.0</span>
      <span class="badge">Agent Standard: agentskills.io v1.0 (scrape-heal/SKILL.md)</span>
    </section>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("## Run a pipeline")
    api_keys = configured_api_keys()
    run_mode = st.radio("Run mode", ("Demo: Football (reliable)", "Live: Books to Scrape"))
    model_id = st.selectbox(
        "Gemma 4 model",
        ALLOWED_MODELS,
        format_func=lambda value: (
            "gemma-4-26b-a4b-it · 26B MoE / 4B active · fast vision"
            if value == ALLOWED_MODELS[0]
            else "gemma-4-31b-it · 31B dense · deep reasoning"
        ),
    )
    thinking_level = st.radio("Gemma 4 thinking level", ("high", "minimal"), horizontal=True)
    st.caption("API keys load from .env. Key 2 is tried if key 1 fails.")

if st.session_state.get("_active_mode") != run_mode:
    for key in ("legacy_result", "heal_result", "run_error", "_books_html"):
        st.session_state.pop(key, None)
    st.session_state["_active_mode"] = run_mode

demo_mode = run_mode == "Demo: Football (reliable)"
preset = build_preset("football_league") if demo_mode else None
if demo_mode:
    html_dom = preset.html
    screenshot = preset.image
    broken_selector = preset.broken_selector
    goal = preset.goal
else:
    html_dom = st.session_state.get("_books_html", "")
    screenshot = None
    broken_selector = "table.legacy-book-list tbody tr"
    goal = "Extract each book's title, price, and availability from the visible listing."

col_left, col_right = st.columns([1.05, 0.95], gap="large")
with col_left:
    st.markdown("### 1. Target webpage viewport & DOM")
    if demo_mode:
        st.caption("Football fixture with a deliberately broken selector. When keys are configured, Gemma tries to repair it; a local fallback keeps the demo reliable.")
        st.image(screenshot, width="stretch", caption="Football layout supplied to the demo healing step")
    else:
        st.markdown(f"Live website: [{BOOKS_TO_SCRAPE_URL}]({BOOKS_TO_SCRAPE_URL})")
        st.caption("The page HTML is fetched when you run the pipeline. Open the site, take a screenshot of its first page, and upload it here so Gemma sees the matching layout.")
        screenshot_file = st.file_uploader("Screenshot of Books to Scrape", type=("png", "jpg", "jpeg"))
        if screenshot_file:
            try:
                screenshot = Image.open(screenshot_file).convert("RGB")
                st.image(screenshot, width="stretch", caption="Screenshot passed to Gemma 4 Vision")
            except Exception as exc:
                st.error(f"Could not read the screenshot: {exc}")
        broken_selector = st.text_input("Broken legacy selector", value=broken_selector)
        goal = st.text_input("Extraction goal", value=goal)
        if not api_keys:
            st.warning("Live mode needs GEMMA_API_KEY_1 in the ignored .env file. The demo works without API keys.")
    if broken_selector:
        st.markdown(f"**Legacy selector**  \n`{broken_selector}`")
    if goal:
        st.markdown(f"**Extraction goal**  \n{goal}")
    with st.expander("Inspect page HTML DOM"):
        st.code(html_dom or "Books to Scrape HTML will be fetched when you run the live pipeline.", language="html")

input_fingerprint = hashlib.sha256(
    json.dumps([
        run_mode,
        broken_selector,
        goal,
        model_id,
        thinking_level,
        [hashlib.sha256(key.encode()).hexdigest() for key in api_keys],
        screenshot.size if screenshot is not None else None,
        hashlib.sha256(screenshot.tobytes()).hexdigest() if screenshot is not None else None,
    ]).encode()
).hexdigest()
if st.session_state.get("_input_fingerprint") != input_fingerprint:
    for key in ("legacy_result", "heal_result", "run_error"):
        st.session_state.pop(key, None)
    st.session_state["_input_fingerprint"] = input_fingerprint

with col_right:
    st.markdown("### 2. Self-healing pipeline & verification")
    button_label = (
        "Run Demo: broken selector → repaired selector"
        if demo_mode
        else "Run Live: fetch Books to Scrape → heal with Gemma"
    )
    run_pipeline = st.button(button_label, type="primary", width="stretch")
    if run_pipeline:
        st.session_state.pop("legacy_result", None)
        st.session_state.pop("heal_result", None)
        st.session_state.pop("run_error", None)
        try:
            if not demo_mode:
                if screenshot is None:
                    raise ValueError("Upload a screenshot of the current Books to Scrape page first.")
                if not api_keys:
                    raise ValueError("Live mode needs GEMMA_API_KEY_1 in .env.")
                with st.spinner("Fetching the live Books to Scrape HTML…"):
                    html_dom = fetch_books_to_scrape()
                st.session_state["_books_html"] = html_dom

            legacy = verify_broken_selector(html_dom, broken_selector)
            st.session_state["legacy_result"] = legacy
    legacy_result = st.session_state.get("legacy_result")
    if legacy_result:
        if legacy_result["matched_count"] == 0:
            error = legacy_result["error"] or "0 elements matched"
            st.markdown(
                f"<div class='redtrace'>SelectorError: 0 elements matched <code>{escape(broken_selector)}</code> in current DOM<br>{escape(error)}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.success(f"Legacy selector unexpectedly matched {legacy_result['matched_count']} elements.")
    if st.session_state.get("run_error"):
        st.error(f"Pipeline stopped: {st.session_state['run_error']}")

    result = st.session_state.get("heal_result")
    if result:
        ver = result["verification"]
        if demo_mode and result.get("offline_mock"):
            st.info("Deterministic local demo: no API keys are configured, so this run did not call Gemma.")
        elif demo_mode and result.get("offline_fallback"):
            st.warning("Gemma did not produce a verified selector; the demo completed with its verified football preset repair.")
        elif demo_mode:
            st.info("Gemma repaired the football fixture live; its records are fixed demo data.")
        elif result.get("api_key_failovers"):
            st.info("The first Gemma API key failed; the request succeeded with the second key.")
        if ver["verified"]:
            st.markdown(
                f"<span class='badge green'>✅ {label}: {ver['matched_row_count']} rows extracted deterministically</span>",
                unsafe_allow_html=True,
            )
        else:
            st.error(f"Selector verification failed after {result['attempts']} attempt(s): {ver['error']}")
        m1, m2, m3 = st.columns(3)
        m1.metric("Latency", f"{result['latency_seconds']:.2f}s")
        m2.metric("Model", result["model"])
        m3.metric("Thinking", result["thinking_level"])
        st.caption(f"{origin} · {result['attempts']} selector attempt(s)" + (" · Cached result" if result.get("cached") else ""))
        diff_left, diff_right = st.columns(2)
        with diff_left:
            st.markdown("**❌ Broken legacy selector**")
            st.code(broken_selector, language="css")
        with diff_right:
            st.markdown("**✅ Healed row selector + XPath**")
            st.code(result["healed_row_css_selector"], language="css")
            st.code(result.get("healed_xpath", ""), language="xpath")
        tabs = st.tabs(["📊 Verified Extracted Data", "🧠 Gemma 4 Visual & DOM Reasoning", "🐍 Patched Python Scraper", "🧩 Agent Skill (SKILL.md) & CLI"])
        with tabs[0]:
            st.dataframe(ver["deterministic_records"], width="stretch", hide_index=True)
            st.download_button(
                "Download verified records as JSON",
                data=json.dumps(ver["deterministic_records"], ensure_ascii=False, indent=2),
                file_name="scrapeheal-verified-records.json",
                mime="application/json",
            )
            st.markdown("**Field selectors**")
            st.json(result["healed_field_selectors"])
        with tabs[1]:
            st.markdown("**Visual analysis**")
            st.write(result.get("visual_analysis", ""))
            st.markdown("**DOM mutation diagnosis**")
            st.write(result.get("dom_mutation_diagnosis", ""))
            st.markdown("**Visual-to-DOM mapping summary**")
            st.write(result.get("reasoning_summary", ""))
            st.progress(max(0, min(100, int(result.get("confidence_score", 0)))) / 100, text=f"Confidence: {result.get('confidence_score', 0)}%")
        with tabs[2]:
            st.code(result.get("patched_python_code", ""), language="python")
            st.caption("Verification: " + ("passed against the page HTML" if ver["verified"] else "not verified"))
        with tabs[3]:
            skill_path = ROOT / "scrape-heal" / "SKILL.md"
            st.markdown(skill_path.read_text(encoding="utf-8"))
            st.code("python scrape-heal/scripts/heal_scraper.py --preset football_league --offline-mock", language="bash")
            st.markdown("**Pipeline**")
            st.markdown("```mermaid\n" + result.get("mermaid_diagram", "") + "\n```")
            if legacy["matched_count"] != 0:
                raise ValueError("The legacy selector unexpectedly matched this page; change it to a selector that no longer matches.")

            hint = None
            if preset:
                hint = {
                    "row_selector": preset.row_selector,
                    "field_selectors": preset.field_selectors,
                    "records": preset.records,
                    "xpath": preset.xpath,
                }
            progress_message = (
                "Running the deterministic football repair…"
                if demo_mode and not api_keys
                else "Gemma 4 is comparing the screenshot and DOM. This can take up to two minutes per request; BeautifulSoup will verify the result…"
            )
            with st.spinner(progress_message):
                result = heal_scraper_with_gemma4(
                    html_dom,
                    screenshot,
                    broken_selector,
                    goal,
                    model_id=model_id,
                    thinking_level=thinking_level,
                    offline_mock=demo_mode and not bool(api_keys),
                    preset_hint=hint,
                )
            st.session_state["heal_result"] = result
        except Exception as exc:
            st.session_state["run_error"] = str(exc)

            label = "Verified on Books to Scrape HTML" if not demo_mode else "Verified on football demo HTML"
        if result.get("offline_mock"):
            origin = "Deterministic local demo"
        elif result.get("offline_fallback"):
            origin = "Verified football preset fallback"
        else:
            origin = "Gemma 4 live inference"
