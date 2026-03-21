import json
from datetime import datetime, timezone
from pathlib import Path

import requests

from model_catalog import DEPLOY_CATALOG

HF_API = "https://huggingface.co/api/models"
CACHE_DIR = Path.home() / ".local_llm_recommender"
CACHE_FILE = CACHE_DIR / "recent_models_cache.json"


class OnlineCatalogError(RuntimeError):
    pass


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def _safe_last_modified(value):
    return value or ""


def _parse_iso_datetime(value):
    if not value:
        return None

    text = str(value).strip()
    if not text:
        return None

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def _sort_models(models):
    return sorted(models, key=lambda x: _safe_last_modified(x.get("last_modified")), reverse=True)


def fetch_recent_models_for_family(family_config, limit=10):
    results = []
    seen_ids = set()
    last_error = None

    for keyword in family_config.get("match_keywords", []):
        for author in family_config.get("trusted_authors", []):
            try:
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
            except Exception as exc:
                last_error = exc
                continue

            for item in items:
                model_id = item.get("id")
                if not model_id or model_id in seen_ids:
                    continue

                seen_ids.add(model_id)
                results.append(
                    {
                        "id": model_id,
                        "last_modified": item.get("lastModified"),
                        "family": family_config["family"],
                        "source": "huggingface",
                    }
                )

    if results:
        return _sort_models(results)

    if last_error:
        raise OnlineCatalogError(f"无法获取 {family_config['family']} 的在线模型信息：{last_error}") from last_error

    return []


def fetch_recent_supported_models(limit_per_family=10):
    all_results = []
    errors = []

    for family in DEPLOY_CATALOG:
        try:
            family_results = fetch_recent_models_for_family(
                family_config=family,
                limit=limit_per_family,
            )
            all_results.extend(family_results)
        except Exception as exc:
            errors.append(str(exc))

    all_results = _sort_models(all_results)

    if all_results:
        return all_results

    if errors:
        raise OnlineCatalogError("；".join(errors))

    raise OnlineCatalogError("没有获取到任何在线模型结果。")


def save_recent_models_cache(models):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "saved_at": _utc_now_iso(),
        "models": _sort_models(models),
    }
    CACHE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_recent_models_cache():
    if not CACHE_FILE.exists():
        return None

    try:
        payload = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None

    models = payload.get("models")
    if not isinstance(models, list) or not models:
        return None

    return {
        "saved_at": payload.get("saved_at"),
        "models": _sort_models(models),
    }


def build_offline_fallback_models():
    results = []

    for family in DEPLOY_CATALOG:
        deploy_options = family.get("deploy_options", [])
        if not deploy_options:
            continue

        first_option = deploy_options[0]
        results.append(
            {
                "id": first_option.get("id", family["family"]),
                "last_modified": None,
                "family": family["family"],
                "source": "offline_catalog",
            }
        )

    return results


def describe_cache_age(saved_at):
    dt = _parse_iso_datetime(saved_at)
    if not dt:
        return "缓存时间未知"

    delta = datetime.now(timezone.utc) - dt
    hours = int(delta.total_seconds() // 3600)

    if hours < 1:
        return "刚刚缓存"
    if hours < 24:
        return f"约 {hours} 小时前缓存"

    days = delta.days
    return f"约 {days} 天前缓存"


def load_recent_supported_models_with_fallback(limit_per_family=10):
    try:
        models = fetch_recent_supported_models(limit_per_family=limit_per_family)
        save_recent_models_cache(models)
        return {
            "models": models,
            "mode": "online",
            "message": "已成功获取在线最新模型列表。",
            "cache_saved_at": _utc_now_iso(),
        }
    except Exception as online_error:
        cached = load_recent_models_cache()
        if cached:
            age_text = describe_cache_age(cached.get("saved_at"))
            return {
                "models": cached["models"],
                "mode": "cache",
                "message": f"在线获取失败，已切换到本地缓存（{age_text}）。",
                "cache_saved_at": cached.get("saved_at"),
                "error": str(online_error),
            }

        offline_models = build_offline_fallback_models()
        return {
            "models": offline_models,
            "mode": "offline",
            "message": "在线获取失败，且没有可用缓存，已切换到离线内置模型目录。",
            "cache_saved_at": None,
            "error": str(online_error),
        }


if __name__ == "__main__":
    state = load_recent_supported_models_with_fallback(limit_per_family=5)
    print(f"模型来源模式：{state['mode']}")
    print(state["message"])
    for model in state["models"][:10]:
        print(model)
