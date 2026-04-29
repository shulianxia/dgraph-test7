#!/usr/bin/env python3
"""
test7 — 主题定义
颜色、字体、样式表
"""

# ── 颜色 ──
COLOR_BG = "#0f0f1a"              # 最深底色
COLOR_SURFACE = "#1a1a2e"         # 面板背景
COLOR_CARD = "#22223a"            # 卡片背景
COLOR_BORDER = "#2d2d4f"          # 边框
COLOR_BORDER_FOCUS = "#7c3aed"    # 聚焦边框

# 渐变主色（紫色→蓝色）
COLOR_PRIMARY = "#7c3aed"         # 紫色主色
COLOR_PRIMARY_LIGHT = "#a78bfa"   # 紫色亮色
COLOR_SECONDARY = "#3b82f6"       # 蓝色辅色
COLOR_SECONDARY_LIGHT = "#60a5fa" # 蓝色亮色
COLOR_ACCENT = "#f97316"          # 橙色强调（顶栏装饰）

# 功能按钮色
COLOR_BTN_INFO = "#7c3aed"        # 紫色-查看节点
COLOR_BTN_NEIGHBOR = "#0891b2"    # 青色-查询邻居
COLOR_BTN_COMMON = "#059669"      # 绿色-共同邻居
COLOR_BTN_TRIANGLE = "#d97706"    # 橙色-三角计数
COLOR_BTN_STATS = "#6366f1"       # 靛色-全图统计
COLOR_BTN_SEARCH = "#8b5cf6"      # 紫罗兰-搜索

# 文字
COLOR_TEXT = "#e2e8f0"
COLOR_TEXT_DIM = "#94a3b8"
COLOR_TEXT_MUTED = "#64748b"
COLOR_SUCCESS = "#22c55e"
COLOR_WARN = "#f59e0b"
COLOR_ERROR = "#ef4444"
COLOR_INFO = "#3b82f6"

# 特殊标记色
COLOR_NODE_HIGHLIGHT = "#fbbf24"  # 节点高亮
COLOR_TAG_ADMIN = "#ef4444"       # 管理员标签
COLOR_TAG_USER = "#3b82f6"        # 用户标签
COLOR_TAG_GUEST = "#94a3b8"       # 访客标签

# ── 三层架构层级色 ──
COLOR_LAYER_CLIENT = "#60a5fa"      # 客户端层 — 蓝色
COLOR_LAYER_COORDINATOR = "#ef4444" # 协调层(管理员层) — 红色
COLOR_LAYER_WORKER = "#34d399"      # Worker 层 — 绿色
LAYER_LABELS = {
    "client": "Client Layer",
    "coordinator": "Coordinator Layer",
    "worker": "Worker Layer",
}
LAYER_NAMES = {
    "client": "客户端层",
    "coordinator": "协调层(管理员层)",
    "worker": "Worker 层",
}

# 层级权限定义：每层可用的查询方法
LAYER_PERMISSIONS = {
    "client": ["get_node_info", "get_neighbors"],
    "coordinator": ["get_node_info", "get_neighbors", "get_common", "get_triangles", "get_stats"],
    "worker": ["get_node_info", "get_neighbors", "get_common", "get_triangles", "get_stats"],
}

# ── 字体 ──
FONT_MONO = "JetBrains Mono, Fira Code, Consolas, 'Noto Sans Mono CJK SC', monospace"
FONT_UI = "'Noto Sans CJK SC', 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
FONT_SIZE_TITLE = 20
FONT_SIZE_BODY = 13
FONT_SIZE_SMALL = 11

# ── 阴影、圆角 ──
RADIUS_CARD = "12px"
RADIUS_BTN = "8px"
RADIUS_INPUT = "8px"
RADIUS_TAG = "10px"


def make_stylesheet():
    """生成主界面完整样式表"""
    return f"""
    /* ── 全局 ── */
    QMainWindow, QDialog {{
        background: {COLOR_BG};
    }}
    QWidget {{
        background: transparent;
        color: {COLOR_TEXT};
        font-family: {FONT_UI};
        font-size: {FONT_SIZE_BODY}px;
    }}
    QWidget#topBar {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #7c3aed, stop:0.5 #3b82f6, stop:1 #0891b2);
        border-radius: 0px;
        min-height: 48px;
        max-height: 48px;
    }}
    QWidget#topBar QLabel {{
        color: white;
        font-weight: bold;
        font-size: 14px;
    }}

    /* ── GroupBox（功能面板卡片） ── */
    QGroupBox {{
        background: {COLOR_CARD};
        border: 1px solid {COLOR_BORDER};
        border-radius: {RADIUS_CARD};
        margin-top: 14px;
        padding: 14px 10px 10px 10px;
        font-weight: bold;
        font-size: 13px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        color: {COLOR_PRIMARY_LIGHT};
    }}

    /* ── 输入框 ── */
    QLineEdit {{
        background: {COLOR_SURFACE};
        border: 1px solid {COLOR_BORDER};
        border-radius: {RADIUS_INPUT};
        padding: 8px 12px;
        font-size: 13px;
        font-family: {FONT_MONO};
        color: {COLOR_TEXT};
        selection-background-color: {COLOR_PRIMARY};
    }}
    QLineEdit:focus {{
        border: 1px solid {COLOR_BORDER_FOCUS};
        background: #1e1e34;
    }}
    QLineEdit::placeholder {{
        color: {COLOR_TEXT_MUTED};
    }}

    /* ── 按钮 ── */
    QPushButton {{
        color: white;
        border: none;
        border-radius: {RADIUS_BTN};
        padding: 8px 16px;
        font-size: 13px;
        font-weight: bold;
        min-height: 18px;
    }}
    QPushButton:hover {{
        opacity: 0.9;
    }}
    QPushButton:pressed {{
        padding-top: 10px;
        padding-bottom: 6px;
    }}
    QPushButton:disabled {{
        background: #3a3a5a !important;
        color: #6a6a8a;
    }}

    /* 各功能按钮颜色 */
    QPushButton#btn_info {{ background: {COLOR_BTN_INFO}; }}
    QPushButton#btn_info:hover {{ background: #6d28d9; }}
    QPushButton#btn_neighbor {{ background: {COLOR_BTN_NEIGHBOR}; }}
    QPushButton#btn_neighbor:hover {{ background: #0e7490; }}
    QPushButton#btn_common {{ background: {COLOR_BTN_COMMON}; }}
    QPushButton#btn_common:hover {{ background: #047857; }}
    QPushButton#btn_triangle {{ background: {COLOR_BTN_TRIANGLE}; }}
    QPushButton#btn_triangle:hover {{ background: #b45309; }}
    QPushButton#btn_stats {{ background: {COLOR_BTN_STATS}; }}
    QPushButton#btn_stats:hover {{ background: #4f46e5; }}
    QPushButton#btn_search {{ background: {COLOR_BTN_SEARCH}; }}
    QPushButton#btn_search:hover {{ background: #7c3aed; }}

    /* 次要按钮（清空、切换用户） */
    QPushButton#btn_secondary {{
        background: transparent;
        border: 1px solid {COLOR_BORDER};
        color: {COLOR_TEXT_DIM};
        padding: 6px 14px;
        font-size: 12px;
    }}
    QPushButton#btn_secondary:hover {{
        background: {COLOR_CARD};
        border-color: {COLOR_TEXT_DIM};
        color: {COLOR_TEXT};
    }}

    /* ── 文本区域 ── */
    QTextEdit {{
        background: {COLOR_SURFACE};
        border: 1px solid {COLOR_BORDER};
        border-radius: {RADIUS_CARD};
        padding: 12px;
        font-family: {FONT_MONO};
        font-size: 13px;
        color: {COLOR_TEXT};
        selection-background-color: {COLOR_PRIMARY};
    }}
    QTextEdit:focus {{
        border: 1px solid {COLOR_BORDER_FOCUS};
    }}

    /* ── 标签页 ── */
    QTabWidget::pane {{
        border: 1px solid {COLOR_BORDER};
        border-radius: {RADIUS_CARD};
        background: {COLOR_SURFACE};
        top: -1px;
    }}
    QTabBar::tab {{
        background: {COLOR_BG};
        color: {COLOR_TEXT_DIM};
        border: 1px solid {COLOR_BORDER};
        border-bottom: none;
        border-radius: 6px 6px 0 0;
        padding: 6px 16px;
        margin-right: 2px;
        font-size: 12px;
    }}
    QTabBar::tab:selected {{
        background: {COLOR_SURFACE};
        color: {COLOR_PRIMARY_LIGHT};
        font-weight: bold;
    }}

    /* ── 状态栏 ── */
    QStatusBar {{
        background: {COLOR_SURFACE};
        border-top: 1px solid {COLOR_BORDER};
        color: {COLOR_TEXT_DIM};
        font-size: 12px;
    }}
    QStatusBar QLabel {{
        color: {COLOR_TEXT_DIM};
        padding: 0 6px;
    }}

    /* ── 分割器 ── */
    QSplitter::handle {{
        background: {COLOR_BORDER};
        width: 2px;
    }}

    /* ── 列表 ── */
    QListWidget {{
        background: {COLOR_SURFACE};
        border: 1px solid {COLOR_BORDER};
        border-radius: {RADIUS_CARD};
        padding: 4px;
        font-size: 12px;
        color: {COLOR_TEXT_DIM};
    }}
    QListWidget::item {{
        padding: 6px 10px;
        border-radius: 4px;
    }}
    QListWidget::item:hover {{
        background: {COLOR_CARD};
        color: {COLOR_TEXT};
    }}
    QListWidget::item:selected {{
        background: {COLOR_PRIMARY};
        color: white;
    }}

    /* ── 滚动条 ── */
    QScrollBar:vertical {{
        background: {COLOR_SURFACE};
        width: 8px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: {COLOR_BORDER};
        border-radius: 4px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {COLOR_TEXT_MUTED};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    """


def make_login_stylesheet():
    """生成登录页面的独特样式"""
    return f"""
    QDialog {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #0f0f1a, stop:0.5 #15152a, stop:1 #1a0a2e);
    }}
    QLabel#login_title {{
        font-size: 26px;
        font-weight: bold;
        color: white;
    }}
    QLabel#login_subtitle {{
        font-size: 13px;
        color: {COLOR_TEXT_DIM};
    }}
    QLabel#user_avatar {{
        font-size: 40px;
        background: {COLOR_CARD};
        border: 2px solid {COLOR_BORDER};
        border-radius: 24px;
        min-width: 64px;
        min-height: 64px;
        max-width: 64px;
        max-height: 64px;
        qproperty-alignment: AlignCenter;
    }}
    QWidget#user_card {{
        background: {COLOR_CARD};
        border: 2px solid transparent;
        border-radius: 12px;
    }}
    QWidget#user_card:hover {{
        border: 2px solid {COLOR_PRIMARY};
        background: #28284a;
    }}
    QWidget#user_card_selected {{
        background: #28284a;
        border: 2px solid {COLOR_PRIMARY};
        border-radius: 12px;
    }}
    QLabel#user_name {{
        font-size: 15px;
        font-weight: bold;
        color: {COLOR_TEXT};
    }}
    QLabel#user_role {{
        font-size: 11px;
        border-radius: {RADIUS_TAG};
        padding: 2px 10px;
    }}
    QLabel#user_role_admin {{
        background: {COLOR_TAG_ADMIN};
        color: white;
        font-size: 11px;
        border-radius: {RADIUS_TAG};
        padding: 2px 10px;
    }}
    QLabel#user_role_user {{
        background: {COLOR_TAG_USER};
        color: white;
        font-size: 11px;
        border-radius: {RADIUS_TAG};
        padding: 2px 10px;
    }}
    QLabel#user_role_guest {{
        background: {COLOR_TAG_GUEST};
        color: #1a1a2e;
        font-size: 11px;
        border-radius: {RADIUS_TAG};
        padding: 2px 10px;
    }}
    QPushButton#login_btn {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #7c3aed, stop:1 #3b82f6);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 30px;
        font-size: 14px;
        font-weight: bold;
        min-width: 160px;
        min-height: 20px;
    }}
    QPushButton#login_btn:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #6d28d9, stop:1 #2563eb);
    }}
    QPushButton#login_btn:pressed {{
        padding-top: 12px;
        padding-bottom: 8px;
    }}
    """
