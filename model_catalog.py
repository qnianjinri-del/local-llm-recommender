DEPLOY_CATALOG = [
    {
        "family": "qwen3.5",
        "match_keywords": ["qwen3.5", "qwen-3.5"],
        "trusted_authors": ["Qwen"],
        "deploy_options": [
            {
                "id": "qwen3.5:0.8b",
                "display_name": "Qwen3.5 0.8B",
                "category": "general",
                "min_ram_gb": 8,
                "min_vram_gb": 0,
                "download_size_gb": 1.0,
                "notes": "超轻量，适合先跑通流程"
            }
        ]
    },
    {
        "family": "qwen2.5",
        "match_keywords": ["qwen2.5", "qwen-2.5"],
        "trusted_authors": ["Qwen"],
        "deploy_options": [
            {
                "id": "qwen2.5:3b",
                "display_name": "Qwen2.5 3B",
                "category": "general",
                "min_ram_gb": 16,
                "min_vram_gb": 0,
                "download_size_gb": 1.9,
                "notes": "轻量中文模型，适合无独显或低配机器"
            },
            {
                "id": "qwen2.5:7b",
                "display_name": "Qwen2.5 7B",
                "category": "general",
                "min_ram_gb": 24,
                "min_vram_gb": 8,
                "download_size_gb": 4.7,
                "notes": "主流档位，更适合有独显的机器"
            }
        ]
    },
    {
        "family": "qwen2.5-coder",
        "match_keywords": ["qwen2.5-coder", "qwen-2.5-coder"],
        "trusted_authors": ["Qwen"],
        "deploy_options": [
            {
                "id": "qwen2.5-coder:7b",
                "display_name": "Qwen2.5 Coder 7B",
                "category": "code",
                "min_ram_gb": 24,
                "min_vram_gb": 8,
                "download_size_gb": 4.7,
                "notes": "偏编程场景"
            }
        ]
    }
]