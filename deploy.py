#!/usr/bin/env python3
"""
deploy.py — 分布式多主机部署工具
将图数据库的 Workers 部署到不同主机上运行。

用法:
  # 1. 查看部署配置
  python3 deploy.py --info

  # 2. 部署到多台主机（生成数据 → 分发 → 远程启动 Worker → 本地启动 Coordinator）
  python3 deploy.py --deploy --worker-hosts "host1:9100,host2:9100,host3:9100" --coord-port 9000

  # 3. 仅生成数据并显示各 Worker 命令（适合手动 SSH 到各机器启动）
  python3 deploy.py --generate-only

  # 4. 仅启动本地 Coordinator（假设 Workers 已手动启动）
  python3 deploy.py --coord-only --coord-port 9000

  # 5. 清理远程 Workers
  python3 deploy.py --clean --worker-hosts "host1:9100,host2:9100"
"""

import os, sys, subprocess, time, signal, socket, json, argparse, threading

BASE = os.path.dirname(os.path.abspath(__file__))
GEN_ALL = os.path.join(BASE, "gen_all.py")
COORD = os.path.join(BASE, "coordinator.py")
WORKER = os.path.join(BASE, "worker.py")
DATA_DIR = os.path.join(BASE, "workers")

procs = []  # 本地进程


def log(msg, emoji="ℹ️"):
    ts = time.strftime("%H:%M:%S")
    print(f"  {emoji} [{ts}] {msg}")


def warn(msg):
    log(f"WARNING: {msg}", "⚠️")


def run_cmd(cmd, timeout=30, capture=True):
    """运行命令并返回结果"""
    try:
        result = subprocess.run(cmd, capture_output=capture, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except FileNotFoundError:
        return -1, "", f"command not found: {cmd[0]}"


def parse_hosts(spec):
    """解析主机列表 'host1:port,host2:port' -> [(host, port), ...]"""
    pairs = [p.strip() for p in spec.split(",") if p.strip()]
    hosts = []
    for p in pairs:
        if ":" in p:
            h, port = p.rsplit(":", 1)
            hosts.append((h.strip(), int(port)))
        else:
            hosts.append((p.strip(), 9100))
    return hosts


def generate_data(num_nodes=1000, density=0.08, seed=42):
    """生成分区数据"""
    log(f"生成测试数据 ({num_nodes} 节点, {NUM_WORKERS} 分区)...", "📦")
    result = subprocess.run(
        [sys.executable, GEN_ALL, str(num_nodes), str(density), str(seed),
         "--num-parts", str(NUM_WORKERS), "--out-dir", DATA_DIR],
        capture_output=True, text=True, timeout=300
    )
    if result.returncode != 0:
        log(f"数据生成失败: {result.stderr}", "❌")
        return False
    log("数据生成完成", "✅")
    return True


def check_ssh(host):
    """检查 SSH 是否可用"""
    rc, out, err = run_cmd(["ssh", "-o", "ConnectTimeout=5", host, "echo", "OK"], timeout=10)
    if rc == 0 and "OK" in out:
        return True
    warn(f"SSH 到 {host} 失败: {err.strip()}")
    return False


def distribute_data(hosts):
    """通过 SCP 分发数据文件到各主机"""
    remote_dir = os.path.basename(BASE)
    for idx, (host, port) in enumerate(hosts):
        part_file = os.path.join(DATA_DIR, f"part_{idx}.json")
        if not os.path.exists(part_file):
            log(f"part_{idx}.json 不存在，跳过 {host}", "⚠️")
            continue
        log(f"分发 part_{idx}.json → {host}:~/{remote_dir}/workers/", "📤")
        rc, out, err = run_cmd(
            ["ssh", host, "mkdir", "-p", f"~/{remote_dir}/workers/"],
            timeout=10
        )
        if rc != 0:
            warn(f"在 {host} 上创建目录失败: {err.strip()}")
            continue
        rc, out, err = run_cmd(
            ["scp", "-q", part_file, f"{host}:~/{remote_dir}/workers/part_{idx}.json"],
            timeout=30
        )
        if rc == 0:
            log(f"part_{idx}.json → {host} 完成", "✅")
        else:
            warn(f"part_{idx}.json → {host} 失败: {err.strip()}")


def start_remote_workers(hosts, coord_host, coord_port, remote_dir):
    """通过 SSH 在远程主机上启动 Worker"""
    for idx, (host, port) in enumerate(hosts):
        part = idx  # 每个 Worker 负责一个分区
        data_path = f"~/{remote_dir}/workers/part_{idx}.json"
        advertise = host  # 对外宣告自身 IP

        cmd = (
            f"cd ~/{remote_dir} && "
            f"nohup python3 worker.py "
            f"--worker-id=w{idx} "
            f"--port={port} "
            f"--partition={part} "
            f"--coord-host={coord_host} "
            f"--coord-port={coord_port} "
            f"--data={data_path} "
            f"--advertise-addr={advertise} "
            f"> worker_{idx}.log 2>&1 &"
        )
        log(f"远程启动 Worker {idx+1}/{len(hosts)} @ {host}:{port}", "🚀")
        rc, out, err = run_cmd(["ssh", host, cmd], timeout=10)
        if rc != 0:
            warn(f"Worker@{host} 启动失败: {err.strip()}")
        else:
            log(f"Worker@{host}:{port} 已启动", "✅")


def clean_remote_workers(hosts):
    """清理远程 Worker 进程"""
    for host, port in hosts:
        log(f"清理 {host} 上的 Worker 进程...", "🧹")
        rc, out, err = run_cmd(
            ["ssh", host, "pkill -f 'worker.py' 2>/dev/null; echo done"],
            timeout=10
        )
        log(f"{host} 已清理", "✅")


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


def start_local_coordinator(host, port):
    """启动本地 Coordinator"""
    log(f"启动 Coordinator ({host}:{port})...", "🌐")
    proc = subprocess.Popen(
        [sys.executable, COORD, "--host", host, "--port", str(port)],
        stdout=open(os.path.join(BASE, "coord.log"), "w"),
        stderr=subprocess.STDOUT, cwd=BASE
    )
    if wait_for_port(port):
        log(f"Coordinator 就绪 ({host}:{port})", "✅")
        procs.append(proc)
        return proc
    else:
        log("Coordinator 启动超时", "❌")
        proc.kill()
        return None


def print_info():
    """打印部署信息"""
    NUM_WORKERS = 5
    print(f"""
  分布式部署信息
  ========================================

  系统架构:
    Coordinator Layer  协调层(管理员层)  — 路由管理
    Worker Layer       Worker 层         — 图数据存储/查询
    Client Layer       客户端层           — GUI 连接

  文件说明:
    coordinator.py     — 协调器 (监听 0.0.0.0:{COORD_DEFAULT_PORT})
    worker.py          — Worker (支持 --advertise-addr 远程注册)
    start_demo.py      — 本地一键启动
    server_start.py    — 服务器端启动 (同一台机器)
    deploy.py          — 分布式部署 (当前脚本)
    connect.py         — 客户端连接工具

  部署方式对比:
    方式                   适用场景                   命令
    ─────────────────────────────────────────────────────────────
    start_demo.py         单机测试                   python3 start_demo.py
    server_start.py       单机服务端 + 远程客户端     python3 server_start.py
    deploy.py --deploy    多台主机分布式部署          python3 deploy.py --deploy ...
    deploy.py --coord-only 手动启动 Worker 后启动协调器  python3 deploy.py --coord-only

  示例:
    # 3 台 Worker 主机
    python3 deploy.py --deploy --worker-hosts "10.0.0.2:9100,10.0.0.3:9100,10.0.0.4:9100"

    # 生成数据，手动部署
    python3 deploy.py --generate-only

    # 只启动 Coordinator (Workers 已手动启动)
    python3 deploy.py --coord-only
""")


COORD_DEFAULT_PORT = 9000
NUM_WORKERS = 5


def main():
    parser = argparse.ArgumentParser(
        description="分布式图查询系统 — 多主机部署工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 deploy.py --deploy --worker-hosts "10.0.0.2:9100,10.0.0.3:9100,10.0.0.4:9100"
  python3 deploy.py --generate-only
  python3 deploy.py --coord-only --coord-port 9000
  python3 deploy.py --clean --worker-hosts "10.0.0.2:9100,10.0.0.3:9100"
        """
    )

    # 模式
    parser.add_argument("--deploy", action="store_true",
                        help="完整部署：生成数据 → 分发 → 远程启动 Worker → 本地启动 Coordinator")
    parser.add_argument("--generate-only", action="store_true",
                        help="仅生成分区数据，并打印各 Worker 的启动命令")
    parser.add_argument("--coord-only", action="store_true",
                        help="仅启动本地 Coordinator（假设 Workers 已在远程手动启动）")
    parser.add_argument("--clean", action="store_true",
                        help="清理远程 Workers")
    parser.add_argument("--info", action="store_true",
                        help="显示部署信息")

    # 参数
    parser.add_argument("--worker-hosts", default=None,
                        help="Worker 主机列表，格式: 'host1:port,host2:port,...' (端口默认 9100)")
    parser.add_argument("--coord-host", default="0.0.0.0",
                        help="Coordinator 监听地址 (默认: 0.0.0.0)")
    parser.add_argument("--coord-port", type=int, default=COORD_DEFAULT_PORT,
                        help=f"Coordinator 端口 (默认: {COORD_DEFAULT_PORT})")
    parser.add_argument("--coord-advertise", default=None,
                        help="Coordinator 对外宣告的地址（让远程 Worker 连接用，默认同 --coord-host）")
    parser.add_argument("--num-nodes", type=int, default=1000,
                        help="生成数据的节点数 (默认: 1000)")
    parser.add_argument("--num-parts", type=int, default=None,
                        help="分区数（即 Worker 数量，默认从 --worker-hosts 推断）")

    args = parser.parse_args()

    # 显示信息
    if args.info:
        print_info()
        sys.exit(0)

    # 解析 Worker 主机列表
    worker_hosts = []
    if args.worker_hosts:
        worker_hosts = parse_hosts(args.worker_hosts)
        global NUM_WORKERS
        NUM_WORKERS = len(worker_hosts)

    if args.num_parts:
        NUM_WORKERS = args.num_parts

    coord_advertise = args.coord_advertise or args.coord_host
    if coord_advertise == "0.0.0.0":
        # 尝试获取本机实际 IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            coord_advertise = s.getsockname()[0]
            s.close()
        except:
            coord_advertise = "127.0.0.1"

    print(f"""
  ╔═══════════════════════════════════════╗
  ║   分布式图查询系统  ·  多主机部署      ║
  ╚═══════════════════════════════════════╝
  """)

    # ─────────────────────────────────
    # 模式 1: 仅生成数据
    # ─────────────────────────────────
    if args.generate_only:
        if not generate_data(args.num_nodes, 0.08, 42):
            sys.exit(1)
        print(f"""
  各 Worker 启动命令 (需 SSH 到各机器执行):
  ========================================""")
        remote_dir = os.path.basename(BASE)
        for i in range(NUM_WORKERS):
            data_path = f"~/{remote_dir}/workers/part_{i}.json"
            print(f"""
  # Worker {i+1} (分区 {i}) — 在 <WORKER_HOST_{i}> 上执行:
  mkdir -p ~/{remote_dir}/workers/
  # 先复制 workers/part_{i}.json 到本机对应目录
  cd ~/{remote_dir}
  python3 worker.py \\
      --worker-id=w{i} \\
      --port=9100 \\
      --partition={i} \\
      --coord-host=<COORD_HOST> \\
      --coord-port={args.coord_port} \\
      --data={data_path} \\
      --advertise-addr=<WORKER_HOST_{i}>
  """)
        sys.exit(0)

    # ─────────────────────────────────
    # 模式 2: 完整部署
    # ─────────────────────────────────
    if args.deploy:
        if not worker_hosts:
            log("--deploy 需要 --worker-hosts 参数", "❌")
            sys.exit(1)

        # 第1步：生成数据
        if not generate_data(args.num_nodes, 0.08, 42):
            sys.exit(1)

        # 第2步：检查 SSH
        all_hosts = list(set(h for h, p in worker_hosts))
        for host in all_hosts:
            if not check_ssh(host):
                log(f"SSH 到 {host} 失败，终止部署", "🛑")
                sys.exit(1)

        # 第3步：分发数据
        remote_dir = os.path.basename(BASE)
        distribute_data(worker_hosts)

        # 第4步：分发脚本
        for host in all_hosts:
            log(f"同步 worker.py 到 {host}...", "📤")
            for f in ["worker.py", "protocol.py"]:
                run_cmd(["scp", "-q", os.path.join(BASE, f), f"{host}:~/{remote_dir}/"],
                        timeout=15)

        # 第5步：远程启动 Workers
        start_remote_workers(worker_hosts, coord_advertise, args.coord_port, remote_dir)
        log("等待 Workers 注册...", "⏳")
        time.sleep(3)

        # 第6步：启动本地 Coordinator
        start_local_coordinator(args.coord_host, args.coord_port)

        print(f"""
  🎯 分布式部署完成！
     Coordinator:  {args.coord_host}:{args.coord_port}
     Workers:      {len(worker_hosts)} 台主机
  """)
        print("  客户端连接:")
        print(f"     python3 connect.py --coord-host {coord_advertise} --coord-port {args.coord_port}")
        print("")

        # 保持运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n  正在停止...")

        return

    # ─────────────────────────────────
    # 模式 3: 仅启动 Coordinator
    # ─────────────────────────────────
    if args.coord_only:
        log("跳过数据生成和 Workers，仅启动 Coordinator", "ℹ️")
        start_local_coordinator(args.coord_host, args.coord_port)

        print(f"""
  🎯 Coordinator 已启动！
     Coordinator:  {args.coord_host}:{args.coord_port}
  """)
        print("  客户端连接:")
        print(f"     python3 connect.py --coord-host {coord_advertise} --coord-port {args.coord_port}")
        print("")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n  正在停止...")

        return

    # ─────────────────────────────────
    # 模式 4: 清理远程 Workers
    # ─────────────────────────────────
    if args.clean:
        if not worker_hosts:
            log("--clean 需要 --worker-hosts 参数", "❌")
            sys.exit(1)
        clean_remote_workers(worker_hosts)

        # 也清理本地 Coordinator
        log("清理本地 Coordinator...", "🧹")
        subprocess.run(["pkill", "-f", "coordinator.py"], stderr=subprocess.DEVNULL)
        log("清理完成", "✅")
        return

    # 无参数 — 显示帮助
    parser.print_help()
    print()
    print_info()


if __name__ == "__main__":
    main()
