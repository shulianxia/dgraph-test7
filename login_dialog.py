#!/usr/bin/env python3
"""
test7 — 用户登录对话框
卡片式用户选择界面
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QWidget, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect
from theme import (
    COLOR_BORDER, COLOR_CARD, COLOR_PRIMARY, COLOR_PRIMARY_LIGHT,
    COLOR_TEXT_DIM, COLOR_TAG_ADMIN, COLOR_TAG_USER, COLOR_TAG_GUEST,
    COLOR_LAYER_CLIENT, COLOR_LAYER_COORDINATOR, COLOR_LAYER_WORKER,
    LAYER_LABELS, LAYER_NAMES,
    FONT_UI, FONT_SIZE_SMALL, make_login_stylesheet,
)

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ── 预置用户数据 ──
# layer: client=客户端层, coordinator=协调层(管理员层), worker=Worker 层
PRESET_USERS = [
    {
        "id": "admin",
        "name": "管理员",
        "avatar": "[S]",
        "role": "管理员",
        "role_tag": "admin",
        "layer": "coordinator",
        "desc": "系统管理 · 完全权限 · 全图查询",
        "color": "#ef4444",
    },
    {
        "id": "shulianxia",
        "name": "shulianxia",
        "avatar": "[C]",
        "role": "开发者",
        "role_tag": "user",
        "layer": "worker",
        "desc": "开发维护 · 高级分析 · 系统调优",
        "color": "#a78bfa",
    },
    {
        "id": "alice",
        "name": "Alice",
        "avatar": "[D]",
        "role": "分析师",
        "role_tag": "user",
        "layer": "client",
        "desc": "数据分析 · 图查询 · 统计报表",
        "color": "#60a5fa",
    },
    {
        "id": "bob",
        "name": "Bob",
        "avatar": "[G]",
        "role": "运维",
        "role_tag": "user",
        "layer": "coordinator",
        "desc": "系统运维 · 节点管理 · 状态监控",
        "color": "#34d399",
    },
    {
        "id": "charlie",
        "name": "Charlie",
        "avatar": "[V]",
        "role": "访客",
        "role_tag": "guest",
        "layer": "client",
        "desc": "只读访问 · 基础查询 · 查看统计",
        "color": "#94a3b8",
    },
]


class UserCard(QWidget):
    """单个用户卡片"""
    clicked = pyqtSignal(dict)

    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = user
        self._setup_ui()
        self._selected = False

    def _setup_ui(self):
        self.setObjectName("user_card")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(180, 200)
        self.setStyleSheet(f"""
            QWidget#user_card {{
                background: {COLOR_CARD};
                border: 2px solid transparent;
                border-radius: 12px;
            }}
            QWidget#user_card:hover {{
                border: 2px solid {COLOR_PRIMARY};
                background: #28284a;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)

        # 头像
        avatar = QLabel(self.user["avatar"])
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setFixedSize(56, 56)
        avatar.setStyleSheet(f"""
            font-size: 32px;
            background: #1a1a35;
            border: 2px solid {self.user['color']};
            border-radius: 28px;
        """)
        layout.addWidget(avatar, 0, Qt.AlignCenter)

        # 用户名
        name = QLabel(self.user["name"])
        name.setAlignment(Qt.AlignCenter)
        name.setStyleSheet("font-size: 15px; font-weight: bold; color: #e2e8f0;")
        name.setWordWrap(True)
        layout.addWidget(name, 0, Qt.AlignCenter)

        # 角色标签
        role = QLabel(self.user["role"])
        role.setAlignment(Qt.AlignCenter)
        if self.user["role_tag"] == "admin":
            bg = COLOR_TAG_ADMIN
        elif self.user["role_tag"] == "guest":
            bg = COLOR_TAG_GUEST
        else:
            bg = COLOR_TAG_USER
        role.setStyleSheet(f"""
            background: {bg}; color: white;
            border-radius: 10px; padding: 2px 12px;
            font-size: 11px;
        """)
        role.setFixedHeight(22)
        layout.addWidget(role, 0, Qt.AlignCenter)

        # 层级标签
        layer = QLabel(LAYER_LABELS.get(self.user["layer"], self.user["layer"]))
        layer.setAlignment(Qt.AlignCenter)
        layer_color = {
            "client": COLOR_LAYER_CLIENT,
            "coordinator": COLOR_LAYER_COORDINATOR,
            "worker": COLOR_LAYER_WORKER,
        }.get(self.user["layer"], COLOR_TEXT_DIM)
        layer.setStyleSheet(f"""
            color: {layer_color};
            font-size: 10px;
            font-weight: bold;
            border: 1px solid {layer_color};
            border-radius: 8px;
            padding: 1px 8px;
        """)
        layer.setFixedHeight(18)
        layout.addWidget(layer, 0, Qt.AlignCenter)

        # 描述
        desc = QLabel(self.user["desc"])
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"font-size: 11px; color: {COLOR_TEXT_DIM};")
        layout.addWidget(desc, 0, Qt.AlignCenter)

    def mousePressEvent(self, event):
        self.clicked.emit(self.user)
        super().mousePressEvent(event)

    def set_selected(self, selected):
        self._selected = selected
        if selected:
            self.setStyleSheet(f"""
                QWidget#user_card {{
                    background: #28284a;
                    border: 2px solid {COLOR_PRIMARY};
                    border-radius: 12px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QWidget#user_card {{
                    background: {COLOR_CARD};
                    border: 2px solid transparent;
                    border-radius: 12px;
                }}
                QWidget#user_card:hover {{
                    border: 2px solid {COLOR_PRIMARY};
                    background: #28284a;
                }}
            """)


class LoginDialog(QDialog):
    """登录对话框 — 卡片式用户选择"""
    login_accepted = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_user = None
        self._cards = []
        self._setup_ui()
        self.setStyleSheet(make_login_stylesheet())

    def _setup_ui(self):
        self.setWindowTitle("分布式图查询系统 - 登录")
        self.setFixedSize(520, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(10)

        # 标题
        title = QLabel("[G] 分布式图查询系统")
        title.setObjectName("login_title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 副标题
        subtitle = QLabel("请选择用户以继续")
        subtitle.setObjectName("login_subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(10)

        # 用户卡片网格 (3列)
        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setAlignment(Qt.AlignCenter)

        row, col = 0, 0
        for user in PRESET_USERS:
            card = UserCard(user)
            card.clicked.connect(self._on_card_clicked)
            self._cards.append(card)
            grid.addWidget(card, row, col)
            col += 1
            if col == 3:
                col = 0
                row += 1

        # 如果少于3个加一行，居中处理
        grid_widget = QWidget()
        grid_widget.setLayout(grid)
        layout.addWidget(grid_widget, 0, Qt.AlignCenter)

        layout.addStretch(1)

        # 登录按钮
        self.login_btn = QPushButton("[K]  选择用户后点击登录")
        self.login_btn.setObjectName("login_btn")
        self.login_btn.setEnabled(False)
        self.login_btn.clicked.connect(self._on_login)
        layout.addWidget(self.login_btn, 0, Qt.AlignCenter)

    def _on_card_clicked(self, user):
        self.selected_user = user
        for card in self._cards:
            card.set_selected(card.user["id"] == user["id"])
        self.login_btn.setText(f"[K]  以 {user['name']} ({user['role']}) 登录")
        self.login_btn.setEnabled(True)

    def _on_login(self):
        if self.selected_user:
            self.login_accepted.emit(self.selected_user)
            self.accept()
