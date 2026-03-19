from detector import get_hardware_info
from online_catalog import fetch_recent_supported_models
from recommender import recommend_from_recent_models

hardware = get_hardware_info()
recent_models = fetch_recent_supported_models(limit_per_family=5)
recommendations = recommend_from_recent_models(recent_models, hardware, category="general")

print("硬件信息：")
print(hardware)

print("\n最终推荐：")
for item in recommendations:
    print(f"- 家族: {item['family']}")
    print(f"  最近模型: {item['source_model_id']}")
    print(f"  推荐部署: {item['display_name']} ({item['deploy_id']})")
    print(f"  最近更新时间: {item['last_modified']}")
    print(f"  说明: {item['notes']}")
    print()