from ollama_backend import check_ollama_running, list_local_models

print("Ollama 是否运行中：", check_ollama_running())

print("\n本地模型列表：")
models = list_local_models()
for model in models:
    print("-", model.get("model"))