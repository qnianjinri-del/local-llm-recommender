import json
import subprocess
import tempfile
import time
import webbrowser
from pathlib import Path
from typing import Callable, Optional

import requests

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_WINDOWS_INSTALLER_URL = "https://ollama.com/download/OllamaSetup.exe"
DEFAULT_INSTALLER_PATH = Path(tempfile.gettempdir()) / "OllamaSetup.exe"


class OllamaPullError(RuntimeError):
    pass


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


def pull_model_stream(
    model_id: str,
    *,
    progress_callback: Optional[Callable[[Optional[int], Optional[int], dict], None]] = None,
    status_callback: Optional[Callable[[str, dict], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
):
    with requests.post(
        f"{OLLAMA_BASE_URL}/api/pull",
        json={"model": model_id, "stream": True},
        stream=True,
        timeout=(10, None),
    ) as response:
        response.raise_for_status()
        last_payload = None

        for raw_line in response.iter_lines(decode_unicode=True):
            if cancel_check and cancel_check():
                raise OllamaPullError("用户已取消模型下载。")

            if not raw_line:
                continue

            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            last_payload = payload

            if payload.get("error"):
                raise OllamaPullError(str(payload["error"]))

            status = str(payload.get("status", "")).strip()
            completed = payload.get("completed")
            total = payload.get("total")

            if status_callback:
                status_callback(status, payload)

            if progress_callback:
                progress_callback(completed, total, payload)

            if status == "success":
                break

        return last_payload or {"status": "success"}


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


def try_start_ollama(timeout=20):
    if check_ollama_running():
        return True

    creationflags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        creationflags = subprocess.CREATE_NO_WINDOW

    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
        )
    except Exception:
        return False

    start_time = time.time()
    while time.time() - start_time < timeout:
        if check_ollama_running():
            return True
        time.sleep(1)

    time.sleep(2)
    return check_ollama_running()


def download_ollama_installer(
    destination: Optional[str] = None,
    *,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    stop_check: Optional[Callable[[], bool]] = None,
):
    target = Path(destination) if destination else DEFAULT_INSTALLER_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        with requests.get(OLLAMA_WINDOWS_INSTALLER_URL, stream=True, timeout=(10, 15)) as response:
            response.raise_for_status()
            total = int(response.headers.get("Content-Length") or 0)
            downloaded = 0

            with target.open("wb") as f:
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if stop_check and stop_check():
                        raise RuntimeError("已取消 Ollama 安装器下载。")

                    if not chunk:
                        continue

                    f.write(chunk)
                    downloaded += len(chunk)

                    if progress_callback:
                        progress_callback(downloaded, total)

        return str(target)
    except Exception:
        if target.exists():
            try:
                target.unlink()
            except Exception:
                pass
        raise


def launch_ollama_installer(installer_path: str):
    subprocess.Popen([installer_path])
    return True


def open_ollama_download_page():
    webbrowser.open("https://ollama.com/download")
