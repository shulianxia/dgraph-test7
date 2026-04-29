#!/usr/bin/env python3
"""
test7 — 一键启动脚本
清理旧进程 → 生成数据 → 启动 Coordinator → 启动 Workers → 启动 GUI
"""

import os, sys, subprocess, time, signal, socket

BASE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.normpath(os.path.join(BASE, "../tools"))
PIP_MIRROR = os.path.join(TOOLS, "pip_mirror.py")
GEN_ALL = os.path.join(BASE, "gen_all.py")
COORD = os.path.join(BASE, "coordinator.py")
WORKER = os.path.join(BASE, "worker.py")
UI = os.path.join(BASE, "ui_app.py")

COORD_PORT = 9000
WORKER_BASE = 9100
NUM_WORKERS = 5
DATA_DIR = os.path.join(BASE, "workers")


def log(msg, emoji="ℹ️"):
    ts = time.strftime("%H:%M:%S")
    print(f"  {emoji} [{ts}] {msg}")


def check_port(port, host="127.0.0.1"):
    """检查端口是否可用"""
    try:
        s = socket.create_connection((host, port), timeout=0.5)
        s.close()
        return False  # 端口被占用
    except (socket.timeout, ConnectionRefusedError, OSError):
        return True   # 端口可用


def wait_for_port(port, host="127.0.0.1", timeout=15):
    """等待端口开放"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            s = socket.create_connection((host, port), timeout=1)
            s.close()
            return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            time.sleep(0.5)
    return False


def kill_old():
    """杀死之前的 Coordinator 和 Worker 进程"""
    log("清理旧进程...", "🧹")
    for proc in ["coordinator.py", "worker.py"]:
        try:
            subprocess.run(
                ["pkill", "-f", proc],
                stderr=subprocess.DEVNULL, timeout=5
            )
        except subprocess.TimeoutExpired:
            subprocess.run(["pkill", "-9", "-f", proc], stderr=subprocess.DEVNULL)
    time.sleep(1)
    log("旧进程已清理", "✅")


def generate_data():
    """生成测试数据"""
    log(f"生成测试数据（{NUM_WORKERS} 分区）...", "📦")
    result = subprocess.run(
        [sys.executable, GEN_ALL, "1000", "0.08", "42",
         "--num-parts", str(NUM_WORKERS),
         "--out-dir", DATA_DIR],
        capture_output=True, text=True, timeout=300
    )
    if result.returncode != 0:
        log(f"数据生成失败: {result.stderr}", "❌")
        return False
    log("数据生成完成", "✅")
    return True


def start_coordinator():
    """启动 Coordinator"""
    log(f"启动 Coordinator (:{COORD_PORT})...", "🌐")
    proc = subprocess.Popen(
        [sys.executable, COORD, "--port", str(COORD_PORT)],
        stdout=open(os.path.join(BASE, "coord.log"), "w"),
        stderr=subprocess.STDOUT,
        cwd=BASE
    )
    if wait_for_port(COORD_PORT):
        log(f"Coordinator 就绪 (:{COORD_PORT})", "✅")
        return proc
    else:
        log("Coordinator 启动超时", "❌")
        proc.kill()
        return None


def start_workers():
    """启动 Workers"""
    procs = []
    for i in range(NUM_WORKERS):
        port = WORKER_BASE + i
        log(f"启动 Worker {i+1}/5 (:{port})...", "⚙️")
        proc = subprocess.Popen(
            [sys.executable, WORKER,
             f"--worker-id=w{i}",
             f"--port={port}",
             f"--partition={i}",
             f"--coord-host=127.0.0.1",
             f"--coord-port={COORD_PORT}",
             f"--data={DATA_DIR}/part_{i}.json"],
            stdout=open(os.path.join(BASE, f"worker_{i}.log"), "w"),
            stderr=subprocess.STDOUT,
            cwd=BASE
        )
        procs.append((i, proc, port))
        time.sleep(0.5)  # 错开启动避免端口竞争

    # 验证全部启动
    all_ok = True
    for i, proc, port in procs:
        if wait_for_port(port, timeout=10):
            log(f"Worker {i+1} 就绪 (:{port})", "✅")
        else:
            log(f"Worker {i+1} 启动超时 (:{port})", "❌")
            all_ok = False
    return procs if all_ok else None


def start_gui():
    """启动 GUI"""
    log("启动图形界面...", "🎨")
    proc = subprocess.Popen(
        [sys.executable, UI],
        cwd=BASE
    )
    return proc


def main():
    print("")
    print("  ╔═══════════════════════════════════════╗")
    print("  ║   分布式图查询系统  ·  一键启动        ║")
    print("  ║   test7 - 多用户登录 + 美化 GUI       ║")
    print("  ╚═══════════════════════════════════════╝")
    print("")

    # 第1步：清理
    kill_old()

    # 第2步：数据生成
    if not generate_data():
        log("终止启动", "🛑")
        sys.exit(1)

    # 第3步：启动 Coordinator
    coord = start_coordinator()
    if not coord:
        log("终止启动", "🛑")
        sys.exit(1)

    # 第4步：启动 Workers
    workers = start_workers()
    if not workers:
        log("终止启动", "🛑")
        sys.exit(1)

    # 第5步：等待系统稳定
    log("系统就绪，启动 GUI...", "🚀")
    time.sleep(2)

    # 第6步：启动 GUI
    gui = start_gui()

    print("")
    print(f"  🎯 系统已全部启动")
    print(f"     Coordinator:  http://127.0.0.1:{COORD_PORT}")
    print(f"     Workers:      {NUM_WORKERS} 个 (:{WORKER_BASE}-:{WORKER_BASE+NUM_WORKERS-1})")
    print(f"     预置用户:     5 个 (管理员 / shulianxia / alice / bob / charlie)")
    print("")
    print("  按 Ctrl+C 停止所有进程")
    print("")

    try:
        gui.wait()
    except KeyboardInterrupt:
        print("\n  正在停止...")
    finally:
        coord.terminate()
        for i, p, _ in workers:
            p.terminate()
        gui.terminate()
        print("  所有进程已停止")


if __name__ == "__main__":
    main()
