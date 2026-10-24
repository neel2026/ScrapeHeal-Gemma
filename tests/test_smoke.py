from pathlib import Path
import sys
import re
import unittest
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


if __name__ == "__main__":
    unittest.main()
