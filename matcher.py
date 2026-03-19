from model_catalog import DEPLOY_CATALOG


def match_model_family(model_id):
    model_id_lower = model_id.lower()

    for family in DEPLOY_CATALOG:
        for keyword in family["match_keywords"]:
            if keyword in model_id_lower:
                return family

    return None


def filter_supported_recent_models(recent_models):
    results = []

    for model in recent_models:
        model_id = model.get("id", "")
        family = match_model_family(model_id)

        if family is None:
            continue

        results.append({
            "id": model_id,
            "last_modified": model.get("last_modified"),
            "family": family["family"],
            "deploy_options": family["deploy_options"],
        })

    return results