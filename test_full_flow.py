from detector import get_hardware_info
from online_catalog import fetch_recent_supported_models
from recommender import recommend_from_recent_models
from ollama_backend import ensure_model_installed


hardware = get_hardware_info()
recent_models = fetch_recent_supported_models(limit_per_family=5)
recommendations = recommend_from_recent_models(
    recent_models,
    hardware,
    category="general",
)

print("硬件信息：")
print(hardware)

print("\n推荐结果：")
for item in recommendations:
    print(f"- {item['display_name']} ({item['deploy_id']})")
    print(f"  来自家族: {item['family']}")
    print(f"  最近模型: {item['source_model_id']}")
    print(f"  最近更新时间: {item['last_modified']}")
    print()

if recommendations:
    chosen = recommendations[0]
    print("准备部署第一个推荐模型：")
    print(chosen["deploy_id"])

    result = ensure_model_installed(chosen["deploy_id"])
    print("\n部署结果：")
    print(result)
else:
    print("没有找到适合当前机器的推荐模型。")