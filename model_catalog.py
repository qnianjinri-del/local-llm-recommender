from typing import Dict, List


def build_option(
    model_id: str,
    display_name: str,
    param_label: str,
    min_ram_gb: int,
    recommended_vram_gb: int,
    download_size_gb: float,
    notes: str,
    category: str = "general",
) -> Dict:
    return {
        "id": model_id,
        "display_name": display_name,
        "param_label": param_label,
        "category": category,
        "min_ram_gb": min_ram_gb,
        "recommended_vram_gb": recommended_vram_gb,
        "download_size_gb": download_size_gb,
        "notes": notes,
    }


def build_family(
    family: str,
    family_display_name: str,
    match_keywords: List[str],
    trusted_authors: List[str],
    deploy_options: List[Dict],
) -> Dict:
    return {
        "family": family,
        "family_display_name": family_display_name,
        "match_keywords": match_keywords,
        "trusted_authors": trusted_authors,
        "deploy_options": deploy_options,
    }


DEPLOY_CATALOG: List[Dict] = [
    build_family(
        family="qwen3.5",
        family_display_name="Qwen 3.5",
        match_keywords=["qwen3.5", "qwen-3.5"],
        trusted_authors=["Qwen"],
        deploy_options=[
            build_option("qwen3.5:0.8b", "Qwen 3.5 0.8B", "0.8B", 8, 0, 1.0, "非常适合先体验本地模型，启动快。"),
            build_option("qwen3.5:2b", "Qwen 3.5 2B", "2B", 12, 0, 2.7, "轻量但更实用，中文和英文都比较友好。"),
            build_option("qwen3.5:4b", "Qwen 3.5 4B", "4B", 16, 0, 3.4, "对多数日常问答场景比较均衡。"),
            build_option("qwen3.5:9b", "Qwen 3.5 9B", "9B", 24, 8, 6.6, "能力更强，适合内存和显卡更充足的机器。"),
            build_option("qwen3.5:27b", "Qwen 3.5 27B", "27B", 48, 16, 17.0, "偏高配档位，更适合追求效果的用户。"),
            build_option("qwen3.5:35b", "Qwen 3.5 35B", "35B", 64, 24, 24.0, "高配档位，回答质量更强但部署成本高。"),
            build_option("qwen3.5:122b", "Qwen 3.5 122B", "122B", 160, 80, 81.0, "旗舰级档位，通常不适合普通个人电脑。"),
        ],
    ),
    build_family(
        family="qwen2.5",
        family_display_name="Qwen 2.5",
        match_keywords=["qwen2.5", "qwen-2.5"],
        trusted_authors=["Qwen"],
        deploy_options=[
            build_option("qwen2.5:0.5b", "Qwen 2.5 0.5B", "0.5B", 8, 0, 0.7, "极轻量，适合先跑通流程。"),
            build_option("qwen2.5:1.5b", "Qwen 2.5 1.5B", "1.5B", 10, 0, 1.1, "轻量实用，比较适合入门。"),
            build_option("qwen2.5:3b", "Qwen 2.5 3B", "3B", 14, 0, 2.0, "兼顾体积和效果，适合作为常用模型。"),
            build_option("qwen2.5:7b", "Qwen 2.5 7B", "7B", 20, 8, 4.7, "中档通用模型，适合内存较充足的机器。"),
            build_option("qwen2.5:14b", "Qwen 2.5 14B", "14B", 32, 12, 9.0, "更强能力，但更依赖内存和显卡。"),
            build_option("qwen2.5:32b", "Qwen 2.5 32B", "32B", 64, 24, 20.0, "高配档位，不适合大多数普通电脑。"),
            build_option("qwen2.5:72b", "Qwen 2.5 72B", "72B", 128, 48, 41.0, "专业级高负载部署。"),
        ],
    ),
    build_family(
        family="llama3.2",
        family_display_name="Llama 3.2",
        match_keywords=["llama3.2", "llama-3.2"],
        trusted_authors=["meta-llama"],
        deploy_options=[
            build_option("llama3.2:1b", "Llama 3.2 1B", "1B", 8, 0, 1.3, "很适合作为轻量英文通用模型。"),
            build_option("llama3.2:3b", "Llama 3.2 3B", "3B", 12, 0, 2.0, "在体积和效果之间比较平衡。"),
        ],
    ),
    build_family(
        family="llama3.1",
        family_display_name="Llama 3.1",
        match_keywords=["llama3.1", "llama-3.1"],
        trusted_authors=["meta-llama"],
        deploy_options=[
            build_option("llama3.1:8b", "Llama 3.1 8B", "8B", 24, 8, 4.9, "更成熟的通用大模型，适合中高配本地部署。"),
            build_option("llama3.1:70b", "Llama 3.1 70B", "70B", 128, 48, 40.0, "旗舰级高负载部署。"),
        ],
    ),
    build_family(
        family="gemma3",
        family_display_name="Gemma 3",
        match_keywords=["gemma3", "gemma-3"],
        trusted_authors=["google"],
        deploy_options=[
            build_option("gemma3:270m", "Gemma 3 270M", "270M", 8, 0, 0.4, "极小体积，适合快速试跑。"),
            build_option("gemma3:1b", "Gemma 3 1B", "1B", 8, 0, 0.8, "轻量上手快，适合低门槛体验。"),
            build_option("gemma3:4b", "Gemma 3 4B", "4B", 16, 0, 3.3, "适合作为日常问答与摘要的常驻模型。"),
            build_option("gemma3:12b", "Gemma 3 12B", "12B", 28, 10, 8.1, "中高档位，效果更强。"),
            build_option("gemma3:27b", "Gemma 3 27B", "27B", 48, 16, 17.0, "高配档位，适合资源更充足的机器。"),
        ],
    ),
    build_family(
        family="granite4",
        family_display_name="Granite 4",
        match_keywords=["granite4", "granite-4"],
        trusted_authors=["ibm-granite", "ibm"],
        deploy_options=[
            build_option("granite4:350m", "Granite 4 350M", "350M", 8, 0, 0.7, "非常轻量，适合先跑通本地流程。"),
            build_option("granite4:1b", "Granite 4 1B", "1B", 10, 0, 3.3, "工具调用能力不错，但下载体积略大。"),
            build_option("granite4:3b", "Granite 4 3B", "3B", 16, 0, 2.1, "小体积但上下文较长，适合通用助手场景。"),
        ],
    ),
    build_family(
        family="mistral",
        family_display_name="Mistral 7B",
        match_keywords=["mistral", "mistral-7b"],
        trusted_authors=["mistralai"],
        deploy_options=[
            build_option("mistral:7b", "Mistral 7B", "7B", 24, 8, 4.4, "经典 7B 档位，适合中高配本地部署。"),
        ],
    ),
    build_family(
        family="ministral-3",
        family_display_name="Ministral 3",
        match_keywords=["ministral-3", "ministral 3"],
        trusted_authors=["mistralai"],
        deploy_options=[
            build_option("ministral-3:3b", "Ministral 3 3B", "3B", 16, 0, 3.0, "Edge 友好，适合比较新的 Ollama 版本。"),
            build_option("ministral-3:8b", "Ministral 3 8B", "8B", 24, 8, 6.0, "能力和体积更均衡，适合中高配。"),
            build_option("ministral-3:14b", "Ministral 3 14B", "14B", 32, 12, 9.1, "效果更强，但更看重内存和显卡。"),
        ],
    ),
    build_family(
        family="deepseek-r1",
        family_display_name="DeepSeek-R1",
        match_keywords=["deepseek-r1", "deepseek r1"],
        trusted_authors=["deepseek-ai"],
        deploy_options=[
            build_option("deepseek-r1:1.5b", "DeepSeek-R1 1.5B", "1.5B", 10, 0, 1.1, "轻量推理模型，适合先感受 R1 系列。"),
            build_option("deepseek-r1:7b", "DeepSeek-R1 7B", "7B", 20, 0, 4.7, "推理能力更强，适合内存更充足的机器。"),
            build_option("deepseek-r1:8b", "DeepSeek-R1 8B", "8B", 24, 8, 5.2, "当前主流档位，兼顾能力和本地可用性。"),
            build_option("deepseek-r1:14b", "DeepSeek-R1 14B", "14B", 32, 10, 9.0, "更强推理能力，适合高配用户。"),
            build_option("deepseek-r1:32b", "DeepSeek-R1 32B", "32B", 64, 24, 20.0, "高配档位，普通电脑通常不建议。"),
            build_option("deepseek-r1:70b", "DeepSeek-R1 70B", "70B", 128, 48, 43.0, "专业级高负载部署。"),
            build_option("deepseek-r1:671b", "DeepSeek-R1 671B", "671B", 512, 160, 404.0, "超大档位，不适合个人电脑。"),
        ],
    ),
    build_family(
        family="deepseek-llm",
        family_display_name="DeepSeek-LLM",
        match_keywords=["deepseek-llm", "deepseek llm"],
        trusted_authors=["deepseek-ai"],
        deploy_options=[
            build_option("deepseek-llm:7b", "DeepSeek-LLM 7B", "7B", 20, 0, 4.0, "基础通用模型，适合本地日常问答。"),
            build_option("deepseek-llm:67b", "DeepSeek-LLM 67B", "67B", 128, 48, 38.0, "超大档位，普通电脑不建议。"),
        ],
    ),
]
