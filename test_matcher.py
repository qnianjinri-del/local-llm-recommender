from online_catalog import fetch_recent_models
from matcher import filter_supported_recent_models

recent_models = fetch_recent_models(limit=50)
matched_models = filter_supported_recent_models(recent_models)

print("匹配到的可部署模型家族：")
for model in matched_models:
    print(model["family"], "=>", model["id"])