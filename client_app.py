"""
Chat Client Application
========================
Quantum-Safe Tactical Communication System - Field Device Client

Interactive terminal-based chat client that:
1. Fetches a quantum-derived AES-256 session key from the KMS server
2. Connects to the Chat Server via WebSocket
3. Encrypts outgoing messages with AES-256-GCM
4. Decrypts incoming messages and verifies authenticity

ENCRYPTION:
-----------
Uses the exact same AES-256-GCM scheme as devices/client.py:
  - 256-bit key from BB84 + HKDF
  - 12-byte (96-bit) random nonce per message
  - 128-bit authentication tag for tamper detection

USAGE:
------
    python client_app.py

You will be prompted for:
  - device_id   (e.g., "Soldier_Alpha")
  - recipient   (e.g., "Soldier_Bravo")
  - kms_url     (default: http://localhost:8000)
  - chat_url    (default: ws://localhost:8765)

Author: QSTCS Development Team
Classification: UNCLASSIFIED
"""

import asyncio
import json
import os
import sys
import time
from typing import Optional

try:
    import httpx
except ImportError:
    print("[Client] ERROR: 'httpx' not installed. Run: pip install httpx>=0.27.0")
    sys.exit(1)

try:
    import websockets
except ImportError:
    print("[Client] ERROR: 'websockets' not installed. Run: pip install websockets>=12.0")
    sys.exit(1)

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# =============================================================================
# CRYPTO HELPERS (mirrors devices/client.py exactly)
# =============================================================================

def encrypt_message(key: bytes, plaintext: str, sender: str, recipient: str) -> dict:
    """
    Encrypt a plaintext message using AES-256-GCM.

    Uses the same format as SoldierDevice.send_encrypted_message():
      - 12-byte random nonce (CRITICAL: never reuse with same key)
      - AES-256-GCM authenticated encryption
      - Returns JSON-serializable packet

    Args:
        key: 32-byte AES-256 session key
        plaintext: Message string to encrypt
        sender: Sender device ID
        recipient: Recipient device ID

    Returns:
        Message packet dict ready for WebSocket transmission
    """
    cipher = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit random nonce
    ciphertext = cipher.encrypt(nonce, plaintext.encode("utf-8"), None)

    return {
        "type": "chat",
        "sender": sender,
        "recipient": recipient,
        "nonce": nonce.hex(),
        "ciphertext": ciphertext.hex(),
        "timestamp": int(time.time()),
    }


def decrypt_message(key: bytes, packet: dict) -> Optional[str]:
    """
    Decrypt and verify an incoming AES-256-GCM encrypted message.

    Args:
        key: 32-byte AES-256 session key
        packet: Received message packet with nonce and ciphertext

    Returns:
        Decrypted plaintext string, or None if verification fails
    """
    try:
        cipher = AESGCM(key)
        nonce = bytes.fromhex(packet["nonce"])
        ciphertext = bytes.fromhex(packet["ciphertext"])
        plaintext_bytes = cipher.decrypt(nonce, ciphertext, None)
        return plaintext_bytes.decode("utf-8")
    except Exception as e:
        print(f"  ❌ Decryption failed: {e}")
        return None


# =============================================================================
# KMS CLIENT
# =============================================================================

def fetch_session_key(kms_url: str, device_id: str, pqc: bool = False) -> Optional[bytes]:
    """
    Request a quantum-derived session key from the KMS server.

    Calls POST /get_session_key and parses the response.
    If an attack is detected (status=RED), returns None.

    Args:
        kms_url: Base URL of the KMS server (e.g., http://192.168.1.100:8000)
        device_id: This device's identifier
        pqc: Enable hybrid PQC key derivation

    Returns:
        32-byte session key, or None if key exchange failed
    """
    endpoint = f"{kms_url}/get_session_key"

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                endpoint,
                json={"device_id": device_id, "force_attack": False, "pqc": pqc},
            )
            data = response.json()

        if "error" in data:
            print(f"  ❌ Key request FAILED: {data['error']}")
            print(f"  ⚠️  QBER = {data.get('qber', 'N/A')}")
            print(f"  🔴 Link Status: {data.get('status', 'UNKNOWN')}")
            return None

        key_hex = data["key_hex"]
        qber = data.get("qber", 0)
        status = data.get("status", "UNKNOWN")
        pqc_on = data.get("pqc_enabled", False)

        key_bytes = bytes.fromhex(key_hex)

        print(f"  ✓ Quantum key established ({len(key_bytes) * 8}-bit AES)")
        print(f"  ✓ QBER = {qber:.2%} | Status: {status}"
              + (f" | PQC Hybrid: ON" if pqc_on else ""))

        return key_bytes

    except httpx.ConnectError:
        print(f"  ❌ Cannot reach KMS at {kms_url}")
        print(f"     Make sure kms_server.py is running.")
        return None
    except Exception as e:
        print(f"  ❌ Key fetch error: {e}")
        return None


def check_link_status(kms_url: str) -> Optional[dict]:
    """Query the KMS for current link health."""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{kms_url}/link_status")
            return response.json()
    except Exception:
        return None


# =============================================================================
# CHAT CLIENT
# =============================================================================

async def sender_loop(
    websocket,
    key: bytes,
    device_id: str,
    recipient_id: str,
    kms_url: str,
):
    """
    Read user input from stdin and send encrypted messages.

    Runs as an async task alongside the receiver loop.
    Special commands:
      /status  — Check link status from KMS
      /rekey   — Request a fresh key
      /quit    — Disconnect
    """
    loop = asyncio.get_event_loop()
    current_key = key

    while True:
        try:
            # Read input in a thread to avoid blocking the event loop
            line = await loop.run_in_executor(None, sys.stdin.readline)

            if not line:
                break

            text = line.strip()
            if not text:
                continue

            # Handle special commands
            if text.lower() == "/quit":
                print(f"[{device_id}] Disconnecting...")
                await websocket.close()
                break

            elif text.lower() == "/status":
                status = check_link_status(kms_url)
                if status:
                    print(f"  📊 Link: {status['status']} | QBER: {status['qber']:.2%} | "
                          f"Keys: {status['total_keys_issued']} | "
                          f"Attacks: {status['attacks_detected']}")
                else:
                    print(f"  ⚠️  Cannot reach KMS")
                continue

            elif text.lower() == "/rekey":
                print(f"[{device_id}] Requesting fresh key...")
                new_key = fetch_session_key(kms_url, device_id)
                if new_key:
                    current_key = new_key
                    print(f"[{device_id}] ✓ Re-keyed successfully")
                else:
                    print(f"[{device_id}] ❌ Re-key failed")
                continue

            elif text.lower() == "/help":
                print("  Commands: /status /rekey /quit /help")
                continue

            # Encrypt and send
            packet = encrypt_message(current_key, text, device_id, recipient_id)
            await websocket.send(json.dumps(packet))

            ct_preview = packet["ciphertext"][:24] + "..."
            print(f"  📤 Sent (encrypted): {ct_preview}")

        except websockets.exceptions.ConnectionClosed:
            print(f"\n[{device_id}] ❌ Connection lost — quantum channel may be compromised.")
            print(f"[{device_id}] The router may have blocked traffic (RED status).")
            break
        except Exception as e:
            print(f"\n[{device_id}] ❌ Send error: {e}")
            break


async def receiver_loop(websocket, key: bytes, device_id: str):
    """
    Listen for incoming encrypted messages and decrypt them.

    Runs as an async task alongside the sender loop.
    """
    try:
        async for raw_message in websocket:
            try:
                data = json.loads(raw_message)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type", "")

            if msg_type == "chat":
                sender = data.get("sender", "UNKNOWN")
                plaintext = decrypt_message(key, data)

                if plaintext:
                    print(f"\n  📩 [{sender}]: {plaintext}")
                    print(f"  > ", end="", flush=True)
                else:
                    print(f"\n  ⚠️  Message from {sender} — decryption failed")
                    print(f"  > ", end="", flush=True)

            elif msg_type == "pong":
                pass  # Keepalive response, ignore

    except websockets.exceptions.ConnectionClosed:
        print(f"\n[{device_id}] ❌ Connection lost — quantum channel may be compromised.")
        print(f"[{device_id}] The router may have blocked traffic (RED status).")
    except Exception as e:
        print(f"\n[{device_id}] ❌ Receive error: {e}")


async def run_client(device_id: str, recipient_id: str, kms_url: str, chat_url: str):
    """
    Main client loop: fetch key, connect, chat.
    """
    print()
    print("=" * 60)
    print(f"  QSTCS Secure Chat — {device_id}")
    print("=" * 60)
    print()

    # --- Step 1: Fetch quantum-derived key from KMS ---
    print(f"[{device_id}] Requesting quantum-derived session key...")
    key = fetch_session_key(kms_url, device_id)

    if key is None:
        print(f"\n[{device_id}] Cannot establish secure channel. Exiting.")
        return

    # --- Step 2: Connect to Chat Server ---
    print(f"\n[{device_id}] Connecting to chat server at {chat_url}...")

    try:
        async with websockets.connect(chat_url) as websocket:
            # Register with the chat server
            reg_msg = json.dumps({"type": "register", "device_id": device_id})
            await websocket.send(reg_msg)

            print(f"[{device_id}] ✓ Connected to chat server")
            print()
            print("-" * 60)
            print(f"  Chatting with: {recipient_id}")
            print(f"  Encryption:   AES-256-GCM")
            print(f"  Commands:     /status /rekey /quit /help")
            print("-" * 60)
            print()
            print("  > ", end="", flush=True)

            # --- Step 3: Run sender and receiver concurrently ---
            sender_task = asyncio.create_task(
                sender_loop(websocket, key, device_id, recipient_id, kms_url)
            )
            receiver_task = asyncio.create_task(
                receiver_loop(websocket, key, device_id)
            )

            # Wait for either task to finish (disconnect or quit)
            done, pending = await asyncio.wait(
                [sender_task, receiver_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel the other task
            for task in pending:
                task.cancel()

    except websockets.exceptions.InvalidURI:
        print(f"[{device_id}] ❌ Invalid chat server URL: {chat_url}")
    except OSError as e:
        print(f"[{device_id}] ❌ Cannot connect to chat server: {e}")
        print(f"[{device_id}] Make sure chat_server.py is running and the router allows traffic.")
    except Exception as e:
        print(f"[{device_id}] ❌ Connection error: {e}")

    print(f"\n[{device_id}] Session ended.")


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Interactive setup and launch."""
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║   QSTCS — Quantum-Safe Tactical Communication System   ║")
    print("║                   Field Device Client                   ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    # Prompt for configuration
    device_id = input("  Device ID [Soldier_Alpha]: ").strip() or "Soldier_Alpha"
    recipient_id = input("  Recipient [Soldier_Bravo]: ").strip() or "Soldier_Bravo"
    kms_url = input("  KMS URL [http://localhost:8000]: ").strip() or "http://localhost:8000"
    chat_url = input("  Chat URL [ws://localhost:8765]: ").strip() or "ws://localhost:8765"

    try:
        asyncio.run(run_client(device_id, recipient_id, kms_url, chat_url))
    except KeyboardInterrupt:
        print(f"\n[{device_id}] Interrupted by user.")


if __name__ == "__main__":
    main()
