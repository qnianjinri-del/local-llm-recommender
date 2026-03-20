# Local LLM Recommender

【小白专用】一键识别电脑硬件，推荐适合本机的最新开源大模型，并通过 Ollama 一键部署。

## 已实现功能

- 自动识别本机硬件信息
- 联网获取近期更新的模型家族
- 根据硬件配置推荐适合的开源模型
- 通过 Ollama 一键下载并部署模型
- 在网页中直接测试模型对话

## 技术栈

- Python 3.13
- Streamlit
- Ollama
- Hugging Face API

## 运行前准备

请先安装：

- Python 3.13
- Ollama
- Git

并确保 Ollama 已经启动。

## 安装依赖

```bash
python -m pip install -r requirements.txt
