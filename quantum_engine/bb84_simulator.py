"""
Lightweight BB84-style QKD simulator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Tuple
import random

QBER_THRESHOLD = 0.11
QBER_SECURITY_THRESHOLD = 0.11   # alias used by tests and dashboard
DEFAULT_NOISE_RATE = 0.01


def _bits_to_bytes(bits: List[int]) -> bytes:
    if not bits:
        return b""
    pad = (-len(bits)) % 8
    if pad:
        bits = bits + [0] * pad
    out = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | (bits[i + j] & 1)
        out.append(byte)
    return bytes(out)


@dataclass
class BB84Result:
    session_id: str
    raw_key: bytes
    qber: float
    attack_detected: bool


def run_bb84_session(
    session_id: str,
    num_bits: int = 256,
    eve: bool = False,
    rng_seed: int | None = None,
    eve_intercept_rate: float = 1.0,
) -> Dict[str, object]:
    """
    Simulates one BB84 key exchange.
    Returns:
    {
      "session_id": str,
      "raw_key": bytes,
      "qber": float,
      "attack_detected": bool
    }
    """

    rng = random.Random(rng_seed)

    alice_bits = [rng.randint(0, 1) for _ in range(num_bits)]
    alice_bases = [rng.randint(0, 1) for _ in range(num_bits)]

    bob_bits: List[int] = []
    bob_bases: List[int] = []

    for i in range(num_bits):
        alice_bit = alice_bits[i]
        alice_basis = alice_bases[i]

        if eve and rng.random() < eve_intercept_rate:
            eve_basis = rng.randint(0, 1)
            if eve_basis == alice_basis:
                eve_bit = alice_bit
            else:
                eve_bit = rng.randint(0, 1)

            bob_basis = rng.randint(0, 1)
            if bob_basis == eve_basis:
                bob_bit = eve_bit
            else:
                bob_bit = rng.randint(0, 1)
        else:
            bob_basis = rng.randint(0, 1)
            if bob_basis == alice_basis:
                if rng.random() < DEFAULT_NOISE_RATE:
                    bob_bit = 1 - alice_bit
                else:
                    bob_bit = alice_bit
            else:
                bob_bit = rng.randint(0, 1)

        bob_bits.append(bob_bit)
        bob_bases.append(bob_basis)

    sifted_alice: List[int] = []
    sifted_bob: List[int] = []
    errors = 0

    for i in range(num_bits):
        if alice_bases[i] == bob_bases[i]:
            sifted_alice.append(alice_bits[i])
            sifted_bob.append(bob_bits[i])
            if alice_bits[i] != bob_bits[i]:
                errors += 1

    total = len(sifted_alice)
    qber = (errors / total) if total else 1.0

    raw_key = _bits_to_bytes(sifted_bob)
    attack_detected = qber >= QBER_THRESHOLD

    result = BB84Result(
        session_id=session_id,
        raw_key=raw_key,
        qber=qber,
        attack_detected=attack_detected,
    )

    return {
        "session_id": result.session_id,
        "raw_key": result.raw_key,
        "qber": result.qber,
        "attack_detected": result.attack_detected,
    }


def simulate_bb84(
    num_bits: int = 512,
    eve_present: bool = False,
    eve_intercept_rate: float = 1.0,
) -> Tuple[bytes, float, bool]:
    """
    Compatibility alias used by tests and dashboard.
    Returns (key_bytes_32, qber, attack_detected).
    Always returns exactly 32 bytes by padding or truncating via HKDF.
    """
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives import hashes

    result = run_bb84_session(
        session_id="sim",
        num_bits=num_bits,
        eve=eve_present,
        rng_seed=None,
        eve_intercept_rate=eve_intercept_rate,
    )

    raw = result["raw_key"]
    if not raw:
        raw = b"\x00" * 32

    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"bb84-simulate-compat",
    )
    key_32 = hkdf.derive(raw)

    return key_32, result["qber"], result["attack_detected"]


if __name__ == "__main__":
    demo = run_bb84_session("demo", num_bits=256, eve=False, rng_seed=42)
    print("BB84 demo session:")
    print({k: (v if k != "raw_key" else f"{len(v)} bytes") for k, v in demo.items()})
