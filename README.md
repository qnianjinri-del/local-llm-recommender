<p align="center">
  <img src="assets/hero.png" width="100%" alt="Local LLM Recommender Hero Banner">
</p>

# Local LLM Recommender

**一键识别电脑硬件，推荐适合本机的开源大模型，并通过 Ollama 一键部署**

---

## 功能亮点
- **自动识别硬件信息**：快速检测 CPU、内存和 GPU 信息  
- **智能模型推荐**：根据硬件和最新官方模型动态推荐  
- **一键部署**：通过 Ollama 快速部署模型，无需手动配置  
- **直接测试**：在桌面应用或网页界面中直接发送测试消息  
- **低门槛**：适合 AI 小白，减少操作成本  

---

## 桌面应用
桌面原型集成硬件检测、模型推荐、一键部署和对话测试功能。  
支持滚动查看全部内容，适配笔记本小屏幕。

### 系统要求
- Windows / macOS / Linux  
- Python 3.13  
- Ollama 已安装并启动  

### 启动方式
在项目根目录下：
```bash
python desktop_app.py