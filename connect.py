#!/usr/bin/env python3
"""
connect.py — 客户端一键连接脚本
在不同电脑上以不同身份登录分布式图查询系统

用法:
  # 连接本地服务
  python3 connect.py

  # 连接远程服务器，手动选择用户
  python3 connect.py --coord-host 192.168.1.100

  # Alice 在自己电脑上一键连接
  python3 connect.py --coord-host 192.168.1.100 --user alice

  # Bob 在自己电脑上一键连接
  python3 connect.py --coord-host 192.168.1.100 --user bob

  # 显示预置用户列表
  python3 connect.py --list-users
"""

import argparse, sys, os, socket

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from login_dialog import PRESET_USERS
from main_window import MainWindow
from rpc_client import DGraphClient
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QFont

from theme import COLOR_SUCCESS, LAYER_NAMES, LAYER_LABELS


def find_user(user_spec):
    """按 id 或 name 查找用户"""
    for u in PRESET_USERS:
        if u["id"] == user_spec or u["name"] == user_spec:
            return u
    return None


def check_connection(host, port):
    """检查 Coordinator 是否可达"""
    try:
        s = socket.create_connection((host, port), timeout=3)
        s.close()
        return True, None
    except socket.timeout:
        return False, "连接超时"
    except ConnectionRefusedError:
        return False, "连接被拒绝（服务未启动）"
    except Exception as e:
        return False, str(e)


def print_users():
    """打印预置用户列表"""
    print("\n  预置用户:")
    print(f"  {'ID':<14} {'名称':<10} {'角色':<8} {'层级':<22}")
    print(f"  {'-'*14} {'-'*10} {'-'*8} {'-'*22}")
    for u in PRESET_USERS:
        layer_cn = LAYER_NAMES.get(u["layer"], u["layer"])
        layer_en = LAYER_LABELS.get(u["layer"], "")
        print(f"  {u['id']:<14} {u['name']:<10} {u['role']:<8} {layer_cn} ({layer_en})")
    print()


def build_auto_user(user_spec):
    """构建与 login_dialog 格式一致的 user dict"""
    u = find_user(user_spec)
    return {
        "id": u["id"],
        "name": u["name"],
        "avatar": u["avatar"],
        "role": u["role"],
        "role_tag": u["role_tag"],
        "layer": u["layer"],
        "desc": u["desc"],
        "color": u["color"],
    }


def main():
    parser = argparse.ArgumentParser(description="分布式图查询系统 — 客户端连接工具")
    parser.add_argument("--coord-host", default="127.0.0.1",
                        help="Coordinator 服务器地址 (默认: 127.0.0.1)")
    parser.add_argument("--coord-port", type=int, default=9000,
                        help="Coordinator 端口 (默认: 9000)")
    parser.add_argument("--user", default=None,
                        help="自动登录指定用户，跳过登录界面 (admin/shulianxia/alice/bob/charlie)")
    parser.add_argument("--list-users", action="store_true",
                        help="显示预置用户列表")
    args = parser.parse_args()

    # 仅列出用户
    if args.list_users:
        print_users()
        sys.exit(0)

    # 验证用户参数
    if args.user and not find_user(args.user):
        print(f"\n  [!] 未知用户 '{args.user}'")
        print_users()
        sys.exit(1)

    # ── 连接信息 ──
    print("")
    print("  ╔═══════════════════════════════════════╗")
    print("  ║   分布式图查询系统  ·  客户端连接      ║")
    print("  ╚═══════════════════════════════════════╝")
    print("")
    print(f"  [>] Coordinator: {args.coord_host}:{args.coord_port}")

    # ── 连接检查 ──
    ok, err = check_connection(args.coord_host, args.coord_port)
    if ok:
        print(f"  [✓] 服务可达")
    else:
        print(f"  [!] {err}")
        print(f"  [~] 仍将启动 GUI，但功能可能受限")
    print("")

    # ── 创建应用 ──
    app = QApplication(sys.argv)
    app.setApplicationName("分布式图查询系统")
    font = QFont("Noto Sans CJK SC", 13)
    app.setFont(font)

    # ── 选择用户 ──
    user = None

    if args.user:
        # 一键模式：自动登录指定用户，不显示登录界面
        user = build_auto_user(args.user)
        print(f"  [@] 自动登录: {user['name']} ({user['role']})")
        print(f"      Layer:    {LAYER_NAMES.get(user['layer'], '')}")
    else:
        # 交互模式：显示登录卡片
        from login_dialog import LoginDialog
        dialog = LoginDialog()
        if dialog.exec_() != LoginDialog.Accepted:
            print("  用户取消登录\n")
            sys.exit(0)
        user = dialog.selected_user
        if not user:
            sys.exit(0)

    print(f"      ── 按 Ctrl+C 退出程序 ──")
    print("")

    # ── 启动 GUI ──
    window = MainWindow(user)
    window.client.host = args.coord_host
    window.client.port = args.coord_port

    if ok:
        # 连接成功，获取并显示统计摘要
        stats = window.client.get_stats()
        if "error" not in stats:
            nodes = stats.get("num_nodes", "?")
            edges = stats.get("num_edges", "?")
            triangles = stats.get("num_triangles", "?")
            partitions = stats.get("num_parts", "?")
            layer_name = LAYER_NAMES.get(user.get("layer", ""), "")
            layer_display = f' · <span style="color: #60a5fa;">{layer_name}</span>' if layer_name else ""
            window._append_result("system",
                f'<div style="color: {COLOR_SUCCESS}; padding: 8px;">'
                f'[OK] 已连接到分布式图查询系统<br>'
                f'服务器: {args.coord_host}:{args.coord_port}<br>'
                f'节点数: {nodes}  |  边数: {edges}  |  三角形: {triangles}  |  分区: {partitions}<br>'
                f'当前用户: {user["name"]} ({user["role"]}){layer_display}</div>'
            )
        else:
            window._append_result("system",
                f'<div style="color: #f59e0b; padding: 8px;">'
                f'[!] 已连接服务器，但获取统计信息失败: {stats["error"]}</div>'
            )
    else:
        window._append_result("system",
            f'<div style="color: #f59e0b; padding: 8px;">'
            f'[!] 无法连接到 {args.coord_host}:{args.coord_port}，功能可能受限</div>'
        )

    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
