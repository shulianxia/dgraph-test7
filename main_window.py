#!/usr/bin/env python3
"""
test7 — 主界面
功能面板 + 结果展示 + 状态栏
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QGroupBox,
    QTabWidget, QListWidget, QListWidgetItem, QSplitter,
    QStatusBar, QFrame, QSizePolicy, QAbstractItemView
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPalette, QColor

from theme import (
    COLOR_BG, COLOR_SURFACE, COLOR_CARD, COLOR_BORDER,
    COLOR_PRIMARY, COLOR_PRIMARY_LIGHT, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED,
    COLOR_SUCCESS, COLOR_WARN, COLOR_ERROR, COLOR_NODE_HIGHLIGHT,
    COLOR_BTN_INFO, COLOR_BTN_NEIGHBOR, COLOR_BTN_COMMON, COLOR_BTN_TRIANGLE, COLOR_BTN_STATS,
    COLOR_LAYER_CLIENT, COLOR_LAYER_COORDINATOR, COLOR_LAYER_WORKER,
    LAYER_LABELS, LAYER_NAMES, LAYER_PERMISSIONS,
    FONT_MONO, make_stylesheet,
)
from rpc_client import DGraphClient, QueryThread, StatusPoller
from login_dialog import LoginDialog

import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class HistoryEntry:
    """单条历史记录"""
    def __init__(self, method, params, result_summary, timestamp=None):
        self.method = method
        self.params = params
        self.result_summary = result_summary
        self.timestamp = timestamp or time.strftime("%H:%M:%S")
        self.full_result = ""

    def title(self):
        labels = {
            "get_node_info": "[i] 节点信息",
            "get_neighbors": "[~] 邻居查询",
            "get_common": "[&] 共同邻居",
            "get_triangles": "[△] 三角计数",
            "get_stats": "[#] 全图统计",
        }
        label = labels.get(self.method, self.method)
        return f"[{self.timestamp}] {label} {self.params}"


class MainWindow(QMainWindow):
    """主界面窗口"""

    METHODS_INFO = {
        "get_node_info": {
            "label": "[i] 节点信息", "color": COLOR_BTN_INFO,
            "desc": "查看单个节点的 ID、度、所属分区",
            "args": [{"name": "节点ID", "ph": "输入节点编号 (0~N-1)"}],
        },
        "get_neighbors": {
            "label": "[~] 邻居查询", "color": COLOR_BTN_NEIGHBOR,
            "desc": "查询目标节点的所有邻居节点",
            "args": [{"name": "节点ID", "ph": "输入节点编号"}],
        },
        "get_common": {
            "label": "[&] 共同邻居", "color": COLOR_BTN_COMMON,
            "desc": "查找两个节点之间的共同邻居",
            "args": [
                {"name": "节点A", "ph": "节点A编号"},
                {"name": "节点B", "ph": "节点B编号"},
            ],
        },
        "get_triangles": {
            "label": "[△] 三角计数", "color": COLOR_BTN_TRIANGLE,
            "desc": "统计包含指定节点的三角形数量（留空则全图统计）",
            "args": [{"name": "节点ID (可选)", "ph": "不填则统计全图"}],
        },
        "get_stats": {
            "label": "[#] 全图统计", "color": COLOR_BTN_STATS,
            "desc": "显示全图节点数、边数、三角形数、分区信息",
            "args": [],
        },
    }

    def __init__(self, user_data):
        super().__init__()
        self.user = user_data
        self.client = DGraphClient()
        self._history = []  # List[HistoryEntry]
        self._method_widgets = {}  # 保存当前查询方法对应的输入控件
        self._setup_ui()
        self._apply_theme()
        self._setup_poller()
        self._update_status_user()
        self._apply_layer_permissions()
        self.setWindowTitle("分布式图查询系统")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # UI 搭建
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── 顶栏 ──
        main_layout.addWidget(self._build_top_bar())

        # ── 主体 ──
        body = QSplitter(Qt.Horizontal)
        body.setHandleWidth(2)

        left_panel = self._build_left_panel()
        right_panel = self._build_right_panel()

        body.addWidget(left_panel)
        body.addWidget(right_panel)
        body.setStretchFactor(0, 2)
        body.setStretchFactor(1, 3)

        main_layout.addWidget(body, 1)

        # ── 状态栏 ──
        self._build_status_bar()

    def _build_top_bar(self):
        bar = QWidget()
        bar.setObjectName("topBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)

        icon = QLabel("⬡")
        icon.setStyleSheet("font-size: 18px;")
        layout.addWidget(icon)

        title = QLabel("分布式图查询系统  ·  Distributed Graph Query")
        layout.addWidget(title)

        layout.addStretch(1)

        # 系统状态指示
        self._status_indicator = QLabel("● 正在连接...")
        self._status_indicator.setStyleSheet("color: #f59e0b; font-size: 12px;")
        layout.addWidget(self._status_indicator)

        return bar

    def _build_left_panel(self):
        """左侧：功能卡片"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 6, 12)
        layout.setSpacing(8)

        scroll_wrapper = QWidget()
        scroll_layout = QVBoxLayout(scroll_wrapper)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(8)

        for method_name, info in self.METHODS_INFO.items():
            card = self._build_method_card(method_name, info)
            scroll_layout.addWidget(card)

        scroll_layout.addStretch(1)

        # 限高滚动
        from PyQt5.QtWidgets import QScrollArea
        sa = QScrollArea()
        sa.setWidget(scroll_wrapper)
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.NoFrame)
        sa.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ width: 6px; }}
        """)
        layout.addWidget(sa)

        return panel

    def _build_method_card(self, method_name, info):
        """构造功能卡片 GroupBox"""
        grp = QGroupBox(info["label"])
        grp.setToolTip(info["desc"])
        layout = QVBoxLayout(grp)
        layout.setSpacing(8)

        inputs = []
        for arg in info["args"]:
            hbox = QHBoxLayout()
            lbl = QLabel(arg["name"])
            lbl.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 12px; min-width: 70px;")
            edit = QLineEdit()
            edit.setPlaceholderText(arg["ph"])
            edit.setMinimumWidth(120)
            hbox.addWidget(lbl)
            hbox.addWidget(edit, 1)
            layout.addLayout(hbox)
            inputs.append(edit)

        btn = QPushButton(info["label"].split(" ")[1] if " " in info["label"] else info["label"])
        btn.setObjectName("btn_" + method_name.replace("get_", ""))
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda checked, m=method_name, i=inputs: self._on_query(m, i))
        layout.addWidget(btn)

        # 存引用以便后续使用
        self._method_widgets[method_name] = {
            "group": grp,
            "inputs": inputs,
            "button": btn,
        }

        return grp

    def _build_right_panel(self):
        """右侧：结果 + 历史标签页"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 12, 12, 12)
        layout.setSpacing(8)

        # 标题
        title = QLabel("[>] 查询结果")
        title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {COLOR_PRIMARY_LIGHT};")
        layout.addWidget(title)

        # 结果输出
        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        self.result_area.setPlaceholderText("选择左侧功能后点击查询按钮...")
        layout.addWidget(self.result_area, 1)

        # 历史标题
        hdr = QHBoxLayout()
        hist_title = QLabel("[*] 查询历史")
        hist_title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {COLOR_PRIMARY_LIGHT};")
        hdr.addWidget(hist_title)

        clear_btn = QPushButton("清空")
        clear_btn.setObjectName("btn_secondary")
        clear_btn.clicked.connect(self._clear_history)
        hdr.addWidget(clear_btn)

        layout.addLayout(hdr)

        self.history_list = QListWidget()
        self.history_list.setAlternatingRowColors(True)
        self.history_list.itemDoubleClicked.connect(self._on_history_double_click)
        layout.addWidget(self.history_list)

        return panel

    def _build_status_bar(self):
        status = self.statusBar()

        # 用户信息
        self._lbl_user = QLabel()
        status.addWidget(self._lbl_user)

        # 层级指示
        self._lbl_layer = QLabel()
        status.addWidget(self._lbl_layer)

        # 状态项
        self._lbl_coord = QLabel("● Coordinator: --")
        self._lbl_coord.setStyleSheet(f"color: {COLOR_TEXT_DIM};")
        status.addPermanentWidget(self._lbl_coord)

        self._lbl_workers = QLabel("● Workers: --")
        self._lbl_workers.setStyleSheet(f"color: {COLOR_TEXT_DIM};")
        status.addPermanentWidget(self._lbl_workers)

        self._lbl_nodes = QLabel("● 节点: --")
        self._lbl_nodes.setStyleSheet(f"color: {COLOR_TEXT_DIM};")
        status.addPermanentWidget(self._lbl_nodes)

        # 切换用户
        switch_btn = QPushButton("[@] 切换用户")
        switch_btn.setObjectName("btn_secondary")
        switch_btn.clicked.connect(self._on_switch_user)
        status.addPermanentWidget(switch_btn)

    def _apply_theme(self):
        self.setStyleSheet(make_stylesheet())

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 用户切换
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _on_switch_user(self):
        dialog = LoginDialog(self)
        if dialog.exec_() == LoginDialog.Accepted and dialog.selected_user:
            self.user = dialog.selected_user
            self._update_status_user()
            self._apply_layer_permissions()
            self._append_result("system",
                f'<div style="padding: 8px;">'
                f'[~] 已切换至用户：<b>{self.user["name"]}</b> '
                f'({self.user["role"]}) '
                f'· <span style="color: #60a5fa;">{LAYER_NAMES.get(self.user["layer"], "")}</span>'
                f'</div>')

    def _update_status_user(self):
        color = self.user.get("color", COLOR_PRIMARY)
        self._lbl_user.setText(
            f'[@] {self.user["avatar"]} {self.user["name"]}  ·  {self.user["role"]}'
        )
        self._lbl_user.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 12px;")

        # 更新层级指示
        layer = self.user.get("layer", "client")
        layer_color = {
            "client": COLOR_LAYER_CLIENT,
            "coordinator": COLOR_LAYER_COORDINATOR,
            "worker": COLOR_LAYER_WORKER,
        }.get(layer, COLOR_TEXT_DIM)
        layer_name = LAYER_NAMES.get(layer, layer)
        self._lbl_layer.setText(f"[≡] {layer_name}")
        self._lbl_layer.setStyleSheet(
            f"color: {layer_color}; font-weight: bold; font-size: 11px;"
        )

    def _apply_layer_permissions(self):
        """根据当前用户的层级启用/禁用查询按钮"""
        layer = self.user.get("layer", "client")
        allowed = LAYER_PERMISSIONS.get(layer, [])

        for method_name, widgets in self._method_widgets.items():
            btn = widgets["button"]
            grp = widgets["group"]
            if method_name in allowed:
                btn.setEnabled(True)
                grp.setToolTip(grp.toolTip().split(" [")[0])
            else:
                btn.setEnabled(False)
                btn.setText(f"[x] 无权限")
                grp.setToolTip(f"{grp.toolTip()} [当前层级无权限]")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 查询执行
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _on_query(self, method_name, inputs):
        """发起查询"""
        args = [edit.text().strip() for edit in inputs]
        params_str = ", ".join(a for a in args if a)

        # 验证输入
        if method_name != "get_stats":
            for a in args:
                if a and not a.isdigit():
                    self._append_error(f"节点ID必须为数字，收到: '{a}'")
                    return

        int_args = [int(a) for a in args if a]

        # 客户端方法
        method_map = {
            "get_node_info": ("get_node_info", int_args[0] if int_args else 0),
            "get_neighbors": ("get_neighbors", int_args[0] if int_args else 0),
            "get_common": ("get_common", int_args[0] if len(int_args) > 0 else 0,
                           int_args[1] if len(int_args) > 1 else 0),
            "get_triangles": ("get_triangles", int_args[0] if int_args else None),
            "get_stats": ("get_stats",),
        }

        method, *call_args = method_map[method_name]

        # 禁用按钮
        self._method_widgets[method_name]["button"].setEnabled(False)
        self._method_widgets[method_name]["button"].setText("[.] 查询中...")

        # 启动后台线程
        self._current_result_cache = {}  # 用于历史记录
        self.thread = QueryThread(self.client, method, *call_args)
        self.thread.finished.connect(
            lambda m, data, mn=method_name, ps=params_str: self._on_result(mn, ps, m, data)
        )
        self.thread.error.connect(
            lambda err, mn=method_name: self._on_error(mn, err)
        )
        self.thread.finished.connect(lambda: self._reenable_button(method_name))
        self.thread.error.connect(lambda: self._reenable_button(method_name))
        self.thread.start()

    def _reenable_button(self, method_name):
        if method_name in self._method_widgets:
            btn = self._method_widgets[method_name]["button"]
            btn.setEnabled(True)
            label = self.METHODS_INFO[method_name]["label"].split(" ")[1]
            btn.setText(label)

    def _on_result(self, method_name, params_str, rpc_method, data):
        """查询成功"""
        html = self._format_result(method_name, data)
        self.result_area.setHtml(html)
        self._add_history(method_name, params_str or data.get("label", ""), html)

    def _on_error(self, method_name, error_msg):
        self._append_error(f"[X] 查询失败: {error_msg}")

    def _append_result(self, method, text):
        self.result_area.append(text)

    def _append_error(self, text):
        self.result_area.setHtml(
            f'<div style="color: {COLOR_ERROR}; padding: 16px;">'
            f'<b>[X] 错误</b><br>{text}</div>'
        )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 结果格式化
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _format_result(self, method_name, data):
        """将查询数据格式化为 HTML"""
        lines = []
        title = self.METHODS_INFO[method_name]["label"]
        lines.append(f'<h3 style="color: {COLOR_PRIMARY_LIGHT}; margin-bottom: 12px;">{title}</h3>')

        if method_name == "get_node_info":
            lines.append(self._fmt_node_info(data))
        elif method_name == "get_neighbors":
            lines.append(self._fmt_neighbors(data))
        elif method_name == "get_common":
            lines.append(self._fmt_common(data))
        elif method_name == "get_triangles":
            lines.append(self._fmt_triangles(data))
        elif method_name == "get_stats":
            lines.append(self._fmt_stats(data))

        # 时间戳
        lines.append(
            f'<hr style="border-color: {COLOR_BORDER}; margin-top: 16px;">'
            f'<span style="color: {COLOR_TEXT_MUTED}; font-size: 11px;">'
            f'查询时间: {time.strftime("%Y-%m-%d %H:%M:%S")}</span>'
        )

        return "".join(lines)

    def _fmt_node_info(self, data):
        node_id = data.get("id", "?")
        degree = data.get("degree", "?")
        partition = data.get("partition", "?")
        neighbors = data.get("neighbors", data.get("neighbor_list", []))

        lines = [
            f'<div style="background: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; '
            f'border-radius: 8px; padding: 16px; margin: 8px 0;">',
            f'<table style="width: 100%; border-collapse: collapse;">',
            self._fmt_row("🆔 节点ID", f'<b style="color: {COLOR_NODE_HIGHLIGHT};">{node_id}</b>'),
            self._fmt_row("[~] 度数", f'<b style="color: {COLOR_PRIMARY_LIGHT};">{degree}</b>'),
            self._fmt_row("[D] 所属分区", f'<b>Partition {partition}</b>'),
            '</table>',
        ]

        if neighbors:
            n_str = ", ".join(str(n) for n in neighbors[:20])
            if len(neighbors) > 20:
                n_str += f" ... 共 {len(neighbors)} 个"
            lines.append(
                f'<div style="margin-top: 8px; padding-top: 8px; '
                f'border-top: 1px solid {COLOR_BORDER};">'
                f'<span style="color: {COLOR_TEXT_DIM};">邻居: </span>'
                f'<span style="font-family: {FONT_MONO}; font-size: 12px;">{n_str}</span></div>'
            )

        lines.append('</div>')
        return "".join(lines)

    def _fmt_neighbors(self, data):
        node_id = data.get("node", data.get("id", "?"))
        neighbors = data.get("neighbors", data.get("neighbor_list", []))

        if not neighbors:
            return f'<div style="color: {COLOR_WARN}; padding: 12px;">节点 {node_id} 没有邻居</div>'

        lines = [
            f'<div style="background: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; '
            f'border-radius: 8px; padding: 16px; margin: 8px 0;">',
            f'<div style="margin-bottom: 8px;">节点 <b style="color: {COLOR_NODE_HIGHLIGHT};">{node_id}</b> '
            f'共有 <b style="color: {COLOR_PRIMARY_LIGHT};">{len(neighbors)}</b> 个邻居</div>',
            '<div>',
        ]

        # 每行最多显示 10 个，用表格布局（Qt HTML 引擎不支持 flexbox）
        cols_per_row = 10
        lines.append('<table style="width: 100%; border-collapse: collapse;">')
        for i, n in enumerate(neighbors):
            if i % cols_per_row == 0:
                lines.append('<tr>')
            lines.append(
                f'<td style="background: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; '
                f'border-radius: 4px; padding: 2px 6px; font-family: {FONT_MONO}; '
                f'font-size: 12px; text-align: center; white-space: nowrap;">{n}</td>'
            )
            if i % cols_per_row == cols_per_row - 1 or i == len(neighbors) - 1:
                lines.append('</tr>')
        lines.append('</table>')

        lines.append('</div></div>')
        return "".join(lines)

    def _fmt_common(self, data):
        a = data.get("a", data.get("node_a", "?"))
        b = data.get("b", data.get("node_b", "?"))
        common = data.get("common", data.get("common_list", []))

        if not common:
            return (
                f'<div style="color: {COLOR_WARN}; padding: 12px;">'
                f'节点 {a} 和 {b} 之间没有共同邻居</div>'
            )

        lines = [
            f'<div style="background: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; '
            f'border-radius: 8px; padding: 16px; margin: 8px 0;">',
            f'<div style="margin-bottom: 8px;">节点 <b style="color: {COLOR_NODE_HIGHLIGHT};">{a}</b> 和 '
            f'<b style="color: {COLOR_NODE_HIGHLIGHT};">{b}</b> '
            f'共有 <b style="color: {COLOR_PRIMARY_LIGHT};">{len(common)}</b> 个共同邻居</div>',
            '<div>',
        ]

        cols_per_row = 10
        lines.append('<table style="width: 100%; border-collapse: collapse;">')
        for i, n in enumerate(common):
            if i % cols_per_row == 0:
                lines.append('<tr>')
            lines.append(
                f'<td style="background: {COLOR_SURFACE}; border: 1px solid {COLOR_SUCCESS}; '
                f'border-radius: 4px; padding: 2px 6px; font-family: {FONT_MONO}; '
                f'font-size: 12px; text-align: center; white-space: nowrap;">{n}</td>'
            )
            if i % cols_per_row == cols_per_row - 1 or i == len(common) - 1:
                lines.append('</tr>')
        lines.append('</table>')

        lines.append('</div></div>')
        return "".join(lines)

    def _fmt_triangles(self, data):
        count = data.get("count", data.get("triangle_count", data.get("triangles", 0)))

        lines = [
            f'<div style="background: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; '
            f'border-radius: 8px; padding: 16px; margin: 8px 0;">',
            f'<div style="font-size: 48px; text-align: center; margin: 8px 0;">△</div>',
        ]

        # 带节点或不带的标题
        node_id = data.get("node", data.get("node_id", "?"))
        if "node" in data or "node_id" in data:
            lines.append(
                f'<div style="text-align: center; font-size: 15px;">'
                f'包含节点 <b style="color: {COLOR_NODE_HIGHLIGHT};">{node_id}</b> 的三角形数: '
                f'<b style="color: {COLOR_SUCCESS}; font-size: 22px;">{count}</b></div>'
            )
        else:
            lines.append(
                f'<div style="text-align: center; font-size: 15px;">'
                f'全图三角形总数: '
                f'<b style="color: {COLOR_SUCCESS}; font-size: 22px;">{count}</b></div>'
            )

        lines.append('</div>')
        return "".join(lines)

    def _fmt_stats(self, data):
        nodes = data.get("nodes", data.get("node_count", data.get("num_nodes", "?")))
        edges = data.get("edges", data.get("edge_count", data.get("num_edges", "?")))
        triangles = data.get("triangles", data.get("triangle_count", data.get("num_triangles", "?")))
        partitions = data.get("partitions", data.get("partition_count", data.get("num_parts", data.get("num_workers", "?"))))

        lines = [
            f'<div style="background: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; '
            f'border-radius: 8px; padding: 16px; margin: 8px 0;">',
            '<table style="width: 100%; border-collapse: collapse;">',
            self._fmt_row("N 节点总数", f'<b style="font-size: 16px; color: {COLOR_NODE_HIGHLIGHT};">{nodes}</b>'),
            self._fmt_row("E 边总数", f'<b style="font-size: 16px; color: {COLOR_PRIMARY_LIGHT};">{edges}</b>'),
            self._fmt_row("A 三角形数", f'<b style="font-size: 16px; color: {COLOR_SUCCESS};">{triangles}</b>'),
            self._fmt_row("P 分区数", str(partitions)),
            '</table>',
        ]

        # 如果有分区详情
        if isinstance(partitions, (list, dict)):
            lines.append(
                f'<div style="margin-top: 8px; padding-top: 8px; '
                f'border-top: 1px solid {COLOR_BORDER}; color: {COLOR_TEXT_DIM};">'
                f'分区详情: {json.dumps(partitions, ensure_ascii=False)}</div>'
            )

        lines.append('</div>')
        return "".join(lines)

    @staticmethod
    def _fmt_row(label, value):
        return (
            f'<tr><td style="color: {COLOR_TEXT_DIM}; padding: 6px 12px; '
            f'white-space: nowrap; width: 100px;">{label}</td>'
            f'<td style="padding: 6px 12px;">{value}</td></tr>'
        )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 查询历史
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _add_history(self, method_name, params_str, html_result):
        entry = HistoryEntry(method_name, params_str, "")
        entry.full_result = html_result

        self._history.append(entry)
        if len(self._history) > 20:
            self._history.pop(0)

        # 更新列表
        item = QListWidgetItem(entry.title())
        item.setData(Qt.UserRole, len(self._history) - 1)
        self.history_list.addItem(item)
        self.history_list.scrollToBottom()

    def _on_history_double_click(self, item):
        idx = item.data(Qt.UserRole)
        if idx is not None and idx < len(self._history):
            entry = self._history[idx]
            self.result_area.setHtml(entry.full_result)

    def _clear_history(self):
        self._history.clear()
        self.history_list.clear()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 状态轮询
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _setup_poller(self):
        self.poller = StatusPoller(self.client, interval=10)
        self.poller.status_updated.connect(self._on_status_update)
        self.poller.connection_lost.connect(self._on_connection_lost)
        self.poller.start()

        # 启动后立即请求一次
        QTimer.singleShot(500, self._update_status_now)

    def _update_status_now(self):
        stats = self.client.get_stats()
        if "error" not in stats:
            self._on_status_update(stats)

    def _on_status_update(self, stats):
        nodes = stats.get("num_nodes", stats.get("nodes", stats.get("node_count", "?")))
        edges = stats.get("num_edges", stats.get("edges", stats.get("edge_count", "?")))
        triangles = stats.get("num_triangles", stats.get("triangles", stats.get("triangle_count", "?")))
        partitions = stats.get("num_parts", stats.get("num_workers", stats.get("partitions", stats.get("partition_count", "?"))))

        self._lbl_coord.setText(f"● Coordinator: {partitions} 分区")
        self._lbl_coord.setStyleSheet("color: #22c55e;")
        self._lbl_workers.setText(f"● Workers: {nodes} 节点 · {edges} 边")
        self._lbl_workers.setStyleSheet("color: #22c55e;")

        node_info = f"● 节点: {nodes} · △ {triangles}"
        self._lbl_nodes.setText(node_info)
        self._lbl_nodes.setStyleSheet("color: #22c55e;")

        self._status_indicator.setText("● 系统就绪")
        self._status_indicator.setStyleSheet("color: #22c55e; font-size: 12px;")

    def _on_connection_lost(self):
        self._lbl_coord.setText("● Coordinator: 断开")
        self._lbl_coord.setStyleSheet("color: #ef4444;")
        self._lbl_workers.setText("● Workers: 断开")
        self._lbl_workers.setStyleSheet("color: #ef4444;")
        self._status_indicator.setText("● 连接断开")
        self._status_indicator.setStyleSheet("color: #ef4444; font-size: 12px;")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 窗口事件
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def closeEvent(self, event):
        if hasattr(self, "poller"):
            self.poller.stop()
            self.poller.wait(2000)
        super().closeEvent(event)
