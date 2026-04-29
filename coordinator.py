#!/usr/bin/env python3
"""
test5 Coordinator — 预取式三角计数 + 多用户查询

新增：
  - MSG_QUERY_STATS: 全图统计
  - MSG_QUERY_NODE_INFO: 节点详细信息
  - 所有查询兼容 test3 短连接模式
"""
import argparse, logging, os, socket, sys, threading, time, uuid
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protocol import (
    MSG_RESULT_OK, MSG_RESULT_ERR, MSG_SHUTDOWN,
    MSG_QUERY_NEIGHBOR, MSG_QUERY_NLIST, MSG_QUERY_COMMON, MSG_QUERY_TRIANGLE,
    MSG_QUERY_STATS, MSG_QUERY_NODE_INFO,
    MSG_REGISTER, MSG_HEARTBEAT, MSG_HEARTBEAT_ACK,
    make_msg, pack_msg, recv_msg, send_msg, get_partition
)

logger = logging.getLogger("Coordinator")

class Coordinator:
    def __init__(self, host="0.0.0.0", port=9000):
        self.host, self.port = host, port
        self.running = False
        self.workers = {}
        self.num_parts = 5
        self._lock = threading.Lock()
        self._server = None
        self._cached_triangles = None
        self._cached_triangles_time = 0
        self._cache_lock = threading.Lock()
        self._handlers = {
            MSG_REGISTER: self._on_register,
            MSG_SHUTDOWN: self._on_shutdown,
            MSG_QUERY_NEIGHBOR: lambda msg: make_msg(MSG_RESULT_OK, "coord",
                self.query_neighbor(msg["payload"].get("node", 0))),
            MSG_QUERY_NLIST: lambda msg: make_msg(MSG_RESULT_OK, "coord",
                self.query_neighbor(msg["payload"].get("node", 0))),
            MSG_QUERY_NODE_INFO: lambda msg: make_msg(MSG_RESULT_OK, "coord",
                self.query_node_info(msg["payload"].get("node", 0))),
            MSG_QUERY_COMMON: lambda msg: make_msg(MSG_RESULT_OK, "coord",
                self.query_common(
                    msg["payload"].get("a", msg["payload"].get("node_a", 0)),
                    msg["payload"].get("b", msg["payload"].get("node_b", 0)))),
            MSG_QUERY_TRIANGLE: lambda msg: make_msg(MSG_RESULT_OK, "coord",
                self.query_triangles_global()
                if "node" not in msg["payload"] and "node_id" not in msg["payload"]
                else self.query_triangles_node(
                    msg["payload"].get("node_id", msg["payload"].get("node", 0)))),
            MSG_QUERY_STATS: lambda msg: make_msg(MSG_RESULT_OK, "coord",
                self.query_stats()),
        }

    def start(self):
        self.running = True
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._server.bind((self.host, self.port))
        except OSError as e:
            if e.errno == 98:
                logger.error(f"端口 {self.port} 已被占用！请先 kill 旧进程:\n  pkill -f \"coordinator.py --port\"")
            raise
        self._server.listen(16)
        logger.info(f"Coordinator @ {self.host}:{self.port}")
        threading.Thread(target=self._auto_hb, daemon=True).start()
        while self.running:
            conn, addr = self._server.accept()
            threading.Thread(target=self._handle, args=(conn, addr), daemon=True).start()

    def stop(self):
        self.running = False
        if self._server:
            self._server.close()

    def _handle(self, conn, addr):
        try:
            msg = recv_msg(conn)
            if msg is None: return
            handler = self._handlers.get(msg.get("msg_type", ""), self._err_handler)
            resp = handler(msg)
            if resp:
                conn.sendall(pack_msg(resp))
        except Exception as e:
            logger.error(f"处理异常: {e}")
        finally:
            conn.close()

    def _err_handler(self, msg):
        return make_msg(MSG_RESULT_ERR, "coord", {"error": "unknown msg_type"})

    def _on_register(self, msg):
        p = msg.get("payload", {})
        wid = p.get("worker_id", "unknown")
        with self._lock:
            self.workers[wid] = {
                "host": p.get("host", "127.0.0.1"),
                "port": p.get("port", 0),
                "partition": p.get("partition", 0),
            }
            if "num_parts" in p:
                self.num_parts = p["num_parts"]
            cnt = len(self.workers)
        logger.info(f"注册: {wid} @ {p.get('host')}:{p.get('port')} ({cnt} 个在线)")
        return make_msg(MSG_RESULT_OK, "coord", {"count": cnt})

    def _on_shutdown(self, msg):
        logger.info("收到关闭指令")
        self.running = False
        return make_msg(MSG_RESULT_OK, "coord", {"status": "shutdown"})

    def _auto_hb(self):
        while self.running:
            time.sleep(15)
            with self._lock:
                items = list(self.workers.items())
            for wid, info in items:
                try:
                    s = socket.create_connection((info["host"], info["port"]), timeout=5)
                    send_msg(s, make_msg(MSG_HEARTBEAT, "coord", {}))
                    resp = recv_msg(s)
                    s.close()
                    if resp and resp["msg_type"] == MSG_HEARTBEAT_ACK:
                        continue
                except:
                    pass
                with self._lock:
                    self.workers.pop(wid, None)
                logger.warning(f"{wid} 心跳超时，已移除")

    def _route(self, node_id):
        with self._lock:
            if not self.workers:
                return None
            part = get_partition(node_id, self.num_parts)
            for wid, info in self.workers.items():
                if info["partition"] == part or len(self.workers) == 1:
                    return info
            return None

    def _rpc(self, info, msg):
        try:
            s = socket.create_connection((info["host"], info["port"]), timeout=30)
            s.sendall(pack_msg(msg))
            resp = recv_msg(s)
            s.close()
            return resp
        except Exception as e:
            logger.error(f"RPC 失败 ({info.get('host')}:{info.get('port')}): {e}")
            return None

    # ── 查询接口 ──
    def query_neighbor(self, node_id):
        info = self._route(node_id)
        if not info: return {"error": f"节点 {node_id} 无 Worker"}
        resp = self._rpc(info, make_msg(MSG_QUERY_NEIGHBOR, "coord", {"node": node_id}))
        if not resp: return {"error": "无响应"}
        return resp.get("payload", {})

    def query_node_info(self, node_id):
        """节点详细信息（直接路由到对应 Worker 查询）"""
        info = self._route(node_id)
        if not info: return {"error": f"节点 {node_id} 无 Worker"}
        resp = self._rpc(info, make_msg(MSG_QUERY_NODE_INFO, "coord", {"node": node_id}))
        if not resp: return {"error": "无响应"}
        return resp.get("payload", {})

    def query_common(self, a, b):
        info_a, info_b = self._route(a), self._route(b)
        if not info_a or not info_b:
            return {"error": f"节点 {a} 或 {b} 无 Worker"}
        if info_a is info_b:
            resp = self._rpc(info_a, make_msg(MSG_QUERY_COMMON, "coord", {"a": a, "b": b}))
            if not resp: return {"error": "无响应"}
            return resp.get("payload", {})
        resp_a = self._rpc(info_a, make_msg(MSG_QUERY_NLIST, "coord", {"node": a}))
        resp_b = self._rpc(info_b, make_msg(MSG_QUERY_NLIST, "coord", {"node": b}))
        if not resp_a or not resp_b:
            return {"error": "无响应"}
        na = set(resp_a.get("payload", {}).get("neighbors", []))
        nb = set(resp_b.get("payload", {}).get("neighbors", []))
        common = sorted(na & nb)
        return {"a": a, "b": b, "common_neighbors": common, "count": len(common)}

    def query_triangles_global(self, force=False):
        """全图三角计数（预取模式），带缓存"""
        import time as _time
        with self._cache_lock:
            if not force and self._cached_triangles is not None and \
               _time.time() - self._cached_triangles_time < 30:
                return self._cached_triangles
        logger.info("开始分布式全图三角计数（预取模式）")
        local_adj = {}
        with self._lock:
            items = list(self.workers.items())
        for wid, info in items:
            resp = self._rpc(info, make_msg("query_all_edges", "coord", {}))
            if resp and resp["msg_type"] == MSG_RESULT_OK:
                for u, v in resp.get("payload", {}).get("edges", []):
                    local_adj.setdefault(u, set()).add(v)
                    local_adj.setdefault(v, set()).add(u)
        logger.info(f"预取邻接表: {len(local_adj)} 节点")
        if not local_adj:
            return {"error": "收集边失败"}
        triangles = set()
        nodes = sorted(local_adj.keys())
        for i, u in enumerate(nodes):
            nu = local_adj[u]
            for v in nu:
                if v <= u:
                    continue
                nv = local_adj.get(v, set())
                for w in nu & nv:
                    if w > v:
                        triangles.add((u, v, w))
        logger.info(f"分布式三角计数完成（预取）: {len(triangles)} 个三角形")
        result = {"count": len(triangles), "triangles": sorted(triangles), "_node_count": len(local_adj)}
        with self._cache_lock:
            self._cached_triangles = result
            self._cached_triangles_time = _time.time()
        return result

    def query_triangles_node(self, node_id):
        info = self._route(node_id)
        if not info: return {"error": f"节点 {node_id} 无 Worker"}
        resp = self._rpc(info, make_msg(MSG_QUERY_NLIST, "coord", {"node": node_id}))
        if not resp or resp["msg_type"] != MSG_RESULT_OK:
            return {"error": "无响应"}
        na = set(resp["payload"].get("neighbors", []))
        triangles = []
        for n in na:
            info_n = self._route(n)
            if not info_n: continue
            resp_n = self._rpc(info_n, make_msg(MSG_QUERY_NLIST, "coord", {"node": n}))
            if not resp_n or resp_n["msg_type"] != MSG_RESULT_OK:
                continue
            nn = set(resp_n["payload"].get("neighbors", []))
            common = na & nn
            for w in common:
                if w > n:
                    triangles.append((node_id, n, w))
        return {"node": node_id, "count": len(triangles), "triangles": sorted(triangles)}

    def query_stats(self):
        """全图统计 — 聚合各 Worker 的分区统计"""
        with self._lock:
            items = list(self.workers.items())
        num_edges = 0
        for wid, info in items:
            resp = self._rpc(info, make_msg(MSG_QUERY_STATS, "coord", {}))
            if resp and resp["msg_type"] == MSG_RESULT_OK:
                s = resp.get("payload", {})
                num_edges += s.get("num_edges", 0)
        triangle_result = self.query_triangles_global()
        if "error" in triangle_result:
            return {
                "num_nodes": 0,
                "num_edges": 0,
                "num_parts": len(items),
                "num_workers": len(items),
                "num_triangles": 0,
                "status": "error",
                "error": triangle_result["error"],
            }
        return {
            "num_nodes": triangle_result.get("_node_count", 0),
            "num_edges": num_edges,
            "num_parts": len(items),
            "num_workers": len(items),
            "num_triangles": triangle_result.get("count", 0),
            "status": "running",
        }


if __name__ == "__main__":
    from protocol import send_msg, recv_or_none
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    logging.getLogger().setLevel(logging.INFO)
    Coordinator(host=args.host, port=args.port).start()
