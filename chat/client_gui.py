"""
Simple Tkinter GUI chat client with AES-GCM encryption and KMS integration.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import queue
import threading
import time
from dataclasses import dataclass

import httpx
import tkinter as tk
from tkinter import ttk

import websockets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


@dataclass
class LinkStatus:
    status: str
    qber: float
    eve_mode: bool
    escalation_level: int


class AsyncWebsocketClient:
    def __init__(self, on_message, on_status):
        self.on_message = on_message
        self.on_status = on_status
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        self.websocket = None
        self.recv_task = None

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def _connect(self, ws_url: str):
        self.websocket = await websockets.connect(ws_url)
        self.on_status("connected")
        self.recv_task = asyncio.create_task(self._recv_loop())

    async def _recv_loop(self):
        try:
            async for raw in self.websocket:
                self.on_message(raw)
        except Exception as exc:
            self.on_status(f"disconnected: {exc}")

    async def _send(self, payload: str):
        if self.websocket is None:
            raise RuntimeError("websocket not connected")
        await self.websocket.send(payload)

    async def _close(self):
        if self.websocket is not None:
            await self.websocket.close()

    def connect(self, ws_url: str):
        return asyncio.run_coroutine_threadsafe(self._connect(ws_url), self.loop)

    def send(self, payload: str):
        return asyncio.run_coroutine_threadsafe(self._send(payload), self.loop)

    def close(self):
        return asyncio.run_coroutine_threadsafe(self._close(), self.loop)


class ChatGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Quantum Secure Chat")
        self.root.geometry("860x560")

        self.incoming = queue.Queue()
        self.status_queue = queue.Queue()

        self.ws_client = AsyncWebsocketClient(self._queue_message, self._queue_status)
        self.aesgcm: AESGCM | None = None
        self.session_id: str | None = None
        self.user_id: str = ""
        self.peer_id: str = ""
        self.kms_base: str = ""

        self._build_ui()
        self._poll_queues()

        threading.Thread(target=self._auto_discover_server, daemon=True).start()

    def _auto_discover_server(self):
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('', 54321))
        except Exception as e:
            self._queue_status(f"Discovery bind failed: {e}")
            return
            
        while True:
            try:
                data, addr = sock.recvfrom(1024)
                text = data.decode('utf-8')
                if text.startswith("QUANTUM_CHAT_ANNOUNCE"):
                    parts = text.split('|')
                    if len(parts) == 4:
                        server_ip = parts[1]
                        kms_port = parts[2]
                        ws_port = parts[3]
                    elif len(parts) == 3:
                        kms_port = parts[1]
                        ws_port = parts[2]
                        server_ip = addr[0]
                    else:
                        continue
                        
                    new_kms = f"http://{server_ip}:{kms_port}"
                    new_ws = f"ws://{server_ip}:{ws_port}"
                        
                    self.root.after(0, lambda k=new_kms, w=new_ws: self._update_urls(k, w))
            except Exception:
                pass

    def _update_urls(self, new_kms: str, new_ws: str):
        if self.kms_var.get() == "http://192.168.1.100:8000":
            self.kms_var.set(new_kms)
        if self.ws_var.get() == "ws://192.168.1.100:8765":
            self.ws_var.set(new_ws)

    def _build_ui(self):
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(frame)
        top.pack(fill=tk.X)

        self.user_var = tk.StringVar(value="Alice")
        self.peer_var = tk.StringVar(value="Bob")
        self.kms_var = tk.StringVar(value="http://192.168.1.100:8000")
        self.ws_var = tk.StringVar(value="ws://192.168.1.100:8765")
        self.new_session_var = tk.BooleanVar(value=True)
        self.hybrid_var = tk.BooleanVar(value=False)
        self.session_var = tk.StringVar(value="")

        ttk.Label(top, text="User").grid(row=0, column=0, sticky=tk.W, padx=4)
        ttk.Entry(top, textvariable=self.user_var, width=12).grid(row=0, column=1, sticky=tk.W)
        ttk.Label(top, text="Peer").grid(row=0, column=2, sticky=tk.W, padx=4)
        ttk.Entry(top, textvariable=self.peer_var, width=12).grid(row=0, column=3, sticky=tk.W)

        ttk.Label(top, text="KMS URL").grid(row=1, column=0, sticky=tk.W, padx=4)
        ttk.Entry(top, textvariable=self.kms_var, width=34).grid(row=1, column=1, columnspan=3, sticky=tk.W)

        ttk.Label(top, text="WS URL").grid(row=2, column=0, sticky=tk.W, padx=4)
        ttk.Entry(top, textvariable=self.ws_var, width=34).grid(row=2, column=1, columnspan=3, sticky=tk.W)

        ttk.Checkbutton(top, text="Create new session", variable=self.new_session_var).grid(
            row=0, column=4, sticky=tk.W, padx=8
        )
        ttk.Checkbutton(top, text="Use hybrid", variable=self.hybrid_var).grid(
            row=1, column=4, sticky=tk.W, padx=8
        )

        ttk.Label(top, text="Session ID").grid(row=2, column=4, sticky=tk.W, padx=8)
        ttk.Entry(top, textvariable=self.session_var, width=24).grid(row=2, column=5, sticky=tk.W)

        button_row = ttk.Frame(frame)
        button_row.pack(fill=tk.X, pady=(8, 0))

        ttk.Button(button_row, text="Connect", command=self.connect).pack(side=tk.LEFT, padx=4)
        ttk.Button(button_row, text="Disconnect", command=self.disconnect).pack(side=tk.LEFT, padx=4)
        ttk.Button(button_row, text="Link Status", command=self.fetch_status).pack(side=tk.LEFT, padx=4)
        ttk.Button(button_row, text="Activate Eve", command=lambda: self.control_eve(True)).pack(side=tk.LEFT, padx=4)
        ttk.Button(button_row, text="Deactivate Eve", command=lambda: self.control_eve(False)).pack(side=tk.LEFT, padx=4)
        ttk.Button(button_row, text="Trigger Attack", command=self.trigger_attack).pack(side=tk.LEFT, padx=4)

        self.log = tk.Text(frame, height=20, state=tk.DISABLED, wrap=tk.WORD)
        self.log.pack(fill=tk.BOTH, expand=True, pady=12)

        bottom = ttk.Frame(frame)
        bottom.pack(fill=tk.X)

        self.message_var = tk.StringVar()
        ttk.Entry(bottom, textvariable=self.message_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(bottom, text="Send", command=self.send_message).pack(side=tk.LEFT, padx=4)

        self.status_label = ttk.Label(frame, text="Status: idle")
        self.status_label.pack(anchor=tk.W, pady=(4, 0))

    def _queue_message(self, raw: str):
        self.incoming.put(raw)

    def _queue_status(self, msg: str):
        self.status_queue.put(msg)

    def _poll_queues(self):
        while not self.incoming.empty():
            raw = self.incoming.get_nowait()
            self._handle_incoming(raw)

        while not self.status_queue.empty():
            msg = self.status_queue.get_nowait()
            self._set_status(f"WebSocket {msg}")

        self.root.after(200, self._poll_queues)

    def _append_log(self, text: str):
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _set_status(self, text: str):
        self.status_label.configure(text=f"Status: {text}")

    def connect(self):
        threading.Thread(target=self._connect_worker, daemon=True).start()

    def _connect_worker(self):
        self.user_id = self.user_var.get().strip()
        self.peer_id = self.peer_var.get().strip()
        self.kms_base = self.kms_var.get().strip().rstrip("/")
        ws_url = self.ws_var.get().strip()

        if not self.user_id or not self.peer_id:
            self._set_status("Enter user and peer")
            return

        try:
            if self.new_session_var.get():
                use_hybrid = bool(self.hybrid_var.get())
                resp = httpx.post(
                    f"{self.kms_base}/create_session",
                    json={"client_a": self.user_id, "client_b": self.peer_id, "use_hybrid": use_hybrid},
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()
                self.session_id = data["session_id"]
                self.session_var.set(self.session_id)
                self._append_log(
                    f"Session created: {self.session_id} status={data['status']} qber={data['qber']:.3f}"
                )
            else:
                self.session_id = self.session_var.get().strip()
                if not self.session_id:
                    self._set_status("Provide session ID")
                    return

            key_resp = httpx.post(
                f"{self.kms_base}/get_key",
                json={"session_id": self.session_id, "client_id": self.user_id},
                timeout=10,
            )
            key_resp.raise_for_status()
            key_data = key_resp.json()
            aes_key = base64.b64decode(key_data["aes_key_b64"])
            self.aesgcm = AESGCM(aes_key)

            if "?" in ws_url:
                ws_url = f"{ws_url}&user_id={self.user_id}"
            else:
                ws_url = f"{ws_url}?user_id={self.user_id}"

            self.ws_client.connect(ws_url)
            self._set_status("connecting...")

        except Exception as exc:
            self._set_status(f"connect failed: {exc}")

    def disconnect(self):
        try:
            self.ws_client.close()
            self._set_status("disconnected")
        except Exception as exc:
            self._set_status(f"disconnect failed: {exc}")

    def send_message(self):
        if self.aesgcm is None or self.session_id is None:
            self._set_status("Not connected")
            return
        text = self.message_var.get().strip()
        if not text:
            return
        self.message_var.set("")

        nonce = os.urandom(12)
        ct = self.aesgcm.encrypt(nonce, text.encode("utf-8"), None)
        ciphertext, tag = ct[:-16], ct[-16:]

        payload = {
            "session_id": self.session_id,
            "from": self.user_id,
            "to": self.peer_id,
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
            "tag": base64.b64encode(tag).decode("ascii"),
            "timestamp": int(time.time()),
        }

        try:
            self.ws_client.send(json.dumps(payload))
            self._append_log(f"[me] {text}")
        except Exception as exc:
            self._set_status(f"send failed: {exc}")

    def _handle_incoming(self, raw: str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return

        if data.get("from") == self.user_id:
            return

        try:
            nonce = base64.b64decode(data["nonce"])
            ciphertext = base64.b64decode(data["ciphertext"])
            tag = base64.b64decode(data["tag"])
            plaintext = self.aesgcm.decrypt(nonce, ciphertext + tag, None)
            sender = data.get("from")
            self._append_log(f"[{sender}] {plaintext.decode('utf-8')}")
        except Exception as exc:
            self._append_log(f"[decrypt failed] {exc}")

    def fetch_status(self):
        threading.Thread(target=self._status_worker, daemon=True).start()

    def _status_worker(self):
        try:
            resp = httpx.get(f"{self.kms_base}/link_status", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            self._set_status(
                f"{data['status']} qber={data['qber']:.3f} eve={data['eve_mode']} level={data['escalation_level']}"
            )
        except Exception as exc:
            self._set_status(f"status failed: {exc}")

    def control_eve(self, on: bool):
        threading.Thread(target=self._control_eve_worker, args=(on,), daemon=True).start()

    def _control_eve_worker(self, on: bool):
        endpoint = "/activate_eve" if on else "/deactivate_eve"
        try:
            resp = httpx.post(f"{self.kms_base}{endpoint}", timeout=10)
            resp.raise_for_status()
            self._set_status(f"eve_mode={on}")
        except Exception as exc:
            self._set_status(f"eve toggle failed: {exc}")

    def trigger_attack(self):
        threading.Thread(target=self._trigger_attack_worker, daemon=True).start()

    def _trigger_attack_worker(self):
        try:
            resp = httpx.post(f"{self.kms_base}/trigger_attack", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            self._set_status(f"attack triggered qber={data['qber']:.3f}")
        except Exception as exc:
            self._set_status(f"trigger failed: {exc}")


def main():
    root = tk.Tk()
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    app = ChatGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
