#!/usr/bin/env python3
"""
test7 — RPC 客户端 + 后台查询线程
"""

import socket, json, time, threading
from PyQt5.QtCore import QThread, pyqtSignal

# ── 协议导入 ──
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protocol import (
    make_msg, pack_msg, recv_msg, MSG_RESULT_OK,
    MSG_QUERY_NEIGHBOR, MSG_QUERY_NLIST, MSG_QUERY_COMMON,
    MSG_QUERY_TRIANGLE, MSG_QUERY_STATS, MSG_QUERY_NODE_INFO,
)


class DGraphClient:
    """封装与 Coordinator 的 RPC 通信，线程安全"""

    def __init__(self, host="127.0.0.1", port=9000, sender="test7_gui"):
        self.host = host
        self.port = port
        self.sender = sender
        self._lock = threading.Lock()

    def _rpc(self, msg_type, payload, timeout=30):
        """发送 RPC 请求并接收响应"""
        try:
            s = socket.create_connection((self.host, self.port), timeout=15)
            msg = make_msg(msg_type, self.sender, payload)
            s.sendall(pack_msg(msg))
            resp = recv_msg(s)
            s.close()
            if resp and resp.get("msg_type") == MSG_RESULT_OK:
                return resp.get("payload", {})
            err = (resp.get("payload", {}).get("error", "查询失败")
                   if resp else "无响应")
            return {"error": err}
        except socket.timeout:
            return {"error": "连接超时，请确认 Coordinator 是否在运行"}
        except ConnectionRefusedError:
            return {"error": f"连接被拒绝 (127.0.0.1:{self.port})，请先启动系统"}
        except Exception as e:
            return {"error": str(e)}

    def get_node_info(self, node_id):
        return self._rpc(MSG_QUERY_NODE_INFO, {"node": int(node_id)})

    def get_neighbors(self, node_id):
        return self._rpc(MSG_QUERY_NEIGHBOR, {"node": int(node_id)})

    def get_common(self, a, b):
        return self._rpc(MSG_QUERY_COMMON, {"a": int(a), "b": int(b)})

    def get_triangles(self, node_id=None):
        if node_id is not None:
            return self._rpc(MSG_QUERY_TRIANGLE, {"node_id": int(node_id)})
        return self._rpc(MSG_QUERY_TRIANGLE, {})

    def get_stats(self):
        return self._rpc(MSG_QUERY_STATS, {})


class QueryThread(QThread):
    """后台查询线程，避免阻塞 UI"""
    finished = pyqtSignal(object, object)  # (method_name, data)
    error = pyqtSignal(str)

    def __init__(self, client, method, *args):
        super().__init__()
        self.client = client
        self.method = method
        self.args = args

    def run(self):
        try:
            fn = getattr(self.client, self.method)
            result = fn(*self.args)
            if isinstance(result, dict) and "error" in result and result["error"]:
                self.error.emit(str(result["error"]))
            else:
                self.finished.emit(self.method, result)
        except Exception as e:
            self.error.emit(str(e))


class StatusPoller(QThread):
    """状态自动刷新线程"""
    status_updated = pyqtSignal(dict)
    connection_lost = pyqtSignal()

    def __init__(self, client, interval=3):
        super().__init__()
        self.client = client
        self.interval = interval
        self.running = True
        self._consecutive_fails = 0

    def run(self):
        while self.running:
            stats = self.client.get_stats()
            if "error" not in stats:
                self._consecutive_fails = 0
                self.status_updated.emit(stats)
            else:
                self._consecutive_fails += 1
                if self._consecutive_fails >= 3:
                    self.connection_lost.emit()
            time.sleep(self.interval)

    def stop(self):
        self.running = False
