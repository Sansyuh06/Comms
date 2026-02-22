"""
Chat Server (WebSocket Relay)
==============================
Quantum-Safe Tactical Communication System - Message Relay

This module implements a zero-knowledge WebSocket relay server that forwards
encrypted message packets between connected field devices without ever
accessing the plaintext content.

ZERO-KNOWLEDGE DESIGN:
-----------------------
The chat server operates on the principle that it should never have access
to cryptographic keys or plaintext messages. It routes opaque JSON packets
containing only ciphertext, nonces, and metadata. Even if the server is
fully compromised, no message content is exposed.

All chat traffic transits through the D-Link DSL-2750U router on port 8765.
When the router gatekeeper detects a quantum channel breach (RED status),
it blocks this port via iptables, physically severing the chat connection.

PROTOCOL:
---------
1. Client connects to ws://<server>:8765
2. Client sends: {"type": "register", "device_id": "Soldier_Alpha"}
3. Client sends chat: {"type": "chat", "sender": "...", "recipient": "...",
                        "nonce": "...", "ciphertext": "...", "timestamp": ...}
4. Server relays to recipient's websocket (or queues if offline)

Run with:
    python chat_server.py

Author: QSTCS Development Team
Classification: UNCLASSIFIED
"""

import asyncio
import json
import socket
import sys
from datetime import datetime
from typing import Dict, Optional

try:
    import websockets
    from websockets.server import serve
except ImportError:
    print("[ChatServer] ERROR: 'websockets' package not installed.")
    print("[ChatServer] Run: pip install websockets>=12.0")
    sys.exit(1)


# =============================================================================
# CONFIGURATION
# =============================================================================

HOST = "0.0.0.0"
PORT = 8765


# =============================================================================
# CHAT SERVER
# =============================================================================

class ChatServer:
    """
    Zero-knowledge WebSocket relay server.

    Routes encrypted message packets between connected clients without
    inspecting or storing the ciphertext content.

    Attributes:
        clients: Dictionary mapping device_id → websocket connection
        message_count: Total messages relayed
    """

    def __init__(self):
        self.clients: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.message_count: int = 0
        self._pending: Dict[str, list] = {}  # Offline message queue

    def timestamp(self) -> str:
        """Get formatted timestamp for logging."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    async def register(self, websocket, device_id: str):
        """Register a client connection."""
        self.clients[device_id] = websocket
        if device_id not in self._pending:
            self._pending[device_id] = []
        print(f"[ChatServer] {self.timestamp()} | ✓ '{device_id}' connected "
              f"({len(self.clients)} clients online)")

        # Deliver any pending messages
        if self._pending[device_id]:
            pending = self._pending[device_id]
            self._pending[device_id] = []
            for msg in pending:
                try:
                    await websocket.send(json.dumps(msg))
                    print(f"[ChatServer] {self.timestamp()} | 📨 Delivered queued "
                          f"message to '{device_id}'")
                except Exception as e:
                    print(f"[ChatServer] {self.timestamp()} | ⚠️  Failed to deliver "
                          f"queued message: {e}")

    async def unregister(self, device_id: str):
        """Unregister a client connection."""
        if device_id in self.clients:
            del self.clients[device_id]
            print(f"[ChatServer] {self.timestamp()} | ✗ '{device_id}' disconnected "
                  f"({len(self.clients)} clients online)")

    async def route_message(self, message: dict):
        """
        Route an encrypted message to its intended recipient.

        The server ONLY reads the 'recipient' field for routing.
        It does NOT inspect nonce, ciphertext, or any crypto fields.
        """
        sender = message.get("sender", "UNKNOWN")
        recipient = message.get("recipient", "UNKNOWN")

        self.message_count += 1

        # Compute ciphertext size for logging (without exposing content)
        ct_hex = message.get("ciphertext", "")
        ct_bytes = len(ct_hex) // 2

        if recipient in self.clients:
            try:
                await self.clients[recipient].send(json.dumps(message))
                print(f"[ChatServer] {self.timestamp()} | 📨 #{self.message_count}: "
                      f"{sender} → {recipient} ({ct_bytes} bytes ciphertext)")
            except Exception as e:
                print(f"[ChatServer] {self.timestamp()} | ⚠️  Delivery failed to "
                      f"'{recipient}': {e}")
                # Queue for later
                if recipient not in self._pending:
                    self._pending[recipient] = []
                self._pending[recipient].append(message)
        else:
            print(f"[ChatServer] {self.timestamp()} | ⏳ #{self.message_count}: "
                  f"{sender} → {recipient} (OFFLINE — message queued)")
            if recipient not in self._pending:
                self._pending[recipient] = []
            self._pending[recipient].append(message)

    async def handler(self, websocket):
        """
        Handle a single WebSocket client connection.

        Protocol:
        1. First message must be registration: {"type": "register", "device_id": "..."}
        2. Subsequent messages are chat packets to be relayed.
        """
        device_id: Optional[str] = None

        try:
            async for raw_message in websocket:
                try:
                    data = json.loads(raw_message)
                except json.JSONDecodeError:
                    print(f"[ChatServer] {self.timestamp()} | ⚠️  Invalid JSON received")
                    continue

                msg_type = data.get("type", "")

                if msg_type == "register":
                    device_id = data.get("device_id", "UNKNOWN")
                    await self.register(websocket, device_id)

                elif msg_type == "chat":
                    if device_id is None:
                        print(f"[ChatServer] {self.timestamp()} | ⚠️  Chat message "
                              f"from unregistered client — ignored")
                        continue
                    await self.route_message(data)

                elif msg_type == "ping":
                    # Keepalive
                    await websocket.send(json.dumps({"type": "pong"}))

                else:
                    print(f"[ChatServer] {self.timestamp()} | ⚠️  Unknown message "
                          f"type: '{msg_type}'")

        except websockets.exceptions.ConnectionClosedError:
            pass
        except websockets.exceptions.ConnectionClosedOK:
            pass
        except Exception as e:
            print(f"[ChatServer] {self.timestamp()} | ❌ Connection error: {e}")
        finally:
            if device_id:
                await self.unregister(device_id)


# =============================================================================
# SERVER STARTUP
# =============================================================================

def get_lan_ip() -> str:
    """Attempt to discover the LAN IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


async def main():
    """Start the WebSocket chat relay server."""
    server = ChatServer()
    lan_ip = get_lan_ip()

    print()
    print("=" * 70)
    print("  QSTCS Chat Server (WebSocket Relay) — ONLINE")
    print("=" * 70)
    print(f"  Local:    ws://127.0.0.1:{PORT}")
    print(f"  LAN:      ws://{lan_ip}:{PORT}")
    print()
    print("  Design: Zero-knowledge relay (never sees plaintext)")
    print("  Router:  All traffic transits D-Link on port {PORT}")
    print("           iptables will DROP this port when status = RED")
    print("=" * 70)
    print()
    print(f"[ChatServer] Listening for connections on {HOST}:{PORT}...")
    print()

    async with serve(server.handler, HOST, PORT):
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[ChatServer] Shutting down...")
