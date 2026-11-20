import unittest

from lowpoly_kit.core import config
from lowpoly_kit.core.checks import registry

CFG = config.defaults()


class Results(unittest.TestCase):
    def test_grouping_and_counts(self):
        rs = [registry.make("smooth_shading", CFG, {}, "B", [1]),
              registry.make("budget_near", CFG, {}),
              registry.make("color_attr_missing", CFG, {}, "A"),
              registry.make("ngon", CFG, {}, "B", [2])]
        groups = registry.group_by_object(rs)
        self.assertEqual([k for k, _ in groups], [None, "A", "B"])
        self.assertEqual([r.check_id for r in groups[2][1]], ["ngon", "smooth_shading"])
        self.assertEqual(registry.summary_counts(rs), {"ERROR": 1, "WARNING": 2, "INFO": 1})
        self.assertEqual(registry.error_count(rs), 1)

    def test_fix_ids_and_selection_kinds(self):
        for d in registry.CHECKS.values():
            self.assertIn(d.severity, registry.SEVERITY_ORDER)
            self.assertIn(d.select, (None, "OBJECT", "VERT", "EDGE", "FACE"))


if __name__ == "__main__":
    unittest.main()
