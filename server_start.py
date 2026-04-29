#!/usr/bin/env python3
"""
server_start.py — 服务器端一键启动（无 GUI）
启动 Coordinator + Workers，供远程客户端连接

用法:
  # 默认启动（Coordinator :9000, Workers :9100-9104）
  python3 server_start.py

  # 自定义端口
  python3 server_start.py --coord-port 9000 --worker-base 9100

  # 指定监听地址（局域网其他机器访问）
  python3 server_start.py --host 0.0.0.0
"""

import os, sys, subprocess, time, signal, socket, argparse

BASE = os.path.dirname(os.path.abspath(__file__))
GEN_ALL = os.path.join(BASE, "gen_all.py")
COORD = os.path.join(BASE, "coordinator.py")
WORKER = os.path.join(BASE, "worker.py")

NUM_WORKERS = 5
DATA_DIR = os.path.join(BASE, "workers")
procs = []


def log(msg, emoji="ℹ️"):
    ts = time.strftime("%H:%M:%S")
    print(f"  {emoji} [{ts}] {msg}")


def check_port(port, host="127.0.0.1"):
    try:
        s = socket.create_connection((host, port), timeout=0.5)
        s.close()
        return False
    except:
        return True


def wait_for_port(port, host="127.0.0.1", timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        try:
            s = socket.create_connection((host, port), timeout=1)
            s.close()
            return True
        except:
            time.sleep(0.5)
    return False


def kill_old():
    log("清理旧 Coordinator / Worker 进程...", "🧹")
    for proc in ["coordinator.py", "worker.py"]:
        try:
            subprocess.run(["pkill", "-f", proc], stderr=subprocess.DEVNULL, timeout=5)
        except subprocess.TimeoutExpired:
            subprocess.run(["pkill", "-9", "-f", proc], stderr=subprocess.DEVNULL)
    time.sleep(1)
    log("旧进程已清理", "✅")


def generate_data():
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


def start_coordinator(host, port):
    log(f"启动 Coordinator ({host}:{port})...", "🌐")
    proc = subprocess.Popen(
        [sys.executable, COORD, "--host", host, "--port", str(port)],
        stdout=open(os.path.join(BASE, "coord.log"), "w"),
        stderr=subprocess.STDOUT,
        cwd=BASE
    )
    if wait_for_port(port, host="127.0.0.1"):
        log(f"Coordinator 就绪 ({host}:{port})", "✅")
        return proc
    else:
        log("Coordinator 启动超时", "❌")
        proc.kill()
        return None


def start_workers(coord_host, coord_port, worker_base, advertise_host=None):
    global procs
    for i in range(NUM_WORKERS):
        port = worker_base + i
        log(f"启动 Worker {i+1}/{NUM_WORKERS} (:{port})...", "⚙️")
        cmd = [
            sys.executable, WORKER,
            f"--worker-id=w{i}",
            f"--port={port}",
            f"--partition={i}",
            f"--coord-host={coord_host}",
            f"--coord-port={coord_port}",
            f"--data={DATA_DIR}/part_{i}.json",
        ]
        if advertise_host:
            cmd.append(f"--advertise-addr={advertise_host}")
        proc = subprocess.Popen(
            cmd,
            stdout=open(os.path.join(BASE, f"worker_{i}.log"), "w"),
            stderr=subprocess.STDOUT,
            cwd=BASE
        )
        procs.append((i, proc, port))
        time.sleep(0.5)

    all_ok = True
    for i, proc, port in procs:
        if wait_for_port(port, timeout=10):
            log(f"Worker {i+1} 就绪 (:{port})", "✅")
        else:
            log(f"Worker {i+1} 启动超时 (:{port})", "❌")
            all_ok = False
    return procs if all_ok else None


def cleanup(signum=None, frame=None):
    print("\n  正在停止所有进程...")
    for i, p, port in procs:
        try:
            p.terminate()
            p.wait(timeout=3)
        except:
            try:
                p.kill()
            except:
                pass
    # 也清理可能残留的进程
    for proc in ["coordinator.py", "worker.py"]:
        subprocess.run(["pkill", "-f", proc], stderr=subprocess.DEVNULL)
    log("所有进程已停止", "🛑")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="分布式图查询系统 — 服务器端一键启动")
    parser.add_argument("--host", default="0.0.0.0", help="Coordinator 监听地址 (默认: 0.0.0.0)")
    parser.add_argument("--coord-port", type=int, default=9000, help="Coordinator 端口 (默认: 9000)")
    parser.add_argument("--worker-base", type=int, default=9100, help="Worker 起始端口 (默认: 9100)")
    args = parser.parse_args()

    # 注册 Ctrl+C 清理
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print("")
    print("  ╔═══════════════════════════════════════╗")
    print("  ║   分布式图查询系统  ·  服务器启动      ║")
    print("  ║   test7 - server start               ║")
    print("  ╚═══════════════════════════════════════╝")
    print("")

    kill_old()

    if not generate_data():
        log("终止启动", "🛑")
        sys.exit(1)

    coord = start_coordinator(args.host, args.coord_port)
    if not coord:
        sys.exit(1)

    workers = start_workers("127.0.0.1", args.coord_port, args.worker_base)
    if not workers:
        sys.exit(1)

    time.sleep(1)

    print("")
    print(f"  🎯 服务器已就绪")
    print(f"     Coordinator:  {args.host}:{args.coord_port}")
    print(f"     Workers:      {NUM_WORKERS} 个 (:{args.worker_base}-:{args.worker_base+NUM_WORKERS-1})")
    print(f"     数据:         {DATA_DIR}")
    print("")
    print(f"  客户端连接:")
    print(f"     python3 connect.py --coord-host <本机IP> --coord-port {args.coord_port}")
    print("")
    print(f"  按 Ctrl+C 停止服务")
    print("")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
