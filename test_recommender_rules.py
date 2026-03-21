import unittest

from recommender import recommend_from_recent_models


class RecommenderRulesTests(unittest.TestCase):
    def setUp(self):
        self.recent_models = [
            {"id": "Qwen/Qwen3.5-0.8B", "family": "qwen3.5", "last_modified": "2026-03-01T00:00:00Z"},
            {"id": "deepseek-ai/DeepSeek-R1", "family": "deepseek-r1", "last_modified": "2026-03-10T00:00:00Z"},
            {"id": "mistralai/Ministral-3", "family": "ministral-3", "last_modified": "2026-02-01T00:00:00Z"},
        ]

    def test_cpu_only_mode_prefers_smaller_qwen_tier(self):
        hardware = {
            "ram_gb": 32,
            "cpu_cores_logical": 16,
            "gpus": [],
        }
        results = recommend_from_recent_models(
            self.recent_models,
            hardware,
            user_preference="balanced",
            sort_mode="overall",
            top_n=8,
        )
        qwen = next(item for item in results if item["family"] == "qwen3.5")
        self.assertEqual(qwen["current_param"], "4B")
        self.assertEqual(qwen["hardware_mode"], "cpu_only")

    def test_gpu_mode_allows_larger_qwen_tier(self):
        hardware = {
            "ram_gb": 32,
            "cpu_cores_logical": 16,
            "gpus": [{"name": "RTX", "vram_gb": 12}],
        }
        results = recommend_from_recent_models(
            self.recent_models,
            hardware,
            user_preference="balanced",
            sort_mode="overall",
            top_n=8,
        )
        qwen = next(item for item in results if item["family"] == "qwen3.5")
        self.assertEqual(qwen["current_param"], "9B")
        self.assertEqual(qwen["hardware_mode"], "gpu")

    def test_lightweight_sort_orders_by_size(self):
        hardware = {
            "ram_gb": 32,
            "cpu_cores_logical": 16,
            "gpus": [],
        }
        results = recommend_from_recent_models(
            self.recent_models,
            hardware,
            user_preference="balanced",
            sort_mode="lightweight",
            top_n=8,
        )
        sizes = [item["download_size_gb"] for item in results]
        self.assertEqual(sizes, sorted(sizes))

    def test_every_result_contains_runtime_fields(self):
        hardware = {
            "ram_gb": 32,
            "cpu_cores_logical": 16,
            "gpus": [],
        }
        results = recommend_from_recent_models(
            self.recent_models,
            hardware,
            user_preference="balanced",
            sort_mode="overall",
            top_n=8,
        )
        self.assertTrue(results)
        first = results[0]
        for key in [
            "family",
            "current_param",
            "score",
            "reason",
            "notes",
            "runtime_feel",
            "runtime_note",
            "sort_mode_used",
        ]:
            self.assertIn(key, first)


if __name__ == "__main__":
    unittest.main()
