import requests

OLLAMA_BASE_URL = "http://localhost:11434"


def check_ollama_running():
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def list_local_models():
    response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
    response.raise_for_status()
    data = response.json()
    return data.get("models", [])


def is_model_installed(model_id):
    models = list_local_models()
    for model in models:
        if model.get("model") == model_id:
            return True
    return False


def pull_model(model_id):
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/pull",
        json={
            "model": model_id,
            "stream": False,
        },
        timeout=3600,
    )
    response.raise_for_status()
    return response.json()


def ensure_model_installed(model_id):
    if is_model_installed(model_id):
        return {
            "status": "already_installed",
            "model": model_id,
        }

    result = pull_model(model_id)
    return {
        "status": "downloaded",
        "model": model_id,
        "detail": result,
    }


def generate_text(model_id, prompt):
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": model_id,
            "prompt": prompt,
            "stream": False,
        },
        timeout=300,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("response", "")