from model_catalog import DEPLOY_CATALOG


def get_best_deploy_option_for_family(family_name, hardware_info, category="general"):
    ram_gb = hardware_info.get("ram_gb", 0)
    gpus = hardware_info.get("gpus", [])

    max_vram_gb = 0
    if gpus:
        max_vram_gb = max(gpu.get("vram_gb", 0) for gpu in gpus)

    for family in DEPLOY_CATALOG:
        if family["family"] != family_name:
            continue

        candidates = []
        for option in family["deploy_options"]:
            if option["category"] != category:
                continue
            if ram_gb < option["min_ram_gb"]:
                continue
            if max_vram_gb < option["min_vram_gb"]:
                continue
            candidates.append(option)

        if not candidates:
            return None

        candidates.sort(
            key=lambda x: (x["min_vram_gb"], x["min_ram_gb"], x["download_size_gb"]),
            reverse=True,
        )
        return candidates[0]

    return None


def recommend_from_recent_models(recent_models, hardware_info, category="general"):
    results = []
    seen_families = set()

    for model in recent_models:
        family_name = model.get("family")
        if not family_name:
            continue

        if family_name in seen_families:
            continue
        seen_families.add(family_name)

        best_option = get_best_deploy_option_for_family(
            family_name=family_name,
            hardware_info=hardware_info,
            category=category,
        )

        if best_option is None:
            continue

        results.append({
            "family": family_name,
            "source_model_id": model.get("id"),
            "last_modified": model.get("last_modified"),
            "deploy_id": best_option["id"],
            "display_name": best_option["display_name"],
            "notes": best_option["notes"],
            "download_size_gb": best_option["download_size_gb"],
        })

    return results