from ollama_backend import generate_text

reply = generate_text(
    model_id="qwen2.5:3b",
    prompt="请用中文一句话介绍你自己。"
)

print("模型回复：")
print(reply)