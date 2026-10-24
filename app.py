"""Streamlit judge dashboard for the ScrapeHeal-Gemma demo."""

from __future__ import annotations

import json
import hashlib
import os
import sys
from pathlib import Path

import requests
import streamlit as st
from PIL import Image

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scrape-heal"))

from scripts.heal_scraper import ALLOWED_MODELS, heal_scraper_with_gemma4, verify_broken_selector
from scripts.presets import PRESETS, build_preset


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
    st.markdown("## Demo controls")
    api_key = st.text_input(
        "Gemini API Key",
        value=os.environ.get("GEMINI_API_KEY", ""),
        type="password",
        help="Loaded from GEMINI_API_KEY or .env. It is used for this session only.",
    )
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
    scenario = st.selectbox("Scenario", [*PRESETS.values(), "Custom Live URL / Screenshot Upload"])
    st.caption("No API key? Built-in scenarios run in clearly labeled offline demo mode.")

if st.session_state.get("_active_scenario") != scenario:
    st.session_state.pop("legacy_result", None)
    st.session_state.pop("heal_result", None)
    st.session_state["_active_scenario"] = scenario

preset = None
custom_html = ""
custom_image = None
custom_broken_selector = ""
custom_goal = ""
if scenario != "Custom Live URL / Screenshot Upload":
    preset_key = next(key for key, label in PRESETS.items() if label == scenario)
    preset = build_preset(preset_key)
    html_dom, screenshot = preset.html, preset.image
    broken_selector, goal = preset.broken_selector, preset.goal
else:
    st.markdown("### Custom webpage input")
    left_input, right_input = st.columns(2)
    with left_input:
        source_mode = st.radio("HTML source", ("Paste HTML", "Fetch URL", "Upload HTML file"), horizontal=True)
        if source_mode == "Paste HTML":
            custom_html = st.text_area("Mutated HTML DOM", height=180, placeholder="Paste the updated page HTML…")
        elif source_mode == "Fetch URL":
            url = st.text_input("Page URL", placeholder="https://example.com/catalog")
            if st.button("Fetch webpage HTML", disabled=not bool(url)):
                try:
                    response = requests.get(url, timeout=20, headers={"User-Agent": "ScrapeHeal-Gemma/1.0"})
                    response.raise_for_status()
                    st.session_state["_url_snapshot"] = {"url": url, "html": response.text}
                except requests.RequestException as exc:
                    st.session_state.pop("_url_snapshot", None)
                    st.error(f"Could not fetch the page: {exc}")
            snapshot = st.session_state.get("_url_snapshot")
            if snapshot and snapshot["url"] == url:
                custom_html = snapshot["html"]
                st.success(f"Loaded snapshot: {len(custom_html):,} HTML characters")
        else:
            html_file = st.file_uploader("HTML file", type=("html", "htm", "txt"))
            if html_file:
                custom_html = html_file.getvalue().decode("utf-8", errors="replace")
    with right_input:
        image_file = st.file_uploader("Screenshot sent to Gemma 4", type=("png", "jpg", "jpeg"))
        if image_file:
            custom_image = Image.open(image_file).convert("RGB")
        custom_broken_selector = st.text_input("Broken legacy selector", placeholder="table.old-list tr")
        custom_goal = st.text_input("Extraction goal", placeholder="Extract product name, price, and stock")
    html_dom, screenshot = custom_html, custom_image
    broken_selector, goal = custom_broken_selector, custom_goal

input_fingerprint = hashlib.sha256(
    html_dom.encode("utf-8")
    + (screenshot.tobytes() if screenshot is not None else b"")
    + json.dumps([broken_selector, goal, model_id, thinking_level, api_key,
                  screenshot.size if screenshot is not None else None]).encode()
).hexdigest()
if st.session_state.get("_input_fingerprint") != input_fingerprint:
    st.session_state.pop("legacy_result", None)
    st.session_state.pop("heal_result", None)
    st.session_state["_input_fingerprint"] = input_fingerprint

col_left, col_right = st.columns([1.05, 0.95], gap="large")
with col_left:
    st.markdown("### 1. Target webpage viewport & mutated DOM")
    if screenshot is not None:
        st.image(screenshot, width="stretch", caption="Visual input passed to Gemma 4 Vision")
    else:
        st.info("Choose a preset or upload a webpage screenshot to start.")
    if broken_selector:
        st.markdown(f"**Legacy selector**  \n`{broken_selector}`")
    if goal:
        st.markdown(f"**Extraction goal**  \n{goal}")
    with st.expander("Inspect raw mutated HTML DOM"):
        st.code(html_dom or "No HTML loaded yet.", language="html")

with col_right:
    st.markdown("### 2. Self-healing pipeline & verification")
    run_legacy = st.button("🚨 Step 1: Run Legacy Scraper (Test Selector)", width="stretch")
    if run_legacy:
        if not html_dom or not broken_selector:
            st.warning("Load HTML and enter the broken selector first.")
        else:
            legacy = verify_broken_selector(html_dom, broken_selector)
            st.session_state["legacy_result"] = legacy
    legacy_result = st.session_state.get("legacy_result")
    if legacy_result:
        if legacy_result["matched_count"] == 0:
            error = legacy_result["error"] or "0 elements matched"
            st.markdown(
                f"<div class='redtrace'>SelectorError: 0 elements matched <code>{broken_selector}</code> in current DOM<br>{error}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.success(f"Legacy selector unexpectedly matched {legacy_result['matched_count']} elements.")

    run_heal = st.button("✨ Step 2: Auto-Heal with Gemma 4 Multimodal", type="primary", width="stretch")
    if run_heal:
        if not html_dom or screenshot is None or not broken_selector or not goal:
            st.warning("Provide HTML, screenshot, broken selector, and extraction goal.")
        elif not api_key and preset is None:
            st.error("Custom pages need GEMINI_API_KEY. Offline demo mode is available for built-in scenarios.")
        else:
            try:
                hint = None
                if preset:
                    hint = {
                        "row_selector": preset.row_selector,
                        "field_selectors": preset.field_selectors,
                        "records": preset.records,
                        "xpath": preset.xpath,
                    }
                with st.spinner("Gemma 4 is comparing the screenshot and DOM; BeautifulSoup will verify every row…"):
                    result = heal_scraper_with_gemma4(
                        html_dom,
                        screenshot,
                        broken_selector,
                        goal,
                        model_id=model_id,
                        thinking_level=thinking_level,
                        api_key=api_key or None,
                        offline_mock=not bool(api_key),
                        preset_hint=hint,
                    )
                st.session_state["heal_result"] = result
            except Exception as exc:
                st.error(f"Healing failed: {exc}")

    result = st.session_state.get("heal_result")
    if result:
        ver = result["verification"]
        origin = "Offline demo fallback" if result.get("offline_mock") or result.get("offline_fallback") else "Gemma 4 live inference"
        if result.get("fallback_error"):
            st.warning(f"Gemma 4 was temporarily unavailable; showing verified built-in demo data. {result['fallback_error']}")
        if ver["verified"]:
            st.markdown(
                f"<span class='badge green'>✅ Verified on Live BeautifulSoup DOM: {ver['matched_row_count']} Rows Extracted Deterministically</span>",
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
            st.json(result["verification"]["deterministic_records"])
            st.download_button(
                "Download verified records as JSON",
                data=json.dumps(result["verification"]["deterministic_records"], ensure_ascii=False, indent=2),
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
            st.caption("Verification: " + ("passed against local DOM" if ver["verified"] else "not verified"))
        with tabs[3]:
            skill_path = ROOT / "scrape-heal" / "SKILL.md"
            st.markdown(skill_path.read_text(encoding="utf-8"))
            st.code("python scrape-heal/scripts/heal_scraper.py --preset football_league --offline-mock", language="bash")
            st.markdown("**Pipeline**")
            st.markdown("```mermaid\n" + result.get("mermaid_diagram", "") + "\n```")
