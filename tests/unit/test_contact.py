import copy
import json
import os
import time
import unittest

from lowpoly_kit.core.buildplan import attach, contact, prompt, reconcile, validate

FIX = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures", "plans")
S = "/tmp"


def load(name):
    with open(os.path.join(FIX, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


class Contact(unittest.TestCase):
    def test_fixtures_have_no_floating_parts(self):
        for name in ("barrel", "terminal", "chair", "tuna"):
            plan, errors = validate.validate(load(name))
            self.assertEqual(errors, [], name)
            start = time.time()
            self.assertEqual(contact.floating_parts(attach.resolve(plan)), [], name)
            self.assertLess(time.time() - start, 5.0, name)

    def test_band_wrapped_around_body_counts_as_contact(self):
        # No vertex of the band is inside the body and vice versa; edges cross faces.
        res = {r.id: r for r in attach.resolve(load("barrel"))}
        self.assertTrue(contact.in_contact(contact.world_mesh(res["upper_band"]), contact.world_mesh(res["body"])))

    def test_floating_fin_is_reported_with_pointer(self):
        p = load("tuna")
        fin = [q for q in p["parts"] if q["id"] == "pectoral_fin"][0]
        fin["attachment"]["normal_offset"] = 0.05
        fin["attachment"]["rotation"] = [0, 0, 0]
        text = json.dumps(p, indent=2)
        r = reconcile.reconcile(text, "paste", "PR_Tuna", [], {})
        self.assertEqual(r.errors, [])
        found = {(w.params["id"], w.pointer) for w in r.warnings}
        idx = [q["id"] for q in p["parts"]].index("pectoral_fin")
        self.assertIn(("pectoral_fin", f"/parts/{idx}/attachment"), found)
        self.assertIn(("pectoral_fin_mirror", f"/parts/{idx}/attachment"), found)
        self.assertTrue(all(w.line > 1 for w in r.warnings))

    def test_positive_normal_offset_warned_even_when_touching(self):
        p = load("tuna")
        fin = [q for q in p["parts"] if q["id"] == "pectoral_fin"][0]
        fin["attachment"]["normal_offset"] = 0.035
        fin["attachment"]["rotation"] = [15, -31, 0]
        fin["size"] = [0.15, 0.006, 0.035]
        r = reconcile.reconcile(json.dumps(p, indent=2), "paste", "PR_Tuna", [], {})
        self.assertIn("plan_positive_normal_offset", [w.code for w in r.warnings])

    def test_warning_prompt_header(self):
        text = prompt.build_error_prompt([("msg", "/parts/7/attachment", 10, 3)], "{}", rejected=False)
        self.assertIn("dựng được nhưng", text)

    def test_notes(self):
        text = prompt.build_prompt("PR_Boat", validate.schema_text(), [], [], notes="mạn cao 2.65 m; cabin ở mũi")
        self.assertIn("- mạn cao 2.65 m\n- cabin ở mũi", text)
        self.assertIn("- (không có)", prompt.build_prompt("PR_Boat", validate.schema_text(), [], []))
        for needle in ("hull", '"top"'):
            self.assertIn(needle, text)

    def test_prompt_explains_surface_frame(self):
        text = prompt.build_prompt("PR_Tuna", validate.schema_text(), [], [])
        self.assertIn("tâm đáy", text)
        self.assertIn("normal_offset", text)


if __name__ == "__main__":
    unittest.main()
