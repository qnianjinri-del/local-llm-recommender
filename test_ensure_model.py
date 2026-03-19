from ollama_backend import ensure_model_installed

result = ensure_model_installed("qwen3.5:0.8b")
print(result)