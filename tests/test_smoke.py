from pathlib import Path
import json
import sys
import re
import unittest
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
        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": ""}):
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
        skill_path = ROOT / "scrape-heal" / "SKILL.md"
        content = skill_path.read_text(encoding="utf-8")
        frontmatter = content.split("---", 2)[1]
        description = next(line.removeprefix("description: ") for line in frontmatter.splitlines() if line.startswith("description: "))
        compatibility = next(line.removeprefix("compatibility: ") for line in frontmatter.splitlines() if line.startswith("compatibility: "))

        self.assertEqual(skill_path.parent.name, "scrape-heal")
        self.assertRegex("scrape-heal", re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$"))
        self.assertIn("name: scrape-heal", frontmatter)
        self.assertIn("license: Apache-2.0", frontmatter)
        self.assertIn('version: "1.0.0"', frontmatter)
        self.assertIn("author:", frontmatter)
        self.assertIn("open_weight_models:", frontmatter)
        self.assertIn("model_license: Apache-2.0", frontmatter)
        self.assertLessEqual(len(description), 1024)
        self.assertLessEqual(len(compatibility), 500)
        self.assertEqual(ALLOWED_MODELS, ("gemma-4-26b-a4b-it", "gemma-4-31b-it"))
        self.assertIn("--preset", content)
        self.assertIn("--offline-mock", content)
        self.assertIn("references/REFERENCE.md", content)


class DashboardRegressionTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict("os.environ", {"GEMINI_API_KEY": ""})
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
        next(button for button in app.button if "Step 2:" in button.label).click().run()
        self.assertTrue(app.session_state["heal_result"]["verified_on_dom"])
        next(radio for radio in app.radio if radio.label == "Gemma 4 thinking level").set_value("minimal").run()
        self.assertFalse(app.exception)
        self.assertNotIn("heal_result", app.session_state)


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

    def test_mock_cache_does_not_replace_live_inference(self):
        html = '<article class="item"><b>A</b></article>'
        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": ""}):
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
        self.assertEqual(options.timeout, 45000)

    def test_empty_rows_are_not_reported_as_verified_extraction(self):
        result = verify_healed_selectors('<div class="item"><b>A</b></div><div class="item"></div>', ".item", {"name": "b"})
        self.assertFalse(result["verified"])
        self.assertEqual(result["matched_row_count"], 2)
        self.assertIn("1", result["error"])


if __name__ == "__main__":
    unittest.main()
