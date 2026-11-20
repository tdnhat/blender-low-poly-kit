import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile

from lowpoly_kit.core.buildplan import prompt

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_builder():
    spec = importlib.util.spec_from_file_location("build_ai_skill", os.path.join(ROOT, "tools", "build_ai_skill.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class AiSkill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.folder, cls.archive = load_builder().build(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_validator(self, plan_path):
        # -I: isolated mode, so nothing from the repository can be imported.
        return subprocess.run([sys.executable, "-I", "scripts/validate_plan.py", plan_path], cwd=self.folder,
                              capture_output=True, text=True)

    def test_skill_md(self):
        with open(os.path.join(self.folder, "SKILL.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertTrue(text.startswith("---\nname: lowpoly-build-plan\ndescription: "))
        self.assertNotIn("{{", text)
        for needle in ("body_surface", "thickness_profile", "validate_plan.py", "−Y"):
            self.assertIn(needle, text)

    def test_zip_layout(self):
        with zipfile.ZipFile(self.archive) as zf:
            names = zf.namelist()
        self.assertIn("lowpoly-build-plan/SKILL.md", names)
        self.assertIn("lowpoly-build-plan/scripts/validate_plan.py", names)
        self.assertIn("lowpoly-build-plan/examples/boat.json", names)
        self.assertFalse(any(n.endswith(".pyc") for n in names))

    def test_examples_validate_ok_in_isolation(self):
        for name in ("barrel", "terminal", "chair", "tuna", "boat"):
            r = self.run_validator(f"examples/{name}.json")
            self.assertEqual(r.returncode, 0, name + r.stdout + r.stderr)
            self.assertIn("OK", r.stdout)

    def test_errors_and_warnings_exit_codes(self):
        with open(os.path.join(self.folder, "examples", "boat.json"), encoding="utf-8") as f:
            plan = json.load(f)
        broken = json.loads(json.dumps(plan))
        broken["parts"][0]["section"] = "box"          # hull params without hull section
        floating = json.loads(json.dumps(plan))
        bar = [q for q in floating["parts"] if q["id"] == "aframe_crossbar"][0]
        bar["attachment"]["position"] = [0, -6.4, 6.5]
        for data, code, needle in ((broken, 1, "plan_hull_params"), (floating, 2, "plan_part_floating")):
            path = os.path.join(self.folder, "case.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            r = self.run_validator("case.json")
            self.assertEqual(r.returncode, code, r.stdout + r.stderr)
            self.assertIn(needle, r.stdout)


class SkillPrompt(unittest.TestCase):
    def test_short_prompt(self):
        text = prompt.build_skill_prompt("PR_Boat", [("TOP", "width", 5.58)], [("TOP", True)], notes="cabin ở mũi")
        self.assertIn("lowpoly-build-plan", text)
        self.assertIn("TOP · Bề rộng (width): 5.5800 m", text)
        self.assertNotIn("$schema", text)
        self.assertNotIn("Duyệt trước", text)
        self.assertIn("Duyệt trước", prompt.build_skill_prompt("PR_Boat", [], [], review=True))


if __name__ == "__main__":
    unittest.main()


class DetailLevel(unittest.TestCase):
    def test_prompts_carry_detail(self):
        from lowpoly_kit.core.buildplan import validate
        full = prompt.build_prompt("PR_Boat", validate.schema_text(), [], [], detail="DETAILED", target_tris=3000)
        self.assertIn("3000 tris", full)
        self.assertNotIn("{{", full)
        skill = prompt.build_skill_prompt("PR_Boat", [], [], detail="DETAILED", target_tris=3000)
        self.assertIn("--target-tris 3000", skill)
        self.assertIn("**Chi tiết**", skill)
        block = prompt.build_skill_prompt("PR_Boat", [], [])
        self.assertIn("**Blockout.**", block)
        self.assertNotIn("--target-tris", block)

    def test_segments_24_32(self):
        from lowpoly_kit.core.buildplan import geometry
        for n in (24, 32):
            g = geometry.cylinder(0.5, 1.0, n)
            self.assertAlmostEqual(max(v[0] for v in g.verts), 0.5)


class TargetTris(AiSkill):
    def test_target_exit_code(self):
        r = self.run_validator("examples/boat.json")
        self.assertEqual(r.returncode, 0)
        r = subprocess.run([sys.executable, "-I", "scripts/validate_plan.py", "examples/boat.json", "--target-tris", "3000"],
                           cwd=self.folder, capture_output=True, text=True)
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertIn("Below target", r.stdout)
        r = subprocess.run([sys.executable, "-I", "scripts/validate_plan.py", "examples/boat.json", "--target-tris", "450"],
                           cwd=self.folder, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)
