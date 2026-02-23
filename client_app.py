"""
Chat Client
============
Quantum-Safe Tactical Communication System — Field Device

Terminal chat client that:
1. Creates or joins a key exchange session with a specific peer
2. Both sides get the same AES-256 key derived from BB84 + HKDF
3. Connects to the chat server via WebSocket
4. Encrypts/decrypts all messages with AES-256-GCM

Run with:
    python client_app.py

Author: QSTCS Development Team
Classification: UNCLASSIFIED
"""

import asyncio
import json
import os
import socket
import sys
import time
from typing import Optional

try:
    import httpx
except ImportError:
    print("ERROR: pip install httpx")
    sys.exit(1)

try:
    import websockets
except ImportError:
    print("ERROR: pip install websockets")
    sys.exit(1)

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# =============================================================================
# NETWORK UTILITY
# =============================================================================

def get_lan_ip() -> str:
    """Auto-detect this machine's LAN IP on the Wi-Fi network."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# =============================================================================
# AES-256-GCM CRYPTO
# =============================================================================

def encrypt(key: bytes, plaintext: str, sender: str, recipient: str) -> dict:
    """Encrypt plaintext with AES-256-GCM. 12-byte nonce, 128-bit tag."""
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return {
        "type": "chat",
        "sender": sender,
        "recipient": recipient,
        "nonce": nonce.hex(),
        "ciphertext": ct.hex(),
        "timestamp": int(time.time()),
    }


def decrypt(key: bytes, packet: dict) -> Optional[str]:
    """Decrypt and verify an AES-256-GCM message."""
    try:
        nonce = bytes.fromhex(packet["nonce"])
        ct = bytes.fromhex(packet["ciphertext"])
        return AESGCM(key).decrypt(nonce, ct, None).decode("utf-8")
    except Exception as e:
        return None


# =============================================================================
# SESSION-BASED KEY EXCHANGE
# =============================================================================

def establish_key(kms_url: str, device_id: str, peer_id: str) -> Optional[tuple]:
    """
    Establish a shared key with the peer through the KMS.

    Tries to create a session first. If the peer already created one,
    joins that session instead.

    Returns:
        (key_bytes, session_id, qber) or None on failure
    """
    with httpx.Client(timeout=10.0) as client:
        # Try to create a session (we're the initiator)
        print(f"[{device_id}] Requesting key exchange with {peer_id}...")

        resp = client.post(
            f"{kms_url}/create_session",
            json={"initiator": device_id, "peer": peer_id},
        )
        data = resp.json()

        if "error" in data:
            # Session creation failed — maybe QBER too high
            print(f"[{device_id}] ❌ Key exchange failed: {data['error']}")
            print(f"[{device_id}]    Status: {data.get('status', '?')} | "
                  f"QBER: {data.get('qber', '?')}")
            return None

        if "key_hex" in data:
            key = bytes.fromhex(data["key_hex"])
            sid = data["session_id"]
            qber = data["qber"]
            print(f"[{device_id}] ✓ Session {sid} | "
                  f"QBER={qber:.2%} | Status={data['status']}")
            return key, sid, qber

        print(f"[{device_id}] ❌ Unexpected response: {data}")
        return None


def join_existing_session(kms_url: str, device_id: str, session_id: str) -> Optional[tuple]:
    """Join a session that the peer already created."""
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(
            f"{kms_url}/join_session",
            json={"session_id": session_id, "device_id": device_id},
        )

        if resp.status_code != 200:
            print(f"[{device_id}] ❌ Join failed: {resp.text}")
            return None

        data = resp.json()
        key = bytes.fromhex(data["key_hex"])
        return key, data["session_id"], data["qber"]


# =============================================================================
# CHAT
# =============================================================================

async def send_loop(ws, key, device_id, peer_id, kms_url):
    """Read stdin, encrypt, send over WebSocket."""
    loop = asyncio.get_event_loop()

    while True:
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                break

            text = line.strip()
            if not text:
                continue

            if text == "/quit":
                await ws.close()
                break
            elif text == "/status":
                try:
                    with httpx.Client(timeout=5) as c:
                        r = c.get(f"{kms_url}/link_status").json()
                    print(f"  Link: {r['status']} | QBER: {r['qber']:.2%} | "
                          f"Eve: {'ACTIVE' if r.get('eve_active') else 'off'} | "
                          f"Sessions: {r['active_sessions']}")
                except Exception as e:
                    print(f"  KMS unreachable: {e}")
                continue
            elif text == "/help":
                print("  /status  /quit  /help")
                continue

            packet = encrypt(key, text, device_id, peer_id)
            await ws.send(json.dumps(packet))

        except websockets.exceptions.ConnectionClosed:
            print(f"\n[{device_id}] Connection lost — router may have blocked traffic (RED).")
            break
        except Exception as e:
            print(f"\n[{device_id}] Error: {e}")
            break


async def recv_loop(ws, key, device_id):
    """Listen for incoming messages, decrypt, print."""
    try:
        async for raw in ws:
            data = json.loads(raw)
            if data.get("type") == "chat":
                sender = data.get("sender", "?")
                plaintext = decrypt(key, data)
                if plaintext:
                    print(f"\n  [{sender}]: {plaintext}")
                    print("  > ", end="", flush=True)
                else:
                    print(f"\n  [{sender}]: <decryption failed>")
                    print("  > ", end="", flush=True)
    except websockets.exceptions.ConnectionClosed:
        print(f"\n[{device_id}] Connection lost.")
    except Exception as e:
        print(f"\n[{device_id}] Recv error: {e}")


async def chat(device_id, peer_id, kms_url, chat_url, key, session_id):
    """Connect to chat server and run send/recv loops."""
    print(f"[{device_id}] Connecting to {chat_url}...")

    try:
        async with websockets.connect(chat_url) as ws:
            await ws.send(json.dumps({"type": "register", "device_id": device_id}))
            print(f"[{device_id}] Connected. Chatting with {peer_id}.")
            print(f"  Session: {session_id} | Encryption: AES-256-GCM")
            print(f"  Commands: /status /quit /help")
            print()
            print("  > ", end="", flush=True)

            sender = asyncio.create_task(send_loop(ws, key, device_id, peer_id, kms_url))
            receiver = asyncio.create_task(recv_loop(ws, key, device_id))

            done, pending = await asyncio.wait(
                [sender, receiver], return_when=asyncio.FIRST_COMPLETED
            )
            for t in pending:
                t.cancel()

    except OSError as e:
        print(f"[{device_id}] Cannot connect to chat server: {e}")
        print(f"  Is chat_server.py running? Is the router allowing traffic?")


# =============================================================================
# MAIN
# =============================================================================

def main():
    lan_ip = get_lan_ip()
    default_kms = f"http://{lan_ip}:8000"
    default_chat = f"ws://{lan_ip}:8765"

    print()
    print("╔══════════════════════════════════════════╗")
    print("║  QSTCS — Quantum-Safe Secure Chat       ║")
    print("╚══════════════════════════════════════════╝")
    print(f"  Detected LAN IP: {lan_ip}")
    print()

    device_id = input("  Device ID [Soldier_Alpha]: ").strip() or "Soldier_Alpha"
    peer_id = input("  Peer ID   [Soldier_Bravo]: ").strip() or "Soldier_Bravo"
    kms_url = input(f"  KMS URL   [{default_kms}]: ").strip() or default_kms
    chat_url = input(f"  Chat URL  [{default_chat}]: ").strip() or default_chat

    # Option to join an existing session
    session_id = input("  Session ID (leave blank to create new): ").strip()

    print()

    if session_id:
        result = join_existing_session(kms_url, device_id, session_id)
    else:
        result = establish_key(kms_url, device_id, peer_id)

    if result is None:
        print(f"[{device_id}] Cannot establish secure channel. Exiting.")
        return

    key, sid, qber = result
    print(f"[{device_id}] Key: {key.hex()[:16]}... ({len(key)*8}-bit)")
    print()

    try:
        asyncio.run(chat(device_id, peer_id, kms_url, chat_url, key, sid))
    except KeyboardInterrupt:
        print(f"\n[{device_id}] Disconnected.")


if __name__ == "__main__":
    main()
