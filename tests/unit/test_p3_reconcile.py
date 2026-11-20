import copy
import json
import os
import unittest

from lowpoly_kit.core.buildplan import reconcile as rc

FIX = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures", "plans")


def load(name):
    with open(os.path.join(FIX, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


def kinds(result):
    return [(a.kind, a.key or a.part_id) for a in result.actions if a.kind != "WRITE_TEXT"]


def codes(result):
    return [e.code for e in result.errors]


class FirstBuild(unittest.TestCase):
    def test_creates_parts_and_writes_text(self):
        r = rc.reconcile(json.dumps(load("barrel")), "paste", "PR_Barrel", [], {})
        self.assertEqual(r.errors, [])
        self.assertEqual(kinds(r), [("CREATE", "body"), ("CREATE", "upper_band")])
        self.assertEqual(r.actions[-1].kind, "WRITE_TEXT")

    def test_asset_name_mismatch(self):
        r = rc.reconcile(json.dumps(load("barrel")), "paste", "PR_Crate", [], {})
        self.assertEqual(codes(r), ["plan_asset_name"])

    def test_paste_rejects_managed_fields(self):
        p = load("barrel")
        p["parts"][0]["baked"] = True
        self.assertIn("plan_managed_field", codes(rc.reconcile(json.dumps(p), "paste", "PR_Barrel", [], {})))


def baked_state(plan, part_id, key):
    _, snap = rc.bake_part(plan, part_id)
    return rc.ObjState(key, part_id, "uid-" + key, snap), snap


class Rebuild(unittest.TestCase):
    def setUp(self):
        self.plan = load("barrel")

    def test_update_delete_rename(self):
        objs = [rc.ObjState("Body", "body", "u1", None), rc.ObjState("Band", "upper_band", "u2", None)]
        p = copy.deepcopy(self.plan)
        p["parts"][1]["id"] = "top_band"
        r = rc.reconcile(json.dumps(p), "editor", "PR_Barrel", objs, {"body": "u1", "upper_band": "u2"})
        self.assertEqual(r.errors, [])
        k = kinds(r)
        self.assertIn(("REPLACE_MESH", "Body"), k)
        self.assertIn(("CREATE", "top_band"), k)
        self.assertIn(("DELETE", "Band"), k)

    def test_baked_part_kept_when_pasting_without_bake_fields(self):
        body, snap = baked_state(self.plan, "body", "Body")
        p = copy.deepcopy(self.plan)
        p["parts"][0]["profile_z_radius"] = [[0.0, 0.5], [0.45, 0.6], [0.90, 0.5]]
        for mode in ("paste", "editor"):
            r = rc.reconcile(json.dumps(p), mode, "PR_Barrel", [body], {"body": "uid-Body"})
            self.assertEqual(r.errors, [], mode)
            self.assertNotIn(("REPLACE_MESH", "Body"), kinds(r))
            merged_body = r.plan["parts"][0]
            self.assertTrue(merged_body["baked"])
            self.assertEqual(merged_body["baked_params"], snap)
            self.assertIn("plan_ignored_baked_change", [n[0] for n in r.notes])
            band = {x.id: x for x in r.resolved}["upper_band"]
            self.assertAlmostEqual(band.computed["radius"], 0.297778, places=5)

    def test_edited_baked_params_and_baked_without_object(self):
        body, snap = baked_state(self.plan, "body", "Body")
        p = copy.deepcopy(self.plan)
        p["parts"][0]["baked"] = True
        p["parts"][0]["baked_params"] = dict(snap, op="lathe_profile", params={"segments": 12})
        r = rc.reconcile(json.dumps(p), "editor", "PR_Barrel", [body], {})
        self.assertIn("plan_baked_mismatch", codes(r))
        p2 = copy.deepcopy(self.plan)
        p2["parts"][1]["baked"] = True
        self.assertIn("plan_baked_without_object", codes(rc.reconcile(json.dumps(p2), "editor", "PR_Barrel", [], {})))

    def test_baked_lathe_body_with_terminal_keyboard(self):
        body, _ = baked_state(self.plan, "body", "Body")
        t = load("terminal")
        t["asset_name"] = "PR_Barrel"
        r = rc.reconcile(json.dumps(t), "paste", "PR_Barrel", [body], {"body": "uid-Body"})
        self.assertIn("plan_rule_parent_type", codes(r))
        self.assertEqual(r.actions, [])

    def test_deleting_baked_part_strips_it(self):
        body, _ = baked_state(self.plan, "body", "Body")
        p = {"schema_version": 1, "asset_name": "PR_Barrel", "units": "m",
             "parts": [{"id": "lid", "op": "add_primitive", "shape": "box", "size": [0.5, 0.5, 0.05]}]}
        r = rc.reconcile(json.dumps(p), "paste", "PR_Barrel", [body], {})
        self.assertIn(("STRIP", "Body"), kinds(r))
        self.assertNotIn(("DELETE", "Body"), kinds(r))

    def test_duplicates(self):
        objs = [rc.ObjState("Body", "body", "u1", None), rc.ObjState("Body.001", "body", "u9", None)]
        r = rc.reconcile(json.dumps(self.plan), "editor", "PR_Barrel", objs, {"body": "u1"})
        self.assertEqual(r.errors, [])
        self.assertIn(("STRIP", "Body.001"), kinds(r))
        self.assertIn(("REPLACE_MESH", "Body"), kinds(r))
        # Ambiguous: no registry entry -> stop before changing anything.
        r = rc.reconcile(json.dumps(self.plan), "editor", "PR_Barrel", objs, {})
        self.assertEqual(codes(r), ["plan_duplicate_objects"])
        self.assertEqual(r.actions, [])

    def test_invalid_draft_keeps_everything(self):
        r = rc.reconcile('{"schema_version": 1,', "editor", "PR_Barrel", [rc.ObjState("Body", "body", "u1", None)], {})
        self.assertEqual(codes(r), ["plan_json_error"])
        self.assertEqual(r.actions, [])


if __name__ == "__main__":
    unittest.main()
