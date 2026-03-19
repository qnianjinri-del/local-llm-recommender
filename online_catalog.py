import requests
from model_catalog import DEPLOY_CATALOG

HF_API = "https://huggingface.co/api/models"


def fetch_recent_models_for_family(family_config, limit=10):
    results = []
    seen_ids = set()

    for keyword in family_config["match_keywords"]:
        for author in family_config["trusted_authors"]:
            response = requests.get(
                HF_API,
                params={
                    "search": keyword,
                    "author": author,
                    "sort": "lastModified",
                    "direction": -1,
                    "limit": limit,
                },
                timeout=20,
            )
            response.raise_for_status()
            items = response.json()

            for item in items:
                model_id = item.get("id")
                if not model_id or model_id in seen_ids:
                    continue

                seen_ids.add(model_id)
                results.append({
                    "id": model_id,
                    "last_modified": item.get("lastModified"),
                    "family": family_config["family"],
                    "source": "huggingface",
                })

    return results


def fetch_recent_supported_models(limit_per_family=10):
    all_results = []

    for family in DEPLOY_CATALOG:
        family_results = fetch_recent_models_for_family(
            family_config=family,
            limit=limit_per_family,
        )
        all_results.extend(family_results)

    all_results.sort(
        key=lambda x: x.get("last_modified") or "",
        reverse=True,
    )
    return all_results


if __name__ == "__main__":
    models = fetch_recent_supported_models(limit_per_family=5)

    print("最近更新且属于支持家族的模型：")
    for model in models[:10]:
        print(model)