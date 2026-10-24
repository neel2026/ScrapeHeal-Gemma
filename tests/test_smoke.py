from pathlib import Path
import json
import sys
import re
import unittest
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scrape-heal"))

from scripts.heal_scraper import (
    ALLOWED_MODELS,
    clean_html_dom,
    heal_scraper_with_gemma4,
    verify_broken_selector,
    verify_healed_selectors,
)
from scripts.presets import PRESETS, build_preset
from scripts import heal_scraper as engine


class SmokeTests(unittest.TestCase):
    def test_presets_have_images_and_mutated_html(self):
        for preset_name in ("football_league", "cloud_gpu", "industrial_b2b"):
            with self.subTest(preset=preset_name):
                preset = build_preset(preset_name)
                self.assertIn(preset_name, PRESETS)
                self.assertGreaterEqual(preset.image.size[0], 800)
                self.assertGreaterEqual(preset.image.size[1], 500)
                self.assertTrue(preset.html)
                self.assertEqual(
                    verify_broken_selector(preset.html, preset.broken_selector)["matched_count"], 0
                )
                verified = verify_healed_selectors(
                    preset.html, preset.row_selector, preset.field_selectors
                )
                self.assertTrue(verified["verified"])
                self.assertEqual(verified["matched_row_count"], len(preset.records))
                self.assertEqual(verified["deterministic_records"], preset.records)

    def test_dom_cleaner_removes_non_content_and_comments(self):
        cleaned = clean_html_dom(
            "<main><p>Keep</p><script>discard()</script><style>.x{}</style>"
            "<!-- secret --><svg><path/></svg><noscript>fallback</noscript></main>"
        )
        self.assertIn("Keep", cleaned)
        for fragment in ("discard", ".x{}", "secret", "<svg", "fallback"):
            self.assertNotIn(fragment, cleaned)

    def test_broken_selector_errors_and_dom_limit_are_reported(self):
        result = verify_broken_selector("<p>one</p>", "[")
        self.assertEqual(result["matched_count"], 0)
        self.assertTrue(result["error"])
        self.assertEqual(clean_html_dom("<p>abcdef</p>", max_chars=4), "<p>a")

    def test_model_allowlist_and_offline_preset_verification(self):
        preset = build_preset("cloud_gpu")
        hint = {
            "row_selector": preset.row_selector,
            "field_selectors": preset.field_selectors,
            "records": preset.records,
            "xpath": preset.xpath,
        }
        with mock.patch.dict("os.environ", {
            "GEMMA_API_KEY_1": "", "GEMMA_API_KEY_2": "",
        }):
            result = heal_scraper_with_gemma4(
                preset.html,
                preset.image,
                preset.broken_selector,
                preset.goal,
                offline_mock=True,
                preset_hint=hint,
            )
        self.assertIn(result["model"], ALLOWED_MODELS)
        self.assertTrue(result["verified_on_dom"])
        self.assertEqual(result["verification"]["matched_row_count"], 4)
        self.assertIn("field_selectors", result["patched_python_code"])
        with self.assertRaises(ValueError):
            heal_scraper_with_gemma4(preset.html, preset.image, "x", "y", model_id="unsupported-model")

    def test_explicit_offline_demo_stays_deterministic_with_live_keys_configured(self):
        preset = build_preset("football_league")
        hint = {
            "row_selector": preset.row_selector,
            "field_selectors": preset.field_selectors,
            "records": preset.records,
            "xpath": preset.xpath,
        }
        with mock.patch.dict("os.environ", {
            "GEMMA_API_KEY_1": "test-primary",
            "GEMMA_API_KEY_2": "test-backup",
        }):
            result = heal_scraper_with_gemma4(
                preset.html, preset.image, preset.broken_selector, preset.goal,
                offline_mock=True, preset_hint=hint,
            )
        self.assertTrue(result["offline_mock"])
        self.assertTrue(result["verified_on_dom"])

    def test_failed_selector_gets_one_self_correction_call(self):
        preset = build_preset("football_league")

        class Response:
            def __init__(self, selector):
                proposal = EngineRegressionTests().proposal(selector)
                proposal["healed_field_selectors"] = {"club": "[data-field=club]"}
                self.text = json.dumps(proposal)

        class Models:
            def __init__(self):
                self.responses = iter((Response(".missing"), Response(preset.row_selector)))
                self.calls = 0

            def generate_content(self, **kwargs):
                self.calls += 1
                return next(self.responses)

        class Client:
            def __init__(self):
                self.models = Models()

        client = Client()
        result = heal_scraper_with_gemma4(
            preset.html,
            preset.image,
            preset.broken_selector,
            preset.goal,
            client=client,
        )
        self.assertTrue(result["verified_on_dom"])
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(client.models.calls, 2)

    def test_skill_frontmatter_matches_folder_and_required_metadata(self):
        import yaml

        skill_path = ROOT / "scrape-heal" / "SKILL.md"
        content = skill_path.read_text(encoding="utf-8")
        self.assertTrue(content.startswith("---\n"))
        parts = content.split("---", 2)
        self.assertEqual(len(parts), 3)
        frontmatter = yaml.safe_load(parts[1])
        self.assertIsInstance(frontmatter, dict)
        name = frontmatter["name"]
        self.assertEqual(name, skill_path.parent.name)
        self.assertRegex(name, re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$"))
        self.assertLessEqual(len(name), 64)
        self.assertTrue(set(frontmatter) <= {"name", "description", "license", "compatibility", "metadata", "allowed-tools"})
        for field, limit in (("description", 1024), ("compatibility", 500)):
            self.assertIsInstance(frontmatter[field], str)
            self.assertTrue(frontmatter[field].strip())
            self.assertLessEqual(len(frontmatter[field]), limit)
        self.assertEqual(frontmatter["license"], "Apache-2.0")
        metadata = frontmatter["metadata"]
        self.assertIsInstance(metadata, dict)
        self.assertTrue(all(isinstance(key, str) and isinstance(value, str) for key, value in metadata.items()))
        self.assertTrue(metadata["author"])
        self.assertEqual(metadata["version"], "1.0.0")
        self.assertEqual(metadata["model_license"], "Apache-2.0")
        self.assertEqual(metadata["open_weight_models"], ", ".join(ALLOWED_MODELS))
        self.assertIn("--preset", content)
        self.assertIn("--offline-mock", content)
        self.assertIn("references/REFERENCE.md", content)


class DashboardRegressionTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict("os.environ", {
            "GEMMA_API_KEY_1": "",
            "GEMMA_API_KEY_2": "",
        })
        patcher.start()
        self.addCleanup(patcher.stop)
        engine._RESPONSE_CACHE.clear()
        engine._REQUEST_TIMESTAMPS.clear()

    def dashboard(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
        self.assertFalse(app.exception)
        return app

    def test_changed_settings_clear_previous_verification(self):
        app = self.dashboard()
        next(button for button in app.button if button.label == "Run Demo: broken selector → repaired selector").click().run()
        self.assertTrue(app.session_state["heal_result"]["verified_on_dom"])
        next(radio for radio in app.radio if radio.label == "Gemma 4 thinking level").set_value("minimal").run()
        self.assertFalse(app.exception)
        self.assertNotIn("heal_result", app.session_state)

    def test_demo_button_runs_broken_selector_and_repair_together(self):
        app = self.dashboard()
        next(button for button in app.button if button.label == "Run Demo: broken selector → repaired selector").click().run()
        self.assertEqual(app.session_state["legacy_result"]["matched_count"], 0)
        self.assertTrue(app.session_state["heal_result"]["verified_on_dom"])
        self.assertTrue(app.session_state["heal_result"]["offline_mock"])
        self.assertEqual(app.session_state["heal_result"]["verification"]["matched_row_count"], 5)

    def test_live_mode_exposes_books_to_scrape_inputs(self):
        app = self.dashboard()
        next(radio for radio in app.radio if radio.label == "Run mode").set_value("Live: Books to Scrape").run()
        self.assertTrue(any(x.label == "Screenshot of Books to Scrape" for x in app.file_uploader))
        self.assertTrue(any(x.label == "Broken legacy selector" for x in app.text_input))
        self.assertTrue(any(button.label == "Run Live: fetch Books to Scrape → heal with Gemma" for button in app.button))
        self.assertFalse(app.exception)

    def test_live_books_button_fetches_html_and_runs_gemma_without_demo_fallback(self):
        from io import BytesIO

        from streamlit.testing.v1 import AppTest

        html = """<html><title>Books to Scrape</title><article class="product_pod">
        <h3><a title="A Light in the Attic">A Light in the ...</a></h3><p class="price_color">£51.77</p>
        <p class="availability">In stock</p></article></html>"""
        response = SimpleNamespace(text=html, raise_for_status=lambda: None, url="https://books.toscrape.com/")
        proposal = {
            "visual_analysis": "A single product card is visible.",
            "dom_mutation_diagnosis": "The old table selector no longer matches the card layout.",
            "reasoning_summary": "The repeated product card maps to one book record.",
            "healed_row_css_selector": "article.product_pod",
            "healed_field_selectors": {"title": "h3 a::attr(title)", "price": ".price_color", "availability": ".availability"},
            "healed_xpath": "//article[contains(@class, 'product_pod')]",
            "confidence_score": 95,
            "visual_extracted_data": [{"title": "A Light in the Attic", "price": "£51.77", "availability": "In stock"}],
            "patched_python_code": "print('books')",
            "mermaid_diagram": "flowchart LR\n A[Books] --> B[Verified]",
        }
        client = mock.Mock()
        client.models.generate_content.return_value = SimpleNamespace(text=json.dumps(proposal))
        original_heal = engine.heal_scraper_with_gemma4

        def live_heal(*args, **kwargs):
            self.assertFalse(kwargs["offline_mock"])
            self.assertIsNone(kwargs["preset_hint"])
            return original_heal(*args, client=client, **kwargs)

        screenshot_buffer = BytesIO()
        build_preset("football_league").image.save(screenshot_buffer, format="PNG")
        with mock.patch.dict("os.environ", {"GEMMA_API_KEY_1": "test-key-one"}), \
             mock.patch("scripts.live_examples.requests.get", return_value=response) as get, \
             mock.patch("scripts.heal_scraper.heal_scraper_with_gemma4", side_effect=live_heal):
            app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
            next(radio for radio in app.radio if radio.label == "Run mode").set_value("Live: Books to Scrape").run()
            next(item for item in app.file_uploader if item.label == "Screenshot of Books to Scrape").upload(
                "books.png", screenshot_buffer.getvalue(), "image/png"
            ).run()
            next(button for button in app.button if button.label == "Run Live: fetch Books to Scrape → heal with Gemma").click().run()

        self.assertFalse(app.exception)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(client.models.generate_content.call_count, 1)
        self.assertEqual(app.session_state["legacy_result"]["matched_count"], 0)
        live_result = app.session_state["heal_result"]
        self.assertFalse(live_result["offline_mock"])
        self.assertFalse(live_result["offline_fallback"])
        self.assertEqual(live_result["verification"]["deterministic_records"], [
            {"title": "A Light in the Attic", "price": "£51.77", "availability": "In stock"}
        ])
        self.assertIn("def extract_field", live_result["patched_python_code"])

    def test_api_key_is_read_from_environment_not_streamlit_input(self):
        app = self.dashboard()
        self.assertNotIn("Gemma API Key", [widget.label for widget in app.text_input])


class EngineRegressionTests(unittest.TestCase):
    def setUp(self):
        engine._RESPONSE_CACHE.clear()
        engine._REQUEST_TIMESTAMPS.clear()
        self.image = build_preset("cloud_gpu").image

    def proposal(self, row_selector=".item"):
        return {
            "visual_analysis": "Repeated item cards.",
            "dom_mutation_diagnosis": "Legacy table replaced by cards.",
            "reasoning_summary": "The item cards correspond to repeated DOM containers.",
            "healed_row_css_selector": row_selector,
            "healed_field_selectors": {"name": "b"},
            "healed_xpath": "//article",
            "confidence_score": 90,
            "visual_extracted_data": [{"name": "A"}],
            "patched_python_code": "print('example')",
            "mermaid_diagram": "flowchart LR\n A[DOM] --> B[Records]",
        }

    def client_for(self, *responses):
        client = mock.Mock()
        client.models.generate_content.side_effect = [
            response if isinstance(response, Exception) else SimpleNamespace(text=json.dumps(response))
            for response in responses
        ]
        return client

    def test_verification_uses_full_dom_after_prompt_truncation(self):
        html = '<article class="item"><b>A</b></article><p>' + "x" * 16000 + '</p><article class="item"><b>B</b></article>'
        result = heal_scraper_with_gemma4(
            html, self.image, ".old", "Extract all names", client=self.client_for(self.proposal())
        )
        self.assertTrue(result["verified_on_dom"])
        self.assertEqual(result["verification"]["deterministic_records"], [{"name": "A"}, {"name": "B"}])

    def test_numbered_api_keys_are_loaded_from_environment_in_order(self):
        with mock.patch.dict("os.environ", {
            "GEMMA_API_KEY_1": "first-test-key",
            "GEMMA_API_KEY_2": "second-test-key",
        }):
            self.assertEqual(engine.configured_api_keys(), ["first-test-key", "second-test-key"])
        with mock.patch.dict("os.environ", {
            "GEMMA_API_KEY_1": "",
            "GEMMA_API_KEY_2": "second-test-key",
        }):
            self.assertEqual(engine.configured_api_keys(), ["second-test-key"])

    def test_failed_primary_key_retries_with_backup_key(self):
        html = '<article class="item"><b>A</b></article>'
        primary_client = self.client_for(ConnectionError("primary unavailable"))
        backup_client = self.client_for(self.proposal())
        with mock.patch.dict("os.environ", {
            "GEMMA_API_KEY_1": "first-test-key",
            "GEMMA_API_KEY_2": "second-test-key",
        }), mock.patch.object(
            engine.genai, "Client", side_effect=[primary_client, backup_client]
        ) as create_client:
            result = heal_scraper_with_gemma4(
                html, self.image, ".old", "Extract names"
            )

        self.assertTrue(result["verified_on_dom"])
        self.assertEqual(result["api_key_failovers"], 1)
        self.assertEqual(create_client.call_count, 2)
        self.assertEqual(primary_client.models.generate_content.call_count, 1)
        self.assertEqual(backup_client.models.generate_content.call_count, 1)

    def test_mock_cache_does_not_replace_live_inference(self):
        html = '<article class="item"><b>A</b></article>'
        with mock.patch.dict("os.environ", {
            "GEMMA_API_KEY_1": "", "GEMMA_API_KEY_2": "",
        }):
            heal_scraper_with_gemma4(html, self.image, ".old", "names", offline_mock=True, mock_result=self.proposal())
            client = self.client_for(self.proposal())
            result = heal_scraper_with_gemma4(html, self.image, ".old", "names", client=client)
        self.assertFalse(result["offline_mock"])
        self.assertEqual(client.models.generate_content.call_count, 1)

    def test_temporary_failure_can_recover_on_next_live_attempt(self):
        html = '<article class="item"><b>A</b></article>'
        client = self.client_for(ConnectionError("temporary outage"), self.proposal())
        hint = {"row_selector": ".item", "field_selectors": {"name": "b"}}
        first = heal_scraper_with_gemma4(html, self.image, ".old", "names", client=client, preset_hint=hint)
        second = heal_scraper_with_gemma4(html, self.image, ".old", "names", client=client, preset_hint=hint)
        self.assertTrue(first["offline_fallback"])
        self.assertFalse(second["offline_fallback"])
        self.assertEqual(client.models.generate_content.call_count, 2)

    def test_cache_distinguishes_changes_beyond_prompt_cutoff(self):
        prefix = "<p>" + "x" * 16000 + "</p>"
        client = self.client_for(self.proposal(), self.proposal())
        for name in ("A", "B"):
            html = prefix + f'<article class="item"><b>{name}</b></article>'
            result = heal_scraper_with_gemma4(html, self.image, ".old", "names", client=client)
            self.assertEqual(result["verification"]["deterministic_records"], [{"name": name}])
        self.assertEqual(client.models.generate_content.call_count, 2)

    def test_model_response_requires_complete_typed_schema(self):
        self.assertEqual(engine._parse_response(json.dumps(self.proposal()))["confidence_score"], 90)
        invalid = self.proposal()
        del invalid["visual_analysis"]
        with self.assertRaises(ValueError):
            engine._parse_response(json.dumps(invalid))
        for field, value in (
            ("confidence_score", "high"), ("confidence_score", None),
            ("confidence_score", 101), ("confidence_score", True),
            ("healed_row_css_selector", None), ("healed_field_selectors", {"name": 2}),
            ("visual_extracted_data", {}), ("patched_python_code", ""),
        ):
            with self.subTest(field=field, value=value):
                invalid = self.proposal()
                invalid[field] = value
                with self.assertRaises(ValueError):
                    engine._parse_response(json.dumps(invalid))

    def test_correction_receives_the_failed_selector_mapping(self):
        failed = self.proposal(".missing-card")
        failed["healed_field_selectors"] = {"name": "b.missing-name"}
        client = self.client_for(failed, self.proposal())
        result = heal_scraper_with_gemma4('<article class="item"><b>A</b></article>', self.image, ".old", "names", client=client)
        self.assertTrue(result["verified_on_dom"])
        self.assertEqual(result["attempts"], 2)
        retry_prompt = client.models.generate_content.call_args_list[1].kwargs["contents"][1]
        self.assertIn(".missing-card", retry_prompt)
        self.assertIn("b.missing-name", retry_prompt)

    def test_api_timeout_is_bounded_and_activates_preset_fallback(self):
        client = self.client_for(TimeoutError("request timed out"))
        hint = {"row_selector": ".item", "field_selectors": {"name": "b"}}
        with mock.patch.object(engine.genai, "Client", return_value=client) as create:
            result = heal_scraper_with_gemma4('<article class="item"><b>A</b></article>', self.image, ".old", "names", api_key="test-placeholder", preset_hint=hint)
        self.assertTrue(result["offline_fallback"])
        self.assertTrue(result["verified_on_dom"])
        options = create.call_args.kwargs.get("http_options")
        self.assertIsNotNone(options)
        self.assertEqual(options.timeout, 120000)

    def test_books_to_scrape_fetch_uses_live_html_and_timeout(self):
        from scripts.live_examples import fetch_books_to_scrape

        html = '<html><title>Books to Scrape</title><article class="product_pod"><h3>Book</h3></article></html>'
        response = SimpleNamespace(text=html, raise_for_status=lambda: None, url="https://books.toscrape.com/")
        with mock.patch("scripts.live_examples.requests.get", return_value=response) as get:
            fetched = fetch_books_to_scrape()

        self.assertEqual(fetched, html)
        self.assertEqual(get.call_args.args[0], "https://books.toscrape.com/")
        self.assertGreaterEqual(get.call_args.kwargs["timeout"], 30)

    def test_books_to_scrape_fetch_rejects_unexpected_page(self):
        from scripts.live_examples import fetch_books_to_scrape

        response = SimpleNamespace(text="<html><title>Login</title></html>", raise_for_status=lambda: None, url="https://books.toscrape.com/")
        with mock.patch("scripts.live_examples.requests.get", return_value=response):
            with self.assertRaisesRegex(ValueError, "did not look like Books to Scrape"):
                fetch_books_to_scrape()

    def test_books_to_scrape_fetch_uses_detected_encoding_for_currency(self):
        import requests

        from scripts.live_examples import fetch_books_to_scrape

        response = requests.Response()
        response.status_code = 200
        response.url = "https://books.toscrape.com/"
        response.encoding = "ISO-8859-1"
        response._content = (
            b'<meta charset="utf-8"><article class="product_pod">'
            b'<p class="price_color">\xc2\xa351.77</p></article>'
        )
        with mock.patch("scripts.live_examples.requests.get", return_value=response):
            fetched = fetch_books_to_scrape()

        self.assertIn("£51.77", fetched)
        self.assertNotIn("Â£51.77", fetched)

    def test_verifier_reads_full_book_title_from_attribute_selector(self):
        html = '<article class="product_pod"><h3><a title="A Full Book Title">A Full Book ...</a></h3></article>'
        result = verify_healed_selectors(html, "article.product_pod", {"title": "h3 a::attr(title)"})

        self.assertTrue(result["verified"])
        self.assertEqual(result["deterministic_records"], [{"title": "A Full Book Title"}])

    def test_generated_patch_script_extracts_full_attribute_values(self):
        html = '<article class="product_pod"><h3><a title="A Full Book Title">A Full Book ...</a></h3></article>'
        code = engine._patched_code("article.product_pod", {"title": "h3 a::attr(title)"})
        captured = StringIO()
        with mock.patch("builtins.open", mock.mock_open(read_data=html)), redirect_stdout(captured):
            exec(compile(code, "<patched scraper>", "exec"), {})

        self.assertEqual(json.loads(captured.getvalue()), [{"title": "A Full Book Title"}])

    def test_empty_rows_are_not_reported_as_verified_extraction(self):
        result = verify_healed_selectors('<div class="item"><b>A</b></div><div class="item"></div>', ".item", {"name": "b"})
        self.assertFalse(result["verified"])
        self.assertEqual(result["matched_row_count"], 2)
        self.assertIn("1", result["error"])


if __name__ == "__main__":
    unittest.main()
