# Local LLM Recommender

一键识别电脑硬件，推荐适合本机的最新开源大模型，并通过 Ollama 一键部署。

## 下载方式

请前往本仓库的 **Releases** 页面，下载最新版本：

- `LocalLLMRecommender.exe`

## 适合谁使用

这个工具面向：

- 想在本地运行开源大模型的普通用户
- 不熟悉 Python、命令行、模型部署的 AI 小白
- 想快速判断自己电脑适合跑什么模型的用户

## 当前已实现功能

- 自动识别本机硬件信息
- 联网获取近期更新的模型家族
- 根据硬件配置推荐适合的开源模型
- 通过 Ollama 一键下载并部署模型
- 在桌面界面中直接测试模型对话

## 使用前准备

使用本工具前，请先安装并启动 **Ollama**。

如果没有安装 Ollama，请先前往 Ollama 官网完成安装。

## 使用步骤

1. 打开 `LocalLLMRecommender.exe`
2. 点击 **开始扫描并推荐**
3. 查看当前电脑适合的模型
4. 在下拉框中选择推荐模型
5. 点击 **一键部署当前选中模型**
6. 在测试问题中输入内容
7. 点击 **发送测试消息** 查看模型回复

## 当前支持的模型家族

- Qwen3.5
- Qwen2.5
- Qwen2.5 Coder

## 当前项目状态

当前版本为桌面版 MVP，已经打通：

- 硬件识别
- 在线模型发现
- 本地推荐
- 一键部署
- 本地测试对话

后续计划继续完善：

- 更丰富的模型家族
- 更精细的推荐逻辑
- 更美观、更有科技感的桌面界面
- 更完善的 Ollama 检测与安装引导
- 更稳定的 Windows 发布体验

## 技术栈

- Python 3.13
- PySide6
- Ollama
- Hugging Face API
- PyInstaller

## 开发者运行方式

如果你想从源码运行项目：

```bash
python -m pip install -r requirements.txt
python desktop_app.py