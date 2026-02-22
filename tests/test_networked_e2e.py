"""
Full networked end-to-end test.
Requires kms_server.py on :8000 and chat_server.py on :8765.
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx
import websockets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KMS = "http://localhost:8000"
CHAT = "ws://localhost:8765"

def p(tag, msg):
    print(f"  [{tag}] {msg}")

async def run_test():
    print("=" * 60)
    print("  Networked E2E Test — Real Session + Real WebSocket")
    print("=" * 60)

    # 1. Reset KMS
    with httpx.Client(timeout=5) as c:
        c.post(f"{KMS}/reset")
    p("KMS", "Reset OK")

    # 2. Alpha creates session
    with httpx.Client(timeout=10) as c:
        r = c.post(f"{KMS}/create_session", json={"initiator": "Alpha", "peer": "Bravo"})
        alpha_data = r.json()
    assert "key_hex" in alpha_data, f"Session creation failed: {alpha_data}"
    key_a = bytes.fromhex(alpha_data["key_hex"])
    sid = alpha_data["session_id"]
    p("Alpha", f"Session {sid} created | QBER={alpha_data['qber']:.2%}")

    # 3. Bravo joins session
    with httpx.Client(timeout=10) as c:
        r = c.post(f"{KMS}/join_session", json={"session_id": sid, "device_id": "Bravo"})
        bravo_data = r.json()
    key_b = bytes.fromhex(bravo_data["key_hex"])
    p("Bravo", f"Joined session {sid}")
    p("KEYS", f"Match: {key_a == key_b}")
    assert key_a == key_b

    # 4. Check link status via API
    with httpx.Client(timeout=5) as c:
        status = c.get(f"{KMS}/link_status").json()
    p("Link", f"Status={status['status']} | QBER={status['qber']:.2%}")
    assert status["status"] in ("GREEN", "YELLOW")

    # 5. Connect both clients to chat server
    ws_alpha = await websockets.connect(CHAT)
    await ws_alpha.send(json.dumps({"type": "register", "device_id": "Alpha"}))
    p("Alpha", "Connected to chat server")

    ws_bravo = await websockets.connect(CHAT)
    await ws_bravo.send(json.dumps({"type": "register", "device_id": "Bravo"}))
    p("Bravo", "Connected to chat server")

    await asyncio.sleep(0.3)

    # 6. Alpha sends encrypted message
    message = "Enemy armor at Grid 842156. 2x T-90 moving east. Request CAS."
    nonce = os.urandom(12)
    ct = AESGCM(key_a).encrypt(nonce, message.encode(), None)

    packet = {
        "type": "chat",
        "sender": "Alpha",
        "recipient": "Bravo",
        "nonce": nonce.hex(),
        "ciphertext": ct.hex(),
        "timestamp": int(time.time()),
    }
    await ws_alpha.send(json.dumps(packet))
    p("Alpha", f"Sent encrypted: {ct.hex()[:32]}...")

    # 7. Bravo receives and decrypts
    raw = await asyncio.wait_for(ws_bravo.recv(), timeout=5)
    received = json.loads(raw)
    dec_nonce = bytes.fromhex(received["nonce"])
    dec_ct = bytes.fromhex(received["ciphertext"])
    plaintext = AESGCM(key_b).decrypt(dec_nonce, dec_ct, None).decode()

    p("Bravo", f"Decrypted: {plaintext[:50]}...")
    p("VERIFY", f"Original matches decrypted: {plaintext == message}")
    assert plaintext == message

    # 8. Bravo replies
    reply = "Copy. CAS inbound ETA 5 mikes. Hold position."
    r_nonce = os.urandom(12)
    r_ct = AESGCM(key_b).encrypt(r_nonce, reply.encode(), None)

    r_packet = {
        "type": "chat",
        "sender": "Bravo",
        "recipient": "Alpha",
        "nonce": r_nonce.hex(),
        "ciphertext": r_ct.hex(),
        "timestamp": int(time.time()),
    }
    await ws_bravo.send(json.dumps(r_packet))
    p("Bravo", f"Sent reply encrypted")

    raw2 = await asyncio.wait_for(ws_alpha.recv(), timeout=5)
    received2 = json.loads(raw2)
    reply_dec = AESGCM(key_a).decrypt(
        bytes.fromhex(received2["nonce"]),
        bytes.fromhex(received2["ciphertext"]),
        None
    ).decode()
    p("Alpha", f"Got reply: {reply_dec}")
    assert reply_dec == reply

    # 9. Trigger attack → status RED
    with httpx.Client(timeout=10) as c:
        atk = c.post(f"{KMS}/trigger_attack").json()
    p("ATTACK", f"Status={atk['status']} | QBER={atk['qber']:.2%}")
    assert atk["status"] == "RED"

    # 10. Verify link status is RED
    with httpx.Client(timeout=5) as c:
        s2 = c.get(f"{KMS}/link_status").json()
    p("Link", f"After attack: {s2['status']}")
    assert s2["status"] == "RED"

    # 11. New session attempt should fail when Eve is active
    with httpx.Client(timeout=10) as c:
        fail = c.post(f"{KMS}/create_session", json={"initiator": "Charlie", "peer": "Delta"}).json()
    p("Charlie", f"Session attempt: {'BLOCKED' if 'error' in fail else 'unexpected success'}")
    assert "error" in fail

    # 12. Reset → GREEN
    with httpx.Client(timeout=5) as c:
        c.post(f"{KMS}/reset")
        s3 = c.get(f"{KMS}/link_status").json()
    p("Reset", f"Status: {s3['status']}")
    assert s3["status"] == "GREEN"

    # Cleanup
    await ws_alpha.close()
    await ws_bravo.close()

    print()
    print("=" * 60)
    print("  ALL 12 CHECKS PASSED ✓")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_test())
