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
                self.text = (
                    '{"healed_row_css_selector": '
                    + __import__("json").dumps(selector)
                    + ', "healed_field_selectors": {"club": "[data-field=club]"}, "healed_xpath": "//div"}'
                )

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


if __name__ == "__main__":
    unittest.main()
