import os
import struct
import unittest

from lowpoly_kit.core import export_post, export_settings, glb, paths, vecmath as vm


def make_gltf():
    positions = [(-0.5, 0, -0.5), (0.5, 0, -0.5), (0.5, 1, 0.5)]
    pos_bytes = b"".join(struct.pack("<fff", *p) for p in positions)
    # Interleave-free colour buffer with a 4-byte stride holding u8 RGBA.
    col_bytes = bytes([255, 0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 255])
    binary = pos_bytes + col_bytes
    gltf = {
        "asset": {"version": "2.0"},
        "scenes": [{"nodes": [0]}],
        "nodes": [
            {"name": "PR_Tủ.001", "translation": [10, 2, 5], "children": [1, 2]},
            {"name": "Thân.001", "mesh": 0, "translation": [0, 0.4, 0]},
            {"name": "Cửa.001", "mesh": 0, "translation": [0.3, 0.5, -0.2], "rotation": [0, 0.7071068, 0, 0.7071068],
             "scale": [-1, 1, 1]},
        ],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "COLOR_0": 1}}]}],
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 36},
                        {"buffer": 0, "byteOffset": 36, "byteLength": 12, "byteStride": 4}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3", "min": [-0.5, 0, -0.5], "max": [0.5, 1, 0.5]},
            {"bufferView": 1, "componentType": 5121, "normalized": True, "count": 3, "type": "VEC4"},
        ],
    }
    return gltf, binary


class Glb(unittest.TestCase):
    def test_roundtrip_with_utf8_names(self):
        gltf, binary = make_gltf()
        data = glb.write(gltf, binary)
        self.assertEqual(len(data) % 4, 0)
        back, b2 = glb.read(data)
        self.assertEqual(back["nodes"][1]["name"], "Thân.001")
        self.assertEqual(b2[:len(binary)], binary)

    def test_accessors_and_summary(self):
        gltf, binary = make_gltf()
        cols = glb.read_accessor(gltf, binary, 1)
        self.assertEqual(cols[0], (1.0, 0.0, 0.0, 1.0))
        info = {i["name"]: i for i in glb.summary(gltf, binary)}
        self.assertIn("COLOR_0", info["Thân.001"]["attributes"])
        self.assertLess(info["Cửa.001"]["det"], 0)
        self.assertTrue(vm.close(vm.get_translation(info["Thân.001"]["world"]), (10, 2.4, 5)))

    def test_rejects_garbage(self):
        with self.assertRaises(glb.GlbError):
            glb.read(b"notglb" * 4)


class PostProcess(unittest.TestCase):
    def test_root_to_origin_and_names(self):
        gltf, binary = make_gltf()
        names = {"PR_Tủ.001": "PR_Tủ", "Thân.001": "Thân", "Cửa.001": "Cửa"}
        post = export_post.postprocess(gltf, "PR_Tủ", names, ["PR_Tủ", "Thân", "Cửa"])
        self.assertEqual((post.missing, post.extra), ([], []))
        info = {i["name"]: i for i in glb.summary(post.gltf, binary)}
        self.assertTrue(vm.close(vm.get_translation(info["PR_Tủ"]["world"]), (0, 0, 0)))
        # Children keep their transform relative to the root.
        self.assertTrue(vm.close(vm.get_translation(info["Cửa"]["world"]), (0.3, 0.5, -0.2)))
        self.assertEqual(gltf["nodes"][0]["name"], "PR_Tủ.001")  # input untouched

    def test_detects_extra_and_missing(self):
        gltf, _ = make_gltf()
        post = export_post.postprocess(gltf, "PR_Tủ", {"PR_Tủ.001": "PR_Tủ"}, ["PR_Tủ", "Thân", "HingePivot"])
        self.assertIn("HingePivot", post.missing)
        self.assertIn("Thân.001", post.extra)

    def test_matrix_root(self):
        gltf = {"nodes": [{"name": "R", "matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 4, 5, 6, 1]}]}
        post = export_post.postprocess(gltf, "R", {}, ["R"])
        self.assertEqual(post.gltf["nodes"][0]["matrix"][12:15], [0.0, 0.0, 0.0])


class Settings(unittest.TestCase):
    def test_filter_against_42_like_options(self):
        available = {k: None for k in export_settings.DESIRED}
        available["export_format"] = ["GLB", "GLTF_SEPARATE"]
        available["export_vertex_color"] = ["MATERIAL", "ACTIVE", "NONE"]
        available["export_materials"] = ["EXPORT", "PLACEHOLDER", "NONE"]
        del available["use_active_collection_with_nested"]
        kwargs, dropped, missing = export_settings.filter_options(available)
        self.assertEqual(dropped, ["use_active_collection_with_nested"])
        self.assertEqual(missing, [])
        self.assertEqual(kwargs["export_vertex_color"], "MATERIAL")
        available["export_format"] = ["GLTF_SEPARATE"]
        _, _, missing = export_settings.filter_options(available)
        self.assertEqual(missing, ["export_format"])


class Paths(unittest.TestCase):
    def test_resolution(self):
        p, err = paths.resolve_export_path("//export", "props", "PR_Barrel", "/proj/scenes/barrel.blend")
        self.assertEqual((p, err), (os.path.normpath("/proj/scenes/export/props/PR_Barrel.glb"), None))
        self.assertEqual(paths.resolve_export_path("//export", "props", "PR_Barrel", "")[1], "export_unsaved_blend")
        self.assertEqual(paths.resolve_export_path("export", "", "PR_B", "")[1], "export_unsaved_blend")
        self.assertEqual(paths.resolve_export_path("/abs/out", "", "PR:B", "")[0], os.path.normpath("/abs/out/PR_B.glb"))
        self.assertTrue(paths.temp_path_for("/a/PR_B.glb").endswith(".glb"))


if __name__ == "__main__":
    unittest.main()
