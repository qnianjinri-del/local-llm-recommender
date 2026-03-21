import sys
import json
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QTextEdit,
    QMessageBox,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QGridLayout,
    QScrollArea,
    QGraphicsDropShadowEffect,
)

from detector import get_hardware_info
from online_catalog import fetch_recent_supported_models
from recommender import recommend_from_recent_models
from ollama_backend import (
    check_ollama_running,
    ensure_model_installed,
    generate_text,
    try_start_ollama,
    open_ollama_download_page,
)


def add_glow(widget, color="#60a5fa", blur=28, x_offset=0, y_offset=0):
    effect = QGraphicsDropShadowEffect()
    effect.setBlurRadius(blur)
    effect.setOffset(x_offset, y_offset)
    effect.setColor(QColor(color))
    widget.setGraphicsEffect(effect)


class BackgroundWidget(QWidget):
    def __init__(self, image_path: str):
        super().__init__()
        self.image_path = image_path
        self.pixmap = QPixmap(image_path) if Path(image_path).exists() else QPixmap()

        self.scan_y = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance_animation)
        self.timer.start(35)

    def advance_animation(self):
        self.scan_y += 2
        if self.scan_y > max(1, self.height()):
            self.scan_y = 0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.Antialiasing, True)

        if not self.pixmap.isNull():
            scaled = self.pixmap.scaled(
                self.size(),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
            painter.fillRect(self.rect(), QColor(6, 10, 22, 75))
        else:
            painter.fillRect(self.rect(), QColor(8, 12, 26))

        painter.fillRect(self.rect(), QColor(30, 50, 95, 22))

        grid_pen = QPen(QColor(90, 140, 255, 18))
        grid_pen.setWidth(1)
        painter.setPen(grid_pen)

        grid_size = 36
        for x in range(0, self.width(), grid_size):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), grid_size):
            painter.drawLine(0, y, self.width(), y)

        scan_color = QColor(56, 189, 248, 42)
        painter.fillRect(0, self.scan_y, self.width(), 3, scan_color)
        painter.fillRect(0, max(0, self.scan_y - 10), self.width(), 14, QColor(56, 189, 248, 10))

        corner_pen = QPen(QColor(125, 211, 252, 40))
        corner_pen.setWidth(2)
        painter.setPen(corner_pen)

        length = 36
        m = 12
        painter.drawLine(m, m, m + length, m)
        painter.drawLine(m, m, m, m + length)

        painter.drawLine(self.width() - m - length, m, self.width() - m, m)
        painter.drawLine(self.width() - m, m, self.width() - m, m + length)

        painter.drawLine(m, self.height() - m, m + length, self.height() - m)
        painter.drawLine(m, self.height() - m - length, m, self.height() - m)

        painter.drawLine(self.width() - m - length, self.height() - m, self.width() - m, self.height() - m)
        painter.drawLine(self.width() - m, self.height() - m - length, self.width() - m, self.height() - m)


class Card(QFrame):
    def __init__(self, title_text: str = ""):
        super().__init__()
        self.setObjectName("card")

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(18, 18, 18, 18)
        self.layout.setSpacing(12)

        if title_text:
            self.title = QLabel(title_text)
            self.title.setObjectName("cardTitle")
            self.layout.addWidget(self.title)

        self.setLayout(self.layout)
        add_glow(self, "#3b82f6", blur=22)


class MetricCard(QFrame):
    def __init__(self, label: str, value: str):
        super().__init__()
        self.setObjectName("metricCard")

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(6)

        self.label_widget = QLabel(label)
        self.label_widget.setObjectName("metricLabel")

        self.value_widget = QLabel(value)
        self.value_widget.setObjectName("metricValue")
        self.value_widget.setWordWrap(True)

        layout.addWidget(self.label_widget)
        layout.addWidget(self.value_widget)
        self.setLayout(layout)
        add_glow(self, "#0ea5e9", blur=18)

    def update_value(self, value: str):
        self.value_widget.setText(value)


class RecommendationCard(QFrame):
    def __init__(self, item: dict, on_select):
        super().__init__()
        self.item = item
        self.on_select = on_select
        self.setObjectName("recommendationCard")

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        title = QLabel(item["display_name"])
        title.setObjectName("recommendationTitle")

        subtitle = QLabel(item["deploy_id"])
        subtitle.setObjectName("recommendationSubTitle")

        family = QLabel(f"模型家族：{item['family']}")
        family.setObjectName("recommendationMeta")

        source = QLabel(f"最近官方模型：{item['source_model_id']}")
        source.setObjectName("recommendationMeta")
        source.setWordWrap(True)

        updated = QLabel(f"最近更新时间：{item['last_modified']}")
        updated.setObjectName("recommendationMeta")
        updated.setWordWrap(True)

        notes = QLabel(f"推荐说明：{item['notes']}")
        notes.setObjectName("recommendationNote")
        notes.setWordWrap(True)

        select_btn = QPushButton("设为当前模型")
        select_btn.setObjectName("secondaryButton")
        select_btn.clicked.connect(lambda: self.on_select(self.item))

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(family)
        layout.addWidget(source)
        layout.addWidget(updated)
        layout.addWidget(notes)
        layout.addWidget(select_btn)

        self.setLayout(layout)
        add_glow(self, "#2563eb", blur=16)

    def set_selected(self, selected: bool):
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Local LLM Recommender")
        self.resize(1260, 900)

        self.recommendations = []
        self.recommendation_cards = []
        self.current_model = None
        self.background_path = "assets/bg_network.jpg"

        self.bg = BackgroundWidget(self.background_path)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.bg)

        self.build_ui()
        self.apply_styles()
        self.update_ollama_status()

    def build_ui(self):
        bg_layout = QVBoxLayout(self.bg)
        bg_layout.setContentsMargins(0, 0, 0, 0)
        bg_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setObjectName("mainScroll")

        self.content_widget = QWidget()
        self.content_widget.setObjectName("contentWidget")

        self.container = QVBoxLayout(self.content_widget)
        self.container.setContentsMargins(24, 22, 24, 22)
        self.container.setSpacing(16)

        self.scroll_area.setWidget(self.content_widget)
        bg_layout.addWidget(self.scroll_area)

        header = QHBoxLayout()
        header.setSpacing(16)

        title_col = QVBoxLayout()
        title_col.setSpacing(4)

        main_title = QLabel("Local LLM Recommender")
        main_title.setObjectName("mainTitle")

        sub_title = QLabel("一键识别电脑硬件，推荐适合本机的开源大模型，并通过 Ollama 一键部署。")
        sub_title.setObjectName("subTitle")

        hud_hint = QLabel("NEURAL MODEL CONTROL PANEL")
        hud_hint.setObjectName("hudHint")

        title_col.addWidget(main_title)
        title_col.addWidget(sub_title)
        title_col.addWidget(hud_hint)

        self.status_badge = QLabel("OLLAMA STATUS")
        self.status_badge.setObjectName("statusBadge")
        add_glow(self.status_badge, "#22c55e", blur=20)

        header.addLayout(title_col, 1)
        header.addWidget(self.status_badge, 0, Qt.AlignTop)

        main_row = QHBoxLayout()
        main_row.setSpacing(16)

        left_col = QVBoxLayout()
        left_col.setSpacing(16)

        hardware_card = Card("硬件概览")
        hardware_grid = QGridLayout()
        hardware_grid.setSpacing(12)

        self.os_metric = MetricCard("操作系统", "--")
        self.cpu_metric = MetricCard("CPU", "--")
        self.ram_metric = MetricCard("内存", "--")
        self.gpu_metric = MetricCard("GPU", "--")

        hardware_grid.addWidget(self.os_metric, 0, 0)
        hardware_grid.addWidget(self.cpu_metric, 0, 1)
        hardware_grid.addWidget(self.ram_metric, 1, 0)
        hardware_grid.addWidget(self.gpu_metric, 1, 1)

        hardware_card.layout.addLayout(hardware_grid)

        action_card = Card("操作控制")

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        self.scan_button = QPushButton("开始扫描并推荐")
        self.scan_button.clicked.connect(self.handle_scan)
        add_glow(self.scan_button, "#3b82f6", blur=26)

        self.ollama_button = QPushButton("检测 / 启动 Ollama")
        self.ollama_button.setObjectName("secondaryButton")
        self.ollama_button.clicked.connect(self.handle_ollama_assist)

        button_row.addWidget(self.scan_button, 2)
        button_row.addWidget(self.ollama_button, 1)

        self.current_model_label = QLabel("当前模型：未选择")
        self.current_model_label.setObjectName("currentModelLabel")
        self.current_model_label.setWordWrap(True)

        self.deploy_button = QPushButton("一键部署当前模型")
        self.deploy_button.setEnabled(False)
        self.deploy_button.clicked.connect(self.handle_deploy)
        add_glow(self.deploy_button, "#7c3aed", blur=24)

        action_card.layout.addLayout(button_row)
        action_card.layout.addWidget(self.current_model_label)
        action_card.layout.addWidget(self.deploy_button)

        log_card = Card("运行日志")
        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        self.result_box.setObjectName("logBox")
        self.result_box.setPlaceholderText("这里会显示硬件信息、推荐结果和部署日志。")
        log_card.layout.addWidget(self.result_box)

        left_col.addWidget(hardware_card)
        left_col.addWidget(action_card)
        left_col.addWidget(log_card, 1)

        right_col = QVBoxLayout()
        right_col.setSpacing(16)

        recommendation_card = Card("推荐模型")
        rec_tip = QLabel("根据本机硬件与近期官方模型动态推荐。点击“设为当前模型”后即可部署或测试。")
        rec_tip.setObjectName("tipLabel")
        rec_tip.setWordWrap(True)

        self.rec_scroll = QScrollArea()
        self.rec_scroll.setWidgetResizable(True)
        self.rec_scroll.setObjectName("recommendationScroll")

        self.rec_container = QWidget()
        self.rec_layout = QVBoxLayout(self.rec_container)
        self.rec_layout.setContentsMargins(0, 0, 0, 0)
        self.rec_layout.setSpacing(12)

        self.rec_empty = QLabel("点击“开始扫描并推荐”后，这里会显示推荐模型卡片。")
        self.rec_empty.setObjectName("emptyHint")
        self.rec_empty.setWordWrap(True)
        self.rec_layout.addWidget(self.rec_empty)
        self.rec_layout.addStretch()

        self.rec_scroll.setWidget(self.rec_container)

        recommendation_card.layout.addWidget(rec_tip)
        recommendation_card.layout.addWidget(self.rec_scroll)

        right_col.addWidget(recommendation_card, 1)

        main_row.addLayout(left_col, 3)
        main_row.addLayout(right_col, 2)

        chat_card = Card("测试对话")

        prompt_label = QLabel("测试问题")
        prompt_label.setObjectName("sectionLabel")

        self.prompt_box = QTextEdit()
        self.prompt_box.setObjectName("promptBox")
        self.prompt_box.setFixedHeight(100)
        self.prompt_box.setPlainText("请用中文一句话介绍你自己。")

        self.chat_button = QPushButton("发送测试消息")
        self.chat_button.setEnabled(False)
        self.chat_button.clicked.connect(self.handle_chat)
        add_glow(self.chat_button, "#06b6d4", blur=24)

        reply_label = QLabel("模型回复")
        reply_label.setObjectName("sectionLabel")

        self.chat_box = QTextEdit()
        self.chat_box.setReadOnly(True)
        self.chat_box.setObjectName("chatBox")
        self.chat_box.setPlaceholderText("这里会显示模型回复。")

        chat_card.layout.addWidget(prompt_label)
        chat_card.layout.addWidget(self.prompt_box)
        chat_card.layout.addWidget(self.chat_button)
        chat_card.layout.addWidget(reply_label)
        chat_card.layout.addWidget(self.chat_box)

        self.container.addLayout(header)
        self.container.addLayout(main_row, 3)
        self.container.addWidget(chat_card, 2)

    def apply_styles(self):
        self.setStyleSheet("""
            QWidget {
                color: #eef4ff;
                font-size: 14px;
                font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
                background: transparent;
            }

            QLabel#mainTitle {
                font-size: 32px;
                font-weight: 800;
                color: #f8fbff;
                letter-spacing: 1px;
            }

            QLabel#subTitle {
                font-size: 14px;
                color: rgba(232, 240, 255, 0.9);
            }

            QLabel#hudHint {
                font-size: 12px;
                font-weight: 700;
                color: #7dd3fc;
                padding: 6px 10px;
                background-color: rgba(15, 23, 42, 70);
                border: 1px solid rgba(125, 211, 252, 70);
                border-radius: 12px;
                max-width: 260px;
            }

            QLabel#statusBadge {
                font-size: 12px;
                font-weight: 700;
                color: #dbeafe;
                padding: 8px 14px;
                background-color: rgba(20, 40, 70, 120);
                border: 1px solid rgba(125, 211, 252, 90);
                border-radius: 14px;
                min-width: 150px;
            }

            QLabel#cardTitle {
                font-size: 18px;
                font-weight: 700;
                color: #dbeafe;
            }

            QLabel#sectionLabel {
                font-size: 13px;
                font-weight: 600;
                color: #93c5fd;
            }

            QLabel#tipLabel {
                font-size: 12px;
                color: #d7e3f8;
                background-color: rgba(15, 23, 42, 58);
                border-radius: 10px;
                padding: 10px;
            }

            QLabel#emptyHint {
                font-size: 13px;
                color: #c8d6f1;
                background-color: rgba(15, 23, 42, 55);
                border-radius: 12px;
                padding: 14px;
            }

            QLabel#currentModelLabel {
                font-size: 13px;
                color: #bfdbfe;
                background-color: rgba(15, 23, 42, 75);
                border-radius: 12px;
                padding: 10px;
            }

            QFrame#card {
                background-color: rgba(7, 14, 28, 102);
                border: 1px solid rgba(120, 170, 255, 92);
                border-radius: 20px;
            }

            QFrame#metricCard {
                background-color: rgba(8, 18, 35, 110);
                border: 1px solid rgba(120, 170, 255, 80);
                border-radius: 16px;
            }

            QLabel#metricLabel {
                font-size: 12px;
                color: #93c5fd;
            }

            QLabel#metricValue {
                font-size: 15px;
                font-weight: 700;
                color: #f8fbff;
            }

            QFrame#recommendationCard {
                background-color: rgba(8, 18, 35, 95);
                border: 1px solid rgba(120, 170, 255, 72);
                border-radius: 16px;
            }

            QFrame#recommendationCard[selected="true"] {
                background-color: rgba(22, 42, 86, 150);
                border: 1px solid rgba(125, 211, 252, 185);
            }

            QLabel#recommendationTitle {
                font-size: 16px;
                font-weight: 700;
                color: #f8fbff;
            }

            QLabel#recommendationSubTitle {
                font-size: 12px;
                color: #7dd3fc;
            }

            QLabel#recommendationMeta {
                font-size: 12px;
                color: #d7e3f8;
            }

            QLabel#recommendationNote {
                font-size: 12px;
                color: #cbd5e1;
                background-color: rgba(15, 23, 42, 55);
                border-radius: 10px;
                padding: 8px;
            }

            QPushButton {
                background-color: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2563eb,
                    stop:0.45 #06b6d4,
                    stop:1 #7c3aed
                );
                color: white;
                border: 1px solid rgba(255, 255, 255, 36);
                border-radius: 12px;
                padding: 12px 16px;
                font-weight: 700;
            }

            QPushButton:hover {
                border: 1px solid rgba(180, 220, 255, 120);
            }

            QPushButton:pressed {
                background-color: #1d4ed8;
            }

            QPushButton:disabled {
                background-color: rgba(60, 70, 90, 120);
                color: rgba(200, 210, 225, 0.65);
                border: 1px solid rgba(148, 163, 184, 35);
            }

            QPushButton#secondaryButton {
                background-color: rgba(15, 23, 42, 85);
                border: 1px solid rgba(125, 211, 252, 100);
                color: #dbeafe;
                padding: 10px 14px;
            }

            QPushButton#secondaryButton:hover {
                background-color: rgba(30, 41, 59, 120);
            }

            QTextEdit {
                background-color: rgba(8, 15, 30, 88);
                border: 1px solid rgba(120, 170, 255, 72);
                border-radius: 14px;
                padding: 10px;
                color: #eef4ff;
                selection-background-color: #2563eb;
            }

            QTextEdit#logBox, QTextEdit#chatBox, QTextEdit#promptBox {
                font-size: 13px;
            }

            QScrollArea {
                border: none;
                background: transparent;
            }

            QScrollArea#mainScroll {
                background: transparent;
                border: none;
            }

            QWidget#contentWidget {
                background: transparent;
            }

            QScrollBar:vertical {
                background: rgba(8, 15, 30, 90);
                width: 10px;
                margin: 4px;
                border-radius: 5px;
            }

            QScrollBar::handle:vertical {
                background: rgba(125, 211, 252, 150);
                min-height: 40px;
                border-radius: 5px;
            }

            QScrollBar::handle:vertical:hover {
                background: rgba(125, 211, 252, 220);
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: none;
                border: none;
            }
        """)

    def update_ollama_status(self):
        if check_ollama_running():
            self.status_badge.setText("● OLLAMA ONLINE")
            self.status_badge.setStyleSheet("""
                QLabel {
                    font-size: 12px;
                    font-weight: 700;
                    color: #dcfce7;
                    padding: 8px 14px;
                    background-color: rgba(20, 83, 45, 130);
                    border: 1px solid rgba(74, 222, 128, 120);
                    border-radius: 14px;
                    min-width: 150px;
                }
            """)
            add_glow(self.status_badge, "#22c55e", blur=24)
        else:
            self.status_badge.setText("● OLLAMA OFFLINE")
            self.status_badge.setStyleSheet("""
                QLabel {
                    font-size: 12px;
                    font-weight: 700;
                    color: #fee2e2;
                    padding: 8px 14px;
                    background-color: rgba(127, 29, 29, 130);
                    border: 1px solid rgba(248, 113, 113, 120);
                    border-radius: 14px;
                    min-width: 150px;
                }
            """)
            add_glow(self.status_badge, "#ef4444", blur=24)

    def show_ollama_guide_dialog(self):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("未检测到 Ollama")
        msg.setText("当前没有检测到 Ollama 正在运行。")
        msg.setInformativeText("你可以尝试自动启动；如果尚未安装，请打开 Ollama 下载页。")

        auto_btn = msg.addButton("自动尝试启动", QMessageBox.AcceptRole)
        download_btn = msg.addButton("打开下载页", QMessageBox.ActionRole)
        msg.addButton("取消", QMessageBox.RejectRole)

        msg.exec()
        clicked = msg.clickedButton()

        if clicked == auto_btn:
            self.result_box.append("")
            self.result_box.append("=== 尝试自动启动 Ollama ===")
            ok = try_start_ollama(timeout=20)
            self.update_ollama_status()

            if ok:
                self.result_box.append("Ollama 已成功启动。")
                self.result_box.append("")
                QMessageBox.information(self, "启动成功", "Ollama 已成功启动。")
                return True

            self.result_box.append("自动启动失败。")
            self.result_box.append("")
            QMessageBox.information(
                self,
                "启动失败",
                "没有成功自动启动 Ollama。\n\n如果尚未安装，请点击“打开下载页”完成安装。"
            )
            return False

        if clicked == download_btn:
            open_ollama_download_page()
            QMessageBox.information(
                self,
                "已打开下载页",
                "已为你打开 Ollama 下载页面。\n\n安装并启动完成后，回到程序重新点击相关按钮即可。"
            )
            return False

        return False

    def ensure_ollama_ready(self):
        self.update_ollama_status()
        if check_ollama_running():
            return True
        return self.show_ollama_guide_dialog()

    def handle_ollama_assist(self):
        self.update_ollama_status()
        if check_ollama_running():
            QMessageBox.information(self, "Ollama 已就绪", "当前已检测到 Ollama 正在运行。")
            return
        self.show_ollama_guide_dialog()

    def set_hardware_summary(self, hardware: dict):
        self.os_metric.update_value(hardware.get("os", "--"))
        self.cpu_metric.update_value(f"{hardware.get('cpu_cores_logical', '--')} 线程")
        self.ram_metric.update_value(f"{hardware.get('ram_gb', '--')} GB")

        gpus = hardware.get("gpus", [])
        if gpus:
            gpu_names = ", ".join(g.get("name", "GPU") for g in gpus)
            self.gpu_metric.update_value(gpu_names)
        else:
            self.gpu_metric.update_value("无独显 / 未检测到 NVIDIA GPU")

    def clear_recommendation_cards(self):
        while self.rec_layout.count():
            item = self.rec_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def render_recommendations(self, recommendations):
        self.clear_recommendation_cards()
        self.recommendation_cards = []

        if not recommendations:
            empty = QLabel("没有找到适合当前机器的推荐模型。")
            empty.setObjectName("emptyHint")
            empty.setWordWrap(True)
            self.rec_layout.addWidget(empty)
            self.rec_layout.addStretch()
            return

        for item in recommendations:
            card = RecommendationCard(item, self.select_recommendation)
            self.recommendation_cards.append(card)
            self.rec_layout.addWidget(card)

        self.rec_layout.addStretch()

    def select_recommendation(self, item):
        self.current_model = item
        self.current_model_label.setText(
            f"当前模型：{item['display_name']}  |  {item['deploy_id']}"
        )
        self.deploy_button.setEnabled(True)
        self.chat_button.setEnabled(True)

        for card in self.recommendation_cards:
            card.set_selected(card.item["deploy_id"] == item["deploy_id"])

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
            QMessageBox.critical(self, "扫描失败", f"扫描或推荐过程中出现错误：\n{e}")
            return

        self.recommendations = recommendations
        self.current_model = None
        self.current_model_label.setText("当前模型：未选择")
        self.deploy_button.setEnabled(False)
        self.chat_button.setEnabled(False)
        self.chat_box.clear()

        self.set_hardware_summary(hardware)
        self.render_recommendations(recommendations)

        output_lines = []
        output_lines.append("=== 硬件信息 ===")
        output_lines.append(json.dumps(hardware, ensure_ascii=False, indent=2))
        output_lines.append("")
        output_lines.append("=== 推荐结果 ===")

        if recommendations:
            for item in recommendations:
                output_lines.append(f"模型名称: {item['display_name']}")
                output_lines.append(f"部署标签: {item['deploy_id']}")
                output_lines.append(f"模型家族: {item['family']}")
                output_lines.append(f"最近官方模型: {item['source_model_id']}")
                output_lines.append(f"最近更新时间: {item['last_modified']}")
                output_lines.append(f"说明: {item['notes']}")
                output_lines.append("-" * 40)

            self.select_recommendation(recommendations[0])
        else:
            output_lines.append("没有找到适合当前机器的推荐模型。")

        self.result_box.setPlainText("\n".join(output_lines))
        self.update_ollama_status()

    def handle_deploy(self):
        if not self.ensure_ollama_ready():
            return

        if not self.current_model:
            QMessageBox.information(self, "未选择模型", "请先选择一个推荐模型。")
            return

        model_id = self.current_model["deploy_id"]

        self.result_box.append("")
        self.result_box.append(f"=== 开始部署 {model_id} ===")

        try:
            result = ensure_model_installed(model_id)
        except Exception as e:
            QMessageBox.critical(self, "部署失败", f"部署模型时出现错误：\n{e}")
            self.result_box.append("=== 部署失败 ===")
            self.result_box.append(str(e))
            self.result_box.append("")
            return

        self.result_box.append("=== 部署结果 ===")
        self.result_box.append(json.dumps(result, ensure_ascii=False, indent=2))
        self.result_box.append("")

        QMessageBox.information(self, "部署完成", f"{model_id} 已完成检查/部署。")

    def handle_chat(self):
        if not self.ensure_ollama_ready():
            return

        if not self.current_model:
            self.chat_box.setPlainText("请先选择一个推荐模型。")
            return

        model_id = self.current_model["deploy_id"]
        prompt = self.prompt_box.toPlainText().strip()

        if not prompt:
            self.chat_box.setPlainText("请输入测试问题。")
            return

        self.chat_box.setPlainText(f"正在调用 {model_id} ...")

        try:
            reply = generate_text(model_id, prompt)
        except Exception as e:
            QMessageBox.critical(self, "调用失败", f"调用模型时出现错误：\n{e}")
            self.chat_box.setPlainText(f"调用失败：{e}")
            return

        self.chat_box.setPlainText(reply)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())