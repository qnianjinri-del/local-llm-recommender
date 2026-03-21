import sys
import json
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QObject, QThread, Signal
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
    QComboBox,
    QProgressDialog,
)

from detector import get_hardware_info
from online_catalog import load_recent_supported_models_with_fallback
from recommender import recommend_from_recent_models
from ollama_backend import (
    check_ollama_running,
    download_ollama_installer,
    generate_text,
    is_model_installed,
    launch_ollama_installer,
    pull_model_stream,
    try_start_ollama,
)


def add_glow(widget, color="#60a5fa", blur=28, x_offset=0, y_offset=0):
    effect = QGraphicsDropShadowEffect()
    effect.setBlurRadius(blur)
    effect.setOffset(x_offset, y_offset)
    effect.setColor(QColor(color))
    widget.setGraphicsEffect(effect)


def format_bytes(num_bytes):
    if num_bytes is None:
        return "--"

    value = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024


class OllamaInstallerDownloadWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            def _progress(downloaded, total):
                if total > 0:
                    percent = max(0, min(100, int(downloaded * 100 / total)))
                    text = f"正在下载 Ollama 安装器... {percent}%（{format_bytes(downloaded)} / {format_bytes(total)}）"
                else:
                    percent = -1
                    text = f"正在下载 Ollama 安装器... {format_bytes(downloaded)}"
                self.progress.emit(percent, text)

            path = download_ollama_installer(
                progress_callback=_progress,
                stop_check=lambda: self._cancelled,
            )

            if self._cancelled:
                self.error.emit("已取消 Ollama 安装器下载。")
                return

            self.finished.emit(path)
        except Exception as e:
            self.error.emit(str(e))


class ModelPullWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, model_id: str):
        super().__init__()
        self.model_id = model_id
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            if is_model_installed(self.model_id):
                self.progress.emit(100, "模型已存在，无需重复下载。")
                self.finished.emit({
                    "status": "already_installed",
                    "model": self.model_id,
                })
                return

            def _status(status, payload):
                completed = payload.get("completed")
                total = payload.get("total")

                if completed is not None and total:
                    percent = max(0, min(100, int(completed * 100 / total)))
                    detail = f"{status or '正在下载模型'}（{format_bytes(completed)} / {format_bytes(total)}）"
                else:
                    percent = -1
                    detail = status or "正在准备下载模型..."

                self.progress.emit(percent, detail)

            result = pull_model_stream(
                self.model_id,
                status_callback=_status,
                cancel_check=lambda: self._cancelled,
            )

            if self._cancelled:
                self.error.emit("已取消模型下载。")
                return

            self.progress.emit(100, "模型下载完成。")
            self.finished.emit({
                "status": "downloaded",
                "model": self.model_id,
                "detail": result,
            })
        except Exception as e:
            self.error.emit(str(e))


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

        title = QLabel(item["family_display_name"])
        title.setObjectName("recommendationTitle")

        title2 = QLabel(f"当前推荐参数：{item.get('current_param', '--')}")
        title2.setObjectName("recommendationSubTitle")

        top_badge_text = item.get("top_badge", "")
        if top_badge_text:
            top_badge = QLabel(top_badge_text)
            top_badge.setObjectName("recommendationTopBadge")
        else:
            top_badge = None

        summary_tag_text = item.get("summary_tag", "")
        if summary_tag_text:
            summary_tag = QLabel(summary_tag_text)
            summary_tag.setObjectName("recommendationTag")
        else:
            summary_tag = None

        freshness_badge_text = item.get("freshness_badge", "")
        if freshness_badge_text:
            freshness_badge = QLabel(freshness_badge_text)
            freshness_badge.setObjectName("recommendationFreshnessBadge")
        else:
            freshness_badge = None

        subtitle = QLabel(item["deploy_id"])
        subtitle.setObjectName("recommendationSubTitle")

        family = QLabel(f"模型标识：{item['family']}")
        family.setObjectName("recommendationMeta")

        source = QLabel(f"最近官方模型：{item['source_model_id']}")
        source.setObjectName("recommendationMeta")
        source.setWordWrap(True)

        updated = QLabel(f"最近更新时间：{item['last_modified']}")
        updated.setObjectName("recommendationMeta")
        updated.setWordWrap(True)

        score_label = QLabel(f"推荐分数：{item.get('score', 'N/A')}")
        score_label.setObjectName("recommendationMeta")

        param_section = QLabel("参数档位")
        param_section.setObjectName("sectionLabel")

        param_all = QLabel(f"这个家族的参数：{item.get('all_params_text', '--')}")
        param_all.setObjectName("recommendationMeta")
        param_all.setWordWrap(True)

        param_fit = QLabel(f"适合你的电脑：{item.get('suitable_params_text', '--')}")
        param_fit.setObjectName("recommendationMeta")
        param_fit.setWordWrap(True)

        param_try = QLabel(f"可尝试：{item.get('tryable_params_text', '--')}")
        param_try.setObjectName("recommendationMeta")
        param_try.setWordWrap(True)

        param_avoid = QLabel(f"暂不建议：{item.get('avoid_params_text', '--')}")
        param_avoid.setObjectName("recommendationMeta")
        param_avoid.setWordWrap(True)

        runtime_section = QLabel("运行体验")
        runtime_section.setObjectName("sectionLabel")

        runtime_feel = QLabel(f"体验判断：{item.get('runtime_feel', '--')}")
        runtime_feel.setObjectName("recommendationMeta")

        runtime_note = QLabel(f"体验说明：{item.get('runtime_note', '')}")
        runtime_note.setObjectName("recommendationMeta")
        runtime_note.setWordWrap(True)

        deploy_level = QLabel(f"部署门槛：{item.get('deploy_level', '--')}")
        deploy_level.setObjectName("recommendationMeta")

        reason_label = QLabel(f"推荐理由：{item.get('reason', '')}")
        reason_label.setObjectName("recommendationMeta")
        reason_label.setWordWrap(True)

        not_recommended = QLabel(f"为什么没推荐更大参数：{item.get('not_recommended_explanation', '')}")
        not_recommended.setObjectName("recommendationNote")
        not_recommended.setWordWrap(True)

        deploy_tip = QLabel(f"部署提示：{item.get('deploy_tip', '')}")
        deploy_tip.setObjectName("recommendationNote")
        deploy_tip.setWordWrap(True)

        notes = QLabel(f"推荐说明：{item.get('notes', '')}")
        notes.setObjectName("recommendationNote")
        notes.setWordWrap(True)

        select_btn = QPushButton("设为当前模型")
        select_btn.setObjectName("secondaryButton")
        select_btn.clicked.connect(lambda: self.on_select(self.item))

        layout.addWidget(title)
        layout.addWidget(title2)
        if top_badge:
            layout.addWidget(top_badge)
        if summary_tag:
            layout.addWidget(summary_tag)
        if freshness_badge:
            layout.addWidget(freshness_badge)
        layout.addWidget(subtitle)
        layout.addWidget(family)
        layout.addWidget(source)
        layout.addWidget(updated)
        layout.addWidget(score_label)
        layout.addWidget(param_section)
        layout.addWidget(param_all)
        layout.addWidget(param_fit)
        layout.addWidget(param_try)
        layout.addWidget(param_avoid)
        layout.addWidget(runtime_section)
        layout.addWidget(runtime_feel)
        layout.addWidget(runtime_note)
        layout.addWidget(deploy_level)
        layout.addWidget(reason_label)
        layout.addWidget(not_recommended)
        layout.addWidget(deploy_tip)
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

        self.ollama_download_thread = None
        self.ollama_download_worker = None
        self.ollama_download_dialog = None

        self.model_pull_thread = None
        self.model_pull_worker = None
        self.model_pull_dialog = None

        self.install_check_timer = QTimer(self)
        self.install_check_timer.timeout.connect(self.check_ollama_post_install)
        self.install_check_attempts = 0
        self._last_model_pull_text = ""

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

        preference_row = QHBoxLayout()
        preference_row.setSpacing(10)

        preference_label = QLabel("推荐偏好：")
        preference_label.setObjectName("sectionLabel")

        self.preference_combo = QComboBox()
        self.preference_combo.setObjectName("preferenceCombo")
        self.preference_combo.addItem("平衡推荐", "balanced")
        self.preference_combo.addItem("速度优先", "speed")
        self.preference_combo.addItem("能力优先", "capability")

        preference_row.addWidget(preference_label)
        preference_row.addWidget(self.preference_combo, 1)

        sort_row = QHBoxLayout()
        sort_row.setSpacing(10)

        sort_label = QLabel("排序方式：")
        sort_label.setObjectName("sectionLabel")

        self.sort_combo = QComboBox()
        self.sort_combo.setObjectName("preferenceCombo")
        self.sort_combo.addItem("综合推荐", "overall")
        self.sort_combo.addItem("更轻量优先", "lightweight")
        self.sort_combo.addItem("更强能力优先", "capability")
        self.sort_combo.addItem("更新更近优先", "freshness")

        sort_row.addWidget(sort_label)
        sort_row.addWidget(self.sort_combo, 1)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        self.scan_button = QPushButton("开始扫描并推荐")
        self.scan_button.clicked.connect(self.handle_scan)
        add_glow(self.scan_button, "#3b82f6", blur=26)

        self.ollama_button = QPushButton("检测 / 启动 Ollama")
        self.ollama_button.setObjectName("secondaryButton")
        self.ollama_button.clicked.connect(self.handle_ollama_assist)

        self.install_ollama_button = QPushButton("下载安装 Ollama")
        self.install_ollama_button.setObjectName("secondaryButton")
        self.install_ollama_button.clicked.connect(self.start_ollama_installer_download)

        button_row.addWidget(self.scan_button, 2)
        button_row.addWidget(self.ollama_button, 1)
        button_row.addWidget(self.install_ollama_button, 1)

        self.current_model_label = QLabel("当前模型：未选择\n参数建议：请先完成扫描并从右侧选择一个推荐模型。\n运行体验：扫描后会显示更直观的体验判断。")
        self.current_model_label.setObjectName("currentModelLabel")
        self.current_model_label.setWordWrap(True)

        self.catalog_mode_label = QLabel("模型来源：尚未扫描")
        self.catalog_mode_label.setObjectName("catalogModeLabel")
        self.catalog_mode_label.setWordWrap(True)

        self.limit_explain_label = QLabel("参数上限解释：完成扫描后，这里会说明为什么更大的参数没有被优先推荐。")
        self.limit_explain_label.setObjectName("limitExplainLabel")
        self.limit_explain_label.setWordWrap(True)

        self.deploy_button = QPushButton("一键部署当前模型")
        self.deploy_button.setEnabled(False)
        self.deploy_button.clicked.connect(self.handle_deploy)
        add_glow(self.deploy_button, "#7c3aed", blur=24)

        action_card.layout.addLayout(preference_row)
        action_card.layout.addLayout(sort_row)
        action_card.layout.addLayout(button_row)
        action_card.layout.addWidget(self.current_model_label)
        action_card.layout.addWidget(self.catalog_mode_label)
        action_card.layout.addWidget(self.limit_explain_label)
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

            QLabel#catalogModeLabel {
                font-size: 12px;
                color: #dbeafe;
                background-color: rgba(15, 23, 42, 68);
                border: 1px solid rgba(125, 211, 252, 60);
                border-radius: 12px;
                padding: 10px;
            }

            QLabel#limitExplainLabel {
                font-size: 12px;
                color: #e2e8f0;
                background-color: rgba(30, 41, 59, 88);
                border: 1px solid rgba(250, 204, 21, 70);
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

            QLabel#recommendationTopBadge {
                font-size: 11px;
                font-weight: 800;
                color: #ecfeff;
                background-color: rgba(34, 197, 94, 0.28);
                border: 1px solid rgba(74, 222, 128, 0.75);
                border-radius: 10px;
                padding: 5px 10px;
                max-width: 90px;
            }

            QLabel#recommendationTag {
                font-size: 11px;
                font-weight: 700;
                color: #dbeafe;
                background-color: rgba(37, 99, 235, 0.25);
                border: 1px solid rgba(96, 165, 250, 0.75);
                border-radius: 10px;
                padding: 5px 10px;
                max-width: 90px;
            }

            QLabel#recommendationFreshnessBadge {
                font-size: 11px;
                font-weight: 800;
                color: #fff7ed;
                background-color: rgba(249, 115, 22, 0.22);
                border: 1px solid rgba(251, 146, 60, 0.78);
                border-radius: 10px;
                padding: 5px 10px;
                max-width: 90px;
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

            QComboBox#preferenceCombo {
                background-color: rgba(8, 15, 30, 88);
                border: 1px solid rgba(120, 170, 255, 72);
                border-radius: 12px;
                padding: 8px 12px;
                min-height: 22px;
                color: #eef4ff;
            }

            QComboBox#preferenceCombo:hover {
                border: 1px solid rgba(180, 220, 255, 120);
            }

            QComboBox#preferenceCombo::drop-down {
                border: none;
                width: 28px;
                background: transparent;
            }

            QComboBox#preferenceCombo QAbstractItemView {
                background-color: rgba(8, 15, 30, 235);
                color: #eef4ff;
                border: 1px solid rgba(120, 170, 255, 110);
                selection-background-color: rgba(37, 99, 235, 180);
                outline: 0;
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
        msg.setInformativeText("你可以尝试自动启动；如果尚未安装，可以直接在这里下载安装 Ollama。")

        auto_btn = msg.addButton("自动尝试启动", QMessageBox.AcceptRole)
        download_btn = msg.addButton("下载安装 Ollama", QMessageBox.ActionRole)
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
                "没有成功自动启动 Ollama。\n\n如果尚未安装，请点击“下载安装 Ollama”继续。"
            )
            return False

        if clicked == download_btn:
            self.start_ollama_installer_download()
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

    def _close_progress_dialog(self, dialog_attr_name):
        dialog = getattr(self, dialog_attr_name, None)
        if dialog is not None:
            dialog.close()
            dialog.deleteLater()
            setattr(self, dialog_attr_name, None)

    def _cleanup_thread_worker(self, thread_attr_name, worker_attr_name):
        thread = getattr(self, thread_attr_name, None)
        if thread is not None:
            thread.quit()
            thread.wait()
            setattr(self, thread_attr_name, None)
        setattr(self, worker_attr_name, None)

    def request_cancel_ollama_download(self):
        worker = self.ollama_download_worker
        dialog = self.ollama_download_dialog
        if worker is not None:
            worker.cancel()
        if dialog is not None:
            dialog.setLabelText("正在取消 Ollama 安装器下载，请稍候...")
            dialog.setCancelButton(None)

    def request_cancel_model_download(self):
        worker = self.model_download_worker
        dialog = self.model_download_dialog
        if worker is not None:
            worker.cancel()
        if dialog is not None:
            dialog.setLabelText("正在取消模型下载，请稍候...")
            dialog.setCancelButton(None)

    def start_ollama_installer_download(self):
        if self.ollama_download_thread is not None:
            QMessageBox.information(self, "正在下载", "Ollama 安装器正在下载中，请稍候。")
            return

        self.result_box.append("")
        self.result_box.append("=== 开始下载 Ollama 安装器 ===")

        dialog = QProgressDialog("正在下载 Ollama 安装器...", "取消", 0, 100, self)
        dialog.setWindowTitle("下载安装 Ollama")
        dialog.setWindowModality(Qt.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.show()
        self.ollama_download_dialog = dialog

        thread = QThread(self)
        worker = OllamaInstallerDownloadWorker()
        worker.moveToThread(thread)

        worker.progress.connect(self.on_ollama_installer_download_progress)
        worker.finished.connect(self.on_ollama_installer_download_finished)
        worker.error.connect(self.on_ollama_installer_download_error)
        dialog.canceled.connect(self.request_cancel_ollama_download)
        thread.started.connect(worker.run)

        self.ollama_download_thread = thread
        self.ollama_download_worker = worker
        thread.start()

    def on_ollama_installer_download_progress(self, percent: int, text: str):
        dialog = self.ollama_download_dialog
        if dialog is None:
            return

        dialog.setLabelText(text)
        if percent < 0:
            dialog.setRange(0, 0)
        else:
            if dialog.maximum() == 0:
                dialog.setRange(0, 100)
            dialog.setValue(percent)

    def on_ollama_installer_download_finished(self, installer_path: str):
        self._close_progress_dialog("ollama_download_dialog")
        self._cleanup_thread_worker("ollama_download_thread", "ollama_download_worker")

        self.result_box.append(f"Ollama 安装器下载完成：{installer_path}")

        try:
            launch_ollama_installer(installer_path)
        except Exception as e:
            QMessageBox.critical(self, "启动安装器失败", f"安装器已经下载完成，但无法自动启动：\n{e}")
            return

        self.result_box.append("已启动 Ollama 安装器，请在弹出的安装窗口中完成安装。")
        self.result_box.append("程序将自动轮询 Ollama 是否已安装并启动。")
        self.result_box.append("")

        self.install_check_attempts = 0
        self.install_check_timer.start(3000)

        QMessageBox.information(
            self,
            "安装器已启动",
            "Ollama 安装器已下载并启动。\n\n请在弹出的安装窗口中完成安装，本软件会自动检测安装结果。",
        )

    def on_ollama_installer_download_error(self, error_text: str):
        self._close_progress_dialog("ollama_download_dialog")
        self._cleanup_thread_worker("ollama_download_thread", "ollama_download_worker")

        if "取消" in error_text:
            self.result_box.append("已取消 Ollama 安装器下载。")
            self.result_box.append("")
            return

        self.result_box.append(f"Ollama 安装器下载失败：{error_text}")
        self.result_box.append("")
        QMessageBox.critical(self, "下载失败", f"下载 Ollama 安装器时出现错误：\n{error_text}")

    def check_ollama_post_install(self):
        self.install_check_attempts += 1

        if check_ollama_running() or try_start_ollama(timeout=2):
            self.install_check_timer.stop()
            self.update_ollama_status()
            self.result_box.append("已检测到 Ollama 安装完成并成功启动。")
            self.result_box.append("")
            QMessageBox.information(self, "安装完成", "已经检测到 Ollama 安装并启动成功。")
            return

        if self.install_check_attempts >= 40:
            self.install_check_timer.stop()
            self.update_ollama_status()
            self.result_box.append("暂时还没有检测到 Ollama 启动。你可以完成安装后，再点击“检测 / 启动 Ollama”。")
            self.result_box.append("")

    def start_model_download_with_progress(self, model_id: str):
        if self.model_pull_thread is not None:
            QMessageBox.information(self, "正在部署", "当前已有模型正在下载/部署，请稍候。")
            return

        self._last_model_pull_text = ""
        dialog = QProgressDialog(f"正在准备部署 {model_id} ...", "取消", 0, 100, self)
        dialog.setWindowTitle("部署模型")
        dialog.setWindowModality(Qt.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.show()
        self.model_pull_dialog = dialog

        thread = QThread(self)
        worker = ModelPullWorker(model_id)
        worker.moveToThread(thread)

        worker.progress.connect(self.on_model_pull_progress)
        worker.finished.connect(self.on_model_pull_finished)
        worker.error.connect(self.on_model_pull_error)
        dialog.canceled.connect(self.request_cancel_model_download)
        thread.started.connect(worker.run)

        self.model_pull_thread = thread
        self.model_pull_worker = worker
        thread.start()

    def on_model_pull_progress(self, percent: int, text: str):
        dialog = self.model_pull_dialog
        if dialog is None:
            return

        dialog.setLabelText(text)
        if percent < 0:
            dialog.setRange(0, 0)
        else:
            if dialog.maximum() == 0:
                dialog.setRange(0, 100)
            dialog.setValue(percent)

        if text and text != self._last_model_pull_text:
            self.result_box.append(text)
            self._last_model_pull_text = text

    def on_model_pull_finished(self, result: dict):
        self._close_progress_dialog("model_pull_dialog")
        self._cleanup_thread_worker("model_pull_thread", "model_pull_worker")

        self.result_box.append("=== 部署结果 ===")
        self.result_box.append(json.dumps(result, ensure_ascii=False, indent=2))
        self.result_box.append("")

        QMessageBox.information(self, "部署完成", f"{result.get('model', '--')} 已完成检查/部署。")

    def on_model_pull_error(self, error_text: str):
        self._close_progress_dialog("model_pull_dialog")
        self._cleanup_thread_worker("model_pull_thread", "model_pull_worker")

        if "取消" in error_text:
            self.result_box.append("已取消模型下载。")
            self.result_box.append("")
            QMessageBox.information(self, "已取消", "已取消当前模型下载。")
            return

        self.result_box.append("=== 部署失败 ===")
        self.result_box.append(error_text)
        self.result_box.append("")
        QMessageBox.critical(self, "部署失败", f"部署模型时出现错误：\n{error_text}")

    def set_catalog_mode_label(self, mode: str, message: str = ""):
        mode_text_map = {
            "online": "模型来源：在线最新列表",
            "cache": "模型来源：本地缓存",
            "offline": "模型来源：离线内置目录",
        }
        title = mode_text_map.get(mode, "模型来源：未知")
        if message:
            self.catalog_mode_label.setText(f"{title}\n{message}")
        else:
            self.catalog_mode_label.setText(title)

    def build_catalog_log_lines(self, catalog_state: dict):
        lines = []
        mode = catalog_state.get("mode", "unknown")
        message = catalog_state.get("message", "")
        error = catalog_state.get("error", "")

        lines.append("=== 模型来源 ===")
        lines.append(f"来源模式: {mode}")
        if message:
            lines.append(f"说明: {message}")
        if error:
            lines.append(f"在线失败原因: {error}")
        lines.append("")
        return lines

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

        lines = [f"当前模型：{item['family_display_name']}  |  {item['deploy_id']}"]
        lines.append(f"当前推荐参数：{item.get('current_param', '--')}")
        lines.append(f"适合你的电脑：{item.get('suitable_params_text', '无')}")
        if item.get("runtime_feel"):
            lines.append(f"运行体验：{item['runtime_feel']}")
        if item.get("runtime_note"):
            lines.append(f"体验说明：{item['runtime_note']}")
        if item.get("summary_tag"):
            lines.append(f"推荐标签：{item['summary_tag']}")
        if item.get("freshness_badge"):
            lines.append(f"新鲜度标签：{item['freshness_badge']}")
        if item.get("deploy_level"):
            lines.append(f"部署门槛：{item['deploy_level']}")
        if item.get("deploy_tip"):
            lines.append(f"部署提示：{item['deploy_tip']}")
        if item.get("not_recommended_explanation"):
            lines.append(f"更大参数说明：{item['not_recommended_explanation']}")

        self.current_model_label.setText("\n".join(lines))
        if item.get("limit_summary"):
            explain_text = f"参数上限解释：{item['limit_summary']}"
            if item.get("limit_examples_text"):
                explain_text += f"\n{item['limit_examples_text']}"
            self.limit_explain_label.setText(explain_text)
        self.deploy_button.setEnabled(True)
        self.chat_button.setEnabled(True)

        for card in self.recommendation_cards:
            card.set_selected(card.item["deploy_id"] == item["deploy_id"])

    def handle_scan(self):
        if not self.ensure_ollama_ready():
            return

        try:
            hardware = get_hardware_info()
            catalog_state = load_recent_supported_models_with_fallback(limit_per_family=8)
            recent_models = catalog_state["models"]
            user_preference = self.preference_combo.currentData()
            sort_mode = self.sort_combo.currentData()
            recommendations = recommend_from_recent_models(
                recent_models,
                hardware,
                category="general",
                user_preference=user_preference,
                sort_mode=sort_mode,
                top_n=8,
            )
        except Exception as e:
            QMessageBox.critical(self, "扫描失败", f"扫描或推荐过程中出现错误：\n{e}")
            return

        self.recommendations = recommendations
        self.current_model = None
        self.current_model_label.setText("当前模型：未选择\n参数建议：请先从推荐列表里选择一个模型。\n运行体验：选择模型后显示。")
        self.limit_explain_label.setText("参数上限解释：完成扫描后，这里会说明为什么更大的参数没有被优先推荐。")
        self.deploy_button.setEnabled(False)
        self.chat_button.setEnabled(False)
        self.chat_box.clear()

        self.set_hardware_summary(hardware)
        self.set_catalog_mode_label(catalog_state.get("mode", "unknown"), catalog_state.get("message", ""))
        self.render_recommendations(recommendations)

        output_lines = []
        output_lines.append("=== 硬件信息 ===")
        output_lines.append(json.dumps(hardware, ensure_ascii=False, indent=2))
        output_lines.append("")
        output_lines.extend(self.build_catalog_log_lines(catalog_state))
        output_lines.append("=== 推荐结果 ===")
        output_lines.append(f"当前推荐偏好: {user_preference}")
        output_lines.append(f"当前排序方式: {sort_mode}")
        output_lines.append("")

        if recommendations:
            for item in recommendations:
                output_lines.append(f"模型家族: {item['family_display_name']}")
                output_lines.append(f"部署标签: {item['deploy_id']}")
                output_lines.append(f"当前推荐参数: {item.get('current_param', '--')}")
                output_lines.append(f"模型标识: {item['family']}")
                output_lines.append(f"最近官方模型: {item['source_model_id']}")
                output_lines.append(f"最近更新时间: {item['last_modified']}")
                if item.get("top_badge"):
                    output_lines.append(f"首选标签: {item['top_badge']}")
                if item.get("summary_tag"):
                    output_lines.append(f"推荐标签: {item['summary_tag']}")
                if item.get("freshness_badge"):
                    output_lines.append(f"新鲜度标签: {item['freshness_badge']}")
                output_lines.append(f"这个家族的参数: {item.get('all_params_text', '--')}")
                output_lines.append(f"适合你的电脑: {item.get('suitable_params_text', '--')}")
                output_lines.append(f"可尝试: {item.get('tryable_params_text', '--')}")
                output_lines.append(f"暂不建议: {item.get('avoid_params_text', '--')}")
                if item.get("runtime_feel"):
                    output_lines.append(f"运行体验: {item['runtime_feel']}")
                if item.get("runtime_note"):
                    output_lines.append(f"体验说明: {item['runtime_note']}")
                if item.get("deploy_level"):
                    output_lines.append(f"部署门槛: {item['deploy_level']}")
                if item.get("deploy_tip"):
                    output_lines.append(f"部署提示: {item['deploy_tip']}")
                if item.get("not_recommended_explanation"):
                    output_lines.append(f"为什么没推荐更大参数: {item['not_recommended_explanation']}")
                output_lines.append(f"参数建议:\n{item.get('tier_advice_text', '')}")
                output_lines.append(f"说明: {item['notes']}")
                output_lines.append("-" * 40)

            if recommendations[0].get("limit_summary"):
                output_lines.append("=== 参数上限解释 ===")
                output_lines.append(recommendations[0]["limit_summary"])
                output_lines.append(recommendations[0].get("limit_examples_text", ""))
                output_lines.append("")

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
        confirm_text = "\n".join([
            f"模型家族：{self.current_model.get('family_display_name', '--')}",
            f"当前推荐参数：{self.current_model.get('current_param', '--')}",
            f"预计下载体积：{self.current_model.get('download_size_gb', '--')}GB",
            f"部署门槛：{self.current_model.get('deploy_level', '--')}",
            f"适合你的电脑：{self.current_model.get('suitable_params_text', '--')}",
            f"运行体验：{self.current_model.get('runtime_feel', '--')}",
            "",
            f"体验说明：{self.current_model.get('runtime_note', '')}",
            f"部署提示：{self.current_model.get('deploy_tip', '')}",
            f"更大参数说明：{self.current_model.get('not_recommended_explanation', '')}",
        ])
        reply = QMessageBox.question(
            self,
            "确认部署",
            confirm_text,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return

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