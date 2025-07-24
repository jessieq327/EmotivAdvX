import json
import threading
import time
import websocket
import ssl
from config import CLIENT_ID, CLIENT_SECRET

class CortexClient:
    def __init__(self):
        self.ws = None
        self.cortex_token = None
        self.session_id = None

        self.focus_value = None
        self.focus_timestamp = None

        self.ready = False
        self._poll_access = False  # 是否轮询 hasAccessRight

    def start(self):
        self.ws = websocket.WebSocketApp(
            "wss://localhost:6868",
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        t = threading.Thread(target=self.ws.run_forever, kwargs={'sslopt': {"cert_reqs": ssl.CERT_NONE}})
        t.daemon = True
        t.start()

    # ---------------- WebSocket callbacks ----------------
    def _on_open(self, _ws):
        print("[Cortex] Connected. Requesting access...")
        self._request_access()

    def _on_close(self, _ws, *args):
        print("[Cortex] WebSocket closed.")

    def _on_error(self, _ws, error):
        print("[Cortex] ERROR:", error)

    def _on_message(self, _ws, message):
        data = json.loads(message)

        # 错误处理
        if "error" in data:
            print("[Cortex][ERROR]", data["error"])
            # 应用未批准 -> 开始轮询
            if data["error"].get("code") == -32102 and not self._poll_access:
                print("[Cortex] Waiting for approval in Launcher...")
                self._poll_access = True
                self._has_access()
            return

        # 按 id 处理响应
        if "id" in data:
            if data["id"] == 0:  # requestAccess
                if data["result"].get("accessGranted"):
                    self._authorize()
                else:
                    print("[Cortex] Please approve this app in Launcher.")
                    self._poll_access = True
                    self._has_access()

            elif data["id"] == 98:  # hasAccessRight 轮询
                if data["result"].get("accessGranted"):
                    print("[Cortex] Access granted. Authorizing...")
                    self._poll_access = False
                    self._authorize()
                elif self._poll_access:
                    threading.Timer(2.0, self._has_access).start()

            elif data["id"] == 1:  # authorize
                self.cortex_token = data["result"]["cortexToken"]
                print("[Cortex] Authorized.")
                self._query_headsets()

            elif data["id"] == 2:  # queryHeadsets
                headsets = data["result"]
                if not headsets:
                    print("[Cortex] No headset (需要真实设备或开启虚拟设备)。")
                    return
                hid = headsets[0]["id"]
                print(f"[Cortex] Using headset: {hid}")
                self._create_session(hid)

            elif data["id"] == 3:  # createSession
                self.session_id = data["result"]["id"]
                print(f"[Cortex] Session created: {self.session_id}. Subscribing 'met'...")
                self._subscribe_met()

            elif data["id"] == 4:  # subscribe
                print("[Cortex] Subscribed to 'met'. Waiting for focus data...")
                self.ready = True

        # 流数据: met
        if "met" in data:
            met = data["met"]
            if isinstance(met, dict) and "foc" in met:
                first = self.focus_value is None
                self.focus_value = met["At"]
                self.focus_timestamp = time.time()
                if first:
                    print(f"[Cortex] First focus value: {self.focus_value}")

    # ---------------- Cortex API 调用 ----------------
    def _send(self, payload):
        self.ws.send(json.dumps(payload))

    def _request_access(self):
        self._send({
            "jsonrpc": "2.0",
            "method": "requestAccess",
            "params": {"clientId": CLIENT_ID, "clientSecret": CLIENT_SECRET},
            "id": 0
        })

    def _has_access(self):
        self._send({
            "jsonrpc": "2.0",
            "method": "hasAccessRight",
            "params": {"clientId": CLIENT_ID, "clientSecret": CLIENT_SECRET},
            "id": 98
        })

    def _authorize(self):
        # 带 debit:1 以启用 performance metrics（如果账号有权限会成功）
        self._send({
            "jsonrpc": "2.0",
            "method": "authorize",
            "params": {
                "clientId": CLIENT_ID,
                "clientSecret": CLIENT_SECRET,
                "debit": 1
            },
            "id": 1
        })

    def _query_headsets(self):
        self._send({
            "jsonrpc": "2.0",
            "method": "queryHeadsets",
            "params": {},
            "id": 2
        })

    def _create_session(self, headset_id):
        self._send({
            "jsonrpc": "2.0",
            "method": "createSession",
            "params": {
                "cortexToken": self.cortex_token,
                "headset": headset_id,
                "status": "active"
            },
            "id": 3
        })

    def _subscribe_met(self):
        self._send({
            "jsonrpc": "2.0",
            "method": "subscribe",
            "params": {
                "cortexToken": self.cortex_token,
                "session": self.session_id,
                "streams": ["met"]
            },
            "id": 4
        })

    # ---------------- 提供给 Flask 的接口 ----------------
    def get_status(self):
        return {
            "authorized": self.cortex_token is not None,
            "session_id": self.session_id,
            "subscribed": self.ready,
            "focus_value": self.focus_value,
            "focus_age_seconds": None if self.focus_timestamp is None else round(time.time() - self.focus_timestamp, 2)
        }

cortex_client = CortexClient()
