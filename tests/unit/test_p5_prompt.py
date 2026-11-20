import json
import unittest

from lowpoly_kit.core.buildplan import prompt, validate


class Prompt(unittest.TestCase):
    def test_prompt_contains_schema_and_measurements(self):
        text = prompt.build_prompt("PR_Barrel", validate.schema_text(),
                                   [("RIGHT", "height", 0.9), ("FRONT", "height", 0.9), ("FRONT", "width", 0.62)])
        self.assertNotIn("{{", text)
        self.assertIn('`asset_name` = "PR_Barrel"', text)
        self.assertIn("FRONT · Bề rộng (width): 0.6200 m", text)
        self.assertLess(text.index("FRONT · Chiều cao"), text.index("RIGHT · Chiều cao"))
        schema_block = text.split("```json\n", 1)[1].rsplit("\n```", 1)[0]
        self.assertEqual(json.loads(schema_block), validate.load_schema())

    def test_no_measurements(self):
        self.assertIn("inferred", prompt.format_measurements([]))


if __name__ == "__main__":
    unittest.main()
