"""End-to-end verification of the real session-based key exchange and encrypted chat."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kms.key_management_service import KeyManagementService
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

print("=" * 60)
print("  QSTCS End-to-End Verification")
print("=" * 60)

kms = KeyManagementService()

# --- 1. Proper session-based key exchange ---
print("\n[1] Alpha creates session with Bravo")
session = kms.create_session("Alpha", "Bravo")
key_a = session["key"]
sid = session["session_id"]
print(f"    Session: {sid}")
print(f"    QBER: {session['qber']:.2%}")
print(f"    Key (Alpha): {key_a.hex()[:24]}...")

print("\n[2] Bravo joins session")
joined = kms.join_session(sid, "Bravo")
key_b = joined["key"]
print(f"    Key (Bravo): {key_b.hex()[:24]}...")
print(f"    Keys identical: {key_a == key_b}")
assert key_a == key_b, "FAIL: keys don't match"

# --- 2. Real AES-256-GCM encryption + decryption ---
print("\n[3] Alpha encrypts a message")
message = "Grid ref 842156 — 2x armored vehicles moving east. Request CAS."
nonce = os.urandom(12)
ct = AESGCM(key_a).encrypt(nonce, message.encode(), None)
print(f"    Plaintext:  {message[:50]}...")
print(f"    Ciphertext: {ct.hex()[:48]}...")
print(f"    Nonce:      {nonce.hex()}")

print("\n[4] Bravo decrypts with same key")
pt = AESGCM(key_b).decrypt(nonce, ct, None).decode()
print(f"    Decrypted:  {pt[:50]}...")
print(f"    Match: {pt == message}")
assert pt == message, "FAIL: decrypted text doesn't match"

# --- 3. Attack detection ---
print("\n[5] Eve activates on quantum channel")
result = kms.trigger_attack()
print(f"    Status: {result['status']}")
print(f"    QBER:   {result['qber']:.2%}")
print(f"    Attacks detected: {result['attacks_detected']}")
assert result["status"] == "RED", "FAIL: should be RED"

# --- 4. Link health check ---
print("\n[6] Link health")
h = kms.check_link_health()
print(f"    Status: {h['status']}")
print(f"    Sessions: {h['total_sessions']}")
print(f"    Keys issued: {h['total_keys_issued']}")
print(f"    Eve active: {h['eve_active']}")

# --- 5. Reset and verify ---
print("\n[7] Reset")
kms.reset()
h = kms.check_link_health()
print(f"    Status after reset: {h['status']}")
assert h["status"] == "GREEN", "FAIL: should be GREEN after reset"

print("\n" + "=" * 60)
print("  ALL CHECKS PASSED ✓")
print("=" * 60)
