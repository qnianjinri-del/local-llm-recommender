from detector import get_hardware_info
from recommender import recommend_models

hardware = get_hardware_info()
models = recommend_models(hardware, category="general")

print("硬件信息：")
print(hardware)

print("\n推荐模型：")
for model in models:
    print(f"- {model['display_name']} ({model['id']})")
