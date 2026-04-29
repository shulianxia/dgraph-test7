#!/usr/bin/env python3
"""
test5 Worker — 复用 test3 短连接模式，新增 stats/node_info
"""
import argparse, json, logging, os, socket, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protocol import (
    MSG_RESULT_OK, MSG_RESULT_ERR, MSG_REGISTER, MSG_HEARTBEAT, MSG_HEARTBEAT_ACK,
    MSG_QUERY_NLIST, MSG_QUERY_NEIGHBOR, MSG_QUERY_COMMON, MSG_QUERY_STATS, MSG_QUERY_NODE_INFO,
    make_msg, pack_msg, recv_msg, send_msg, GraphStorage, get_partition, LocalQuery
)

logger = logging.getLogger("Worker")

class Worker:
    def __init__(self, wid, data_path, listen_port=10000,
                 coord_host="127.0.0.1", coord_port=9000, partition=0):
        self.wid = wid
        self.data_path = data_path
        self.listen_port = listen_port
        self.coord_host, self.coord_port = coord_host, coord_port
        self.partition = partition
        self.storage = GraphStorage()
        self.running = False

    def load_data(self):
        if not os.path.exists(self.data_path):
            logger.error(f"数据文件不存在: {self.data_path}")
            return False
        with open(self.data_path) as f:
            raw = json.load(f)
        nodes = len(raw.get("adjacency", {}))
        edges = sum(len(v) for v in raw.get("adjacency", {}).values())
        self.storage = GraphStorage.from_dict(raw)
        logger.info(f"{self.wid} 加载 {nodes} 节点, {edges // 2} 边")
        return True

    def start(self):
        self.running = True
        self._register()
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            srv.bind(("0.0.0.0", self.listen_port))
        except OSError as e:
            if e.errno == 98:
                logger.error(f"端口 {self.listen_port} 已被占用！请先 kill 旧进程:\n  pkill -f \"worker.py --worker-id\"")
            raise
        srv.listen(16)
        logger.info(f"{self.wid} @ :{self.listen_port} 就绪 (分区 {self.partition})")
        while self.running:
            conn, addr = srv.accept()
            threading.Thread(target=self._handle, args=(conn, addr), daemon=True).start()

    def _register(self):
        try:
            s = socket.create_connection((self.coord_host, self.coord_port), timeout=10)
            msg = make_msg(MSG_REGISTER, self.wid, {
                "host": "127.0.0.1",
                "port": self.listen_port,
                "worker_id": self.wid,
                "partition": self.partition,
            })
            s.sendall(pack_msg(msg))
            resp = recv_msg(s)
            s.close()
            if resp and resp["msg_type"] == MSG_RESULT_OK:
                logger.info(f"注册成功, {resp['payload'].get('count')} 个在线")
            else:
                logger.error("注册失败")
        except Exception as e:
            logger.error(f"注册异常: {e}")

    def _handle(self, conn, addr):
        try:
            msg = recv_msg(conn)
            if msg is None: return
            resp = self._process(msg)
            if resp:
                conn.sendall(pack_msg(resp))
        except Exception as e:
            logger.error(f"处理异常: {e}")
        finally:
            conn.close()

    def _process(self, msg):
        mt = msg["msg_type"]
        p = msg.get("payload", {})
        query = LocalQuery(self.storage)

        if mt == MSG_HEARTBEAT:
            return make_msg(MSG_HEARTBEAT_ACK, self.wid, {})

        elif mt == MSG_QUERY_NLIST or mt == MSG_QUERY_NEIGHBOR:
            n = p.get("node", p.get("node_id", 0))
            na = [int(nn) for nn in query.neighbors(n)]
            return make_msg(MSG_RESULT_OK, self.wid, {"node": n, "neighbors": na, "degree": len(na)})

        elif mt == "query_all_edges":
            edges = query.get_edges()
            return make_msg(MSG_RESULT_OK, self.wid, {"edges": edges})

        elif mt == MSG_QUERY_COMMON or mt == "query_common":
            a = p.get("a", p.get("node_a", 0))
            b = p.get("b", p.get("node_b", 0))
            common = query.common_neighbors(a, b)
            return make_msg(MSG_RESULT_OK, self.wid, {"a": a, "b": b, "neighbors": common, "count": len(common)})

        elif mt == MSG_QUERY_NODE_INFO:
            nid = p.get("node", p.get("node_id", 0))
            result = query.query_node_info(nid)
            return make_msg(MSG_RESULT_OK, self.wid, result)

        elif mt == MSG_QUERY_STATS:
            stats = query.query_stats()
            return make_msg(MSG_RESULT_OK, self.wid, stats)

        return make_msg(MSG_RESULT_ERR, self.wid, {"error": f"unknown msg_type: {mt}"})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker-id", default="node_0")
    ap.add_argument("--port", type=int, default=10000)
    ap.add_argument("--coord-host", default="127.0.0.1")
    ap.add_argument("--coord-port", type=int, default=9000)
    ap.add_argument("--partition", type=int, default=0)
    ap.add_argument("--data", default="")
    args = ap.parse_args()

    logging.getLogger().setLevel(logging.INFO)
    w = Worker(args.worker_id, args.data, args.port, args.coord_host, args.coord_port, args.partition)
    if not w.load_data():
        sys.exit(1)
    w.start()
