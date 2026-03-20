import sys
import json

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QTextEdit,
    QComboBox,
    QMessageBox,
)

from detector import get_hardware_info
from online_catalog import fetch_recent_supported_models
from recommender import recommend_from_recent_models
from ollama_backend import (
    check_ollama_running,
    ensure_model_installed,
    generate_text,
)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Local LLM Recommender")
        self.resize(950, 850)

        self.recommendations = []

        title = QLabel("本地开源大模型推荐器")
        subtitle = QLabel("桌面版原型：接入硬件检测、模型推荐、一键部署和测试对话。")

        self.scan_button = QPushButton("开始扫描并推荐")
        self.scan_button.clicked.connect(self.handle_scan)

        self.model_select = QComboBox()
        self.model_select.setEnabled(False)

        self.deploy_button = QPushButton("一键部署当前选中模型")
        self.deploy_button.setEnabled(False)
        self.deploy_button.clicked.connect(self.handle_deploy)

        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        self.result_box.setPlaceholderText("这里会显示硬件信息、推荐结果和部署日志。")

        self.prompt_box = QTextEdit()
        self.prompt_box.setPlaceholderText("请输入测试问题，例如：请用中文一句话介绍你自己。")
        self.prompt_box.setFixedHeight(100)
        self.prompt_box.setPlainText("请用中文一句话介绍你自己。")

        self.chat_button = QPushButton("发送测试消息")
        self.chat_button.setEnabled(False)
        self.chat_button.clicked.connect(self.handle_chat)

        self.chat_box = QTextEdit()
        self.chat_box.setReadOnly(True)
        self.chat_box.setPlaceholderText("这里会显示模型回复。")

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.scan_button)
        layout.addWidget(self.model_select)
        layout.addWidget(self.deploy_button)
        layout.addWidget(self.result_box)
        layout.addWidget(QLabel("测试问题"))
        layout.addWidget(self.prompt_box)
        layout.addWidget(self.chat_button)
        layout.addWidget(QLabel("模型回复"))
        layout.addWidget(self.chat_box)

        self.setLayout(layout)

    def ensure_ollama_ready(self):
        if check_ollama_running():
            return True

        QMessageBox.warning(
            self,
            "未检测到 Ollama",
            "当前没有检测到 Ollama 正在运行。\n\n请先安装并启动 Ollama，然后再使用模型推荐、部署和测试功能。"
        )
        return False

    def handle_scan(self):
        if not self.ensure_ollama_ready():
            return

        try:
            hardware = get_hardware_info()
            recent_models = fetch_recent_supported_models(limit_per_family=5)
            recommendations = recommend_from_recent_models(
                recent_models,
                hardware,
                category="general",
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "扫描失败",
                f"扫描或推荐过程中出现错误：\n{e}"
            )
            return

        self.recommendations = recommendations
        self.model_select.clear()
        self.chat_box.clear()

        output_lines = []
        output_lines.append("=== 硬件信息 ===")
        output_lines.append(json.dumps(hardware, ensure_ascii=False, indent=2))
        output_lines.append("")
        output_lines.append("=== 推荐结果 ===")

        if recommendations:
            for item in recommendations:
                self.model_select.addItem(
                    f"{item['display_name']} ({item['deploy_id']})",
                    item,
                )

                output_lines.append(f"模型名称: {item['display_name']}")
                output_lines.append(f"部署标签: {item['deploy_id']}")
                output_lines.append(f"模型家族: {item['family']}")
                output_lines.append(f"最近官方模型: {item['source_model_id']}")
                output_lines.append(f"最近更新时间: {item['last_modified']}")
                output_lines.append(f"说明: {item['notes']}")
                output_lines.append("-" * 40)

            self.model_select.setEnabled(True)
            self.deploy_button.setEnabled(True)
            self.chat_button.setEnabled(True)
        else:
            output_lines.append("没有找到适合当前机器的推荐模型。")
            self.model_select.setEnabled(False)
            self.deploy_button.setEnabled(False)
            self.chat_button.setEnabled(False)

        self.result_box.setPlainText("\n".join(output_lines))

    def handle_deploy(self):
        if not self.ensure_ollama_ready():
            return

        index = self.model_select.currentIndex()
        if index < 0:
            return

        item = self.model_select.currentData()
        if not item:
            return

        model_id = item["deploy_id"]

        self.result_box.append("")
        self.result_box.append(f"=== 开始部署 {model_id} ===")

        try:
            result = ensure_model_installed(model_id)
        except Exception as e:
            QMessageBox.critical(
                self,
                "部署失败",
                f"部署模型时出现错误：\n{e}"
            )
            self.result_box.append("=== 部署失败 ===")
            self.result_box.append(str(e))
            self.result_box.append("")
            return

        self.result_box.append("=== 部署结果 ===")
        self.result_box.append(json.dumps(result, ensure_ascii=False, indent=2))
        self.result_box.append("")

        QMessageBox.information(
            self,
            "部署完成",
            f"{model_id} 已完成检查/部署。"
        )

    def handle_chat(self):
        if not self.ensure_ollama_ready():
            return

        index = self.model_select.currentIndex()
        if index < 0:
            return

        item = self.model_select.currentData()
        if not item:
            return

        model_id = item["deploy_id"]
        prompt = self.prompt_box.toPlainText().strip()

        if not prompt:
            self.chat_box.setPlainText("请输入测试问题。")
            return

        self.chat_box.setPlainText(f"正在调用 {model_id} ...")

        try:
            reply = generate_text(model_id, prompt)
        except Exception as e:
            QMessageBox.critical(
                self,
                "调用失败",
                f"调用模型时出现错误：\n{e}"
            )
            self.chat_box.setPlainText(f"调用失败：{e}")
            return

        self.chat_box.setPlainText(reply)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())