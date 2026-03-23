"""
Start all core services for the quantum-aware secure chat demo.

This launches:
- KMS API server
- WebSocket chat relay
- Optional GUI clients (default: 2)

Router guard is still run separately on a Linux/OpenWrt box.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time


def _launch(cmd: list[str]) -> subprocess.Popen:
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_CONSOLE
    return subprocess.Popen(cmd, creationflags=creationflags)


def _broadcast_presence(kms_port: int, chat_port: int):
    import socket
    import threading
    import time
    
    def _get_local_ip() -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return '127.0.0.1'
    
    def _loop():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # on windows SO_REUSEADDR usually works, sometimes we need to bind to specific interface
        while True:
            try:
                local_ip = _get_local_ip()
                message = f"QUANTUM_CHAT_ANNOUNCE|{local_ip}|{kms_port}|{chat_port}".encode('utf-8')
                sock.sendto(message, ('255.255.255.255', 54321))
            except Exception:
                pass
            time.sleep(3)
            
    t = threading.Thread(target=_loop, daemon=True)
    t.start()


def _check_for_existing_server() -> bool:
    import socket
    import time
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1.5)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', 54321))
    except Exception:
        pass
        
    start_time = time.time()
    while time.time() - start_time < 3.5:
        try:
            data, addr = sock.recvfrom(1024)
            text = data.decode('utf-8')
            if text.startswith("QUANTUM_CHAT_ANNOUNCE"):
                parts = text.split('|')
                server_ip = parts[1] if len(parts) >= 4 else addr[0]
                print(f"[*] Found existing Quantum Chat server at {server_ip}! Joining as client...")
                return True
        except socket.timeout:
            pass
        except Exception:
            pass
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Start all demo services")
    parser.add_argument("--kms-host", default="0.0.0.0")
    parser.add_argument("--kms-port", type=int, default=8000)
    parser.add_argument("--chat-host", default="0.0.0.0")
    parser.add_argument("--chat-port", type=int, default=8765)
    parser.add_argument("--clients", type=int, default=1, help="Number of GUI clients to open")
    parser.add_argument("--no-gui", action="store_true", help="Do not open GUI clients")
    args = parser.parse_args()

    python = sys.executable

    procs: list[subprocess.Popen] = []

    print("[*] Checking for existing servers on the local network (takes ~3 seconds)...")
    server_exists = _check_for_existing_server()

    try:
        if not server_exists:
            print("[*] No existing server found. Hosting a new Quantum Chat server...")
            procs.append(
            _launch(
                [
                    python,
                    "-m",
                    "kms.kms_server",
                    "--host",
                    args.kms_host,
                    "--port",
                    str(args.kms_port),
                ]
            )
        )

        procs.append(
            _launch(
                [
                    python,
                    "-m",
                    "chat.chat_server",
                    "--host",
                    args.chat_host,
                    "--port",
                    str(args.chat_port),
                ]
            )
        )

        if not server_exists:
            _broadcast_presence(args.kms_port, args.chat_port)
            print("Services launched.")
            print("KMS UI: http://<your_kms_ip>:8000/")

        if not args.no_gui:
            for _ in range(max(args.clients, 0)):
                procs.append(_launch([python, "-m", "chat.client_gui"]))

        print("Press Ctrl+C here to stop all child processes.")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        for proc in procs:
            try:
                if os.name == "nt":
                    proc.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    proc.terminate()
            except Exception:
                pass
        time.sleep(1)
        for proc in procs:
            try:
                if proc.poll() is None:
                    proc.kill()
            except Exception:
                pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
