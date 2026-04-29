#!/usr/bin/env python3
"""
test5 — 分布式图查询系统协议（基于 test3）

新增消息类型：
  MSG_QUERY_STATS    = 0x25  全图统计
  MSG_QUERY_NODE_INFO = 0x26  节点详细信息（含属性）
"""
import hashlib, json, logging, socket, struct, threading, time, uuid
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="[%(asctime)s %(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("DGProto")

# ── 图存储 ──
class GraphStorage:
    """与 test3 完全一致"""
    def __init__(self, directed=False):
        self.directed = directed
        self.adjacency = defaultdict(list)
        self.node_attrs = defaultdict(dict)

    def add_node(self, nid, **attrs):
        self.node_attrs[nid].update(attrs)
        if nid not in self.adjacency:
            self.adjacency[nid] = []

    def add_edge(self, src, dst, **attrs):
        self.add_node(src); self.add_node(dst)
        if dst not in self.adjacency[src]:
            self.adjacency[src].append(dst)
        if not self.directed and src not in self.adjacency[dst]:
            self.adjacency[dst].append(src)

    def get_neighbors(self, nid):
        return list(self.adjacency.get(int(nid), []))

    def num_nodes(self):
        return len(self.node_attrs)

    def num_edges(self):
        seen = set()
        for s, nbrs in self.adjacency.items():
            for d in nbrs:
                seen.add(tuple(sorted((s, d))) if not self.directed else (s, d))
        return len(seen)

    def all_edges(self):
        seen = set(); out = []
        for s, nbrs in self.adjacency.items():
            for d in nbrs:
                k = tuple(sorted((s, d))) if not self.directed else (s, d)
                if k not in seen:
                    seen.add(k); out.append(k)
        return out

    def get_stats(self):
        """返回全图统计信息"""
        adj = dict(self.adjacency)
        degrees = [len(nbrs) for nbrs in adj.values()]
        total_edges = 0
        seen = set()
        for s, nbrs in adj.items():
            for d in nbrs:
                k = tuple(sorted((s, int(d)))) if not self.directed else (s, d)
                if k not in seen:
                    seen.add(k); total_edges += 1

        return {
            "num_nodes": self.num_nodes(),
            "num_edges": total_edges,
            "min_degree": min(degrees) if degrees else 0,
            "max_degree": max(degrees) if degrees else 0,
            "avg_degree": round(sum(degrees) / len(degrees), 2) if degrees else 0.0,
        }

    def to_dict(self):
        return {
            "adjacency": {str(k): v for k, v in self.adjacency.items()},
            "node_attrs": {str(k): dict(v) for k, v in self.node_attrs.items()},
            "directed": self.directed,
        }

    @classmethod
    def from_dict(cls, d):
        g = cls(directed=d.get("directed", False))
        for k, v in d["node_attrs"].items():
            g.add_node(int(k), **v)
        for k, v in d["adjacency"].items():
            g.adjacency[int(k)] = v
        return g


# ── 本地查询 ──
class LocalQuery:
    """与 test3 一致"""
    def __init__(self, storage):
        self.g = storage

    def neighbors(self, node):
        return set(self.g.adjacency.get(int(node), []))

    def common_neighbors(self, a, b):
        return sorted(self.neighbors(a) & self.neighbors(b))

    def get_edges(self):
        return self.g.all_edges()

    def query_neighbor(self, nid):
        nbrs = self.g.get_neighbors(nid)
        return {"node": nid, "neighbors": sorted(nbrs), "degree": len(nbrs)}

    def query_nlist(self, nid):
        return {"node": nid, "neighbors": sorted(self.g.get_neighbors(nid))}

    def query_common(self, a, b):
        na = set(self.g.get_neighbors(a))
        nb = set(self.g.get_neighbors(b))
        common = sorted(na & nb)
        return {"node_a": a, "node_b": b, "common_neighbors": common, "count": len(common)}

    def query_node_info(self, nid):
        """节点详细信息（含属性和统计）"""
        nbrs = self.g.get_neighbors(nid)
        attrs = dict(self.g.node_attrs.get(int(nid), {}))
        return {
            "node": nid,
            "attrs": attrs,
            "degree": len(nbrs),
            "neighbors": sorted(nbrs),
        }

    def query_stats(self):
        """全图统计"""
        return self.g.get_stats()


# ── 一致性哈希 ──
def get_partition(node_id, num_partitions):
    return int(hashlib.md5(str(node_id).encode()).hexdigest(), 16) % num_partitions


# ── 消息类型 ──
MSG_REGISTER          = 0x01
MSG_REGISTER_ACK      = 0x02
MSG_HEARTBEAT         = 0x10
MSG_HEARTBEAT_ACK     = 0x11
MSG_QUERY_NLIST       = 0x20   # 邻居列表（别名也用于 neighbor）
MSG_QUERY_NEIGHBOR    = 0x20
MSG_QUERY_COMMON      = 0x21   # 共同邻居
MSG_QUERY_TRIANGLE    = 0x22   # 三角计数
MSG_QUERY_EDGES       = 0x23   # 获取所有边
MSG_QUERY_NLIST_BULK  = 0x24   # 批量邻居列表
MSG_QUERY_STATS       = 0x25   # 全图统计
MSG_QUERY_NODE_INFO   = 0x26   # 节点详细信息
MSG_RESULT_OK         = 0x30
MSG_RESULT_ERR        = 0x31
MSG_SHUTDOWN          = 0xFF


def make_msg(msg_type, sender, payload):
    return {"msg_id": str(uuid.uuid4()), "msg_type": msg_type, "sender": sender,
            "timestamp": time.time(), "payload": payload}


def pack_msg(d):
    body = json.dumps(d, ensure_ascii=False).encode("utf-8")
    return struct.pack("!I", len(body)) + body


def recv_msg(sock):
    raw = sock.recv(4)
    if not raw: return None
    length = struct.unpack("!I", raw)[0]
    body = b""
    while len(body) < length:
        chunk = sock.recv(length - len(body))
        if not chunk: return None
        body += chunk
    return json.loads(body.decode("utf-8"))


def send_msg(sock, msg):
    sock.sendall(pack_msg(msg))


def recv_or_none(sock):
    try: return recv_msg(sock)
    except: return None
