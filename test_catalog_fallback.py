import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import online_catalog


class CatalogFallbackTests(unittest.TestCase):
    def test_offline_fallback_models_are_available(self):
        models = online_catalog.build_offline_fallback_models()
        self.assertTrue(models)
        self.assertIn("family", models[0])
        self.assertIn("id", models[0])

    def test_fallback_uses_cache_when_online_fetch_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache_file = cache_dir / "recent_models_cache.json"
            payload = {
                "saved_at": "2026-03-20T00:00:00+00:00",
                "models": [
                    {
                        "id": "Qwen/Qwen3.5-0.8B",
                        "last_modified": "2026-03-19T00:00:00Z",
                        "family": "qwen3.5",
                        "source": "huggingface",
                    }
                ],
            }
            cache_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            with patch.object(online_catalog, "CACHE_DIR", cache_dir), \
                 patch.object(online_catalog, "CACHE_FILE", cache_file), \
                 patch.object(online_catalog, "fetch_recent_supported_models", side_effect=RuntimeError("network down")):
                state = online_catalog.load_recent_supported_models_with_fallback(limit_per_family=3)

        self.assertEqual(state["mode"], "cache")
        self.assertTrue(state["models"])
        self.assertIn("在线获取失败", state["message"])

    def test_fallback_uses_offline_catalog_when_no_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache_file = cache_dir / "recent_models_cache.json"

            with patch.object(online_catalog, "CACHE_DIR", cache_dir), \
                 patch.object(online_catalog, "CACHE_FILE", cache_file), \
                 patch.object(online_catalog, "fetch_recent_supported_models", side_effect=RuntimeError("network down")):
                state = online_catalog.load_recent_supported_models_with_fallback(limit_per_family=3)

        self.assertEqual(state["mode"], "offline")
        self.assertTrue(state["models"])


if __name__ == "__main__":
    unittest.main()
