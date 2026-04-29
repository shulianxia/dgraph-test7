#!/usr/bin/env python3
"""
test7 — 分布式图查询系统 GUI（美化版 + 多用户登录）
入口文件
"""

import sys, os, argparse

from PyQt5.QtWidgets import QApplication, QSplashScreen, QMessageBox
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPixmap, QPainter, QColor

# 确保当前目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from login_dialog import LoginDialog
from main_window import MainWindow
from rpc_client import DGraphClient
from theme import COLOR_SUCCESS, LAYER_NAMES


def parse_args():
    parser = argparse.ArgumentParser(description="分布式图查询系统 GUI")
    parser.add_argument("--coord-host", default="127.0.0.1", help="Coordinator 地址")
    parser.add_argument("--coord-port", type=int, default=9000, help="Coordinator 端口")
    return parser.parse_args()


def check_coordinator(host, port):
    """启动时检查 Coordinator 是否可用"""
    client = DGraphClient(host, port)
    stats = client.get_stats()
    if "error" in stats:
        return False, stats["error"]
    return True, stats


def main():
    args = parse_args()
    app = QApplication(sys.argv)
    app.setApplicationName("分布式图查询系统")
    app.setOrganizationName("DGraph")

    # 设置全局字体
    font = QFont("Noto Sans CJK SC", 13)
    app.setFont(font)

    # =========================================
    # 1. 启动自动检查 Coordinator
    # =========================================
    ok, result = check_coordinator(args.coord_host, args.coord_port)

    # =========================================
    # 2. 显示登录框
    # =========================================
    dialog = LoginDialog()

    if dialog.exec_() != LoginDialog.Accepted:
        return  # 用户取消登录

    user = dialog.selected_user
    if not user:
        return

    # =========================================
    # 3. 显示主界面
    # =========================================
    window = MainWindow(user)
    window.client.host = args.coord_host
    window.client.port = args.coord_port

    # 如果 Coordinator 不可用，显示警告但不阻止进入
    if not ok:
        QTimer.singleShot(1000, lambda: QMessageBox.warning(
            window, "连接警告",
            f"无法连接到 Coordinator ({args.coord_host}:{args.coord_port}):\n{result}\n\n"
            "请确保先启动后端服务。\n部分功能可能不可用。"
        ))
    else:
        # 登录成功，显示摘要
        nodes = result.get("num_nodes", result.get("nodes", "?"))
        edges = result.get("num_edges", result.get("edges", "?"))
        triangles = result.get("num_triangles", result.get("triangles", "?"))
        layer_name = LAYER_NAMES.get(user.get("layer", ""), "")
        layer_display = f' &middot; <span style="color: #60a5fa;">{layer_name}</span>' if layer_name else ""
        window._append_result("system",
            f'<div style="color: {COLOR_SUCCESS}; padding: 8px;">'
            f'[OK] 已连接到分布式图查询系统<br>'
            f'节点数: {nodes}  |  边数: {edges}  |  三角形: {triangles}  |  分区: 5<br>'
            f'当前用户: {user["name"]} ({user["role"]}){layer_display}</div>'
        )

    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
