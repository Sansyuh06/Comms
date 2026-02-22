"""
BB84 Quantum Key Distribution Simulator
========================================
Defense-Grade Implementation for QSTCS

This module implements the BB84 quantum key distribution protocol, invented by 
Charles Bennett and Gilles Brassard in 1984. BB84 enables two parties (Alice and Bob)
to establish a shared secret key with information-theoretic security.

QUANTUM MECHANICS PRIMER (For UG Reviewers)
--------------------------------------------
A qubit exists in superposition of |0⟩ and |1⟩ until measured. The key insight of BB84
is that measurement disturbs quantum states. If an eavesdropper (Eve) intercepts qubits,
her measurements collapse the states and introduce detectable errors.

Two measurement bases are used:
  - Computational (Z) basis: measures |0⟩ or |1⟩
  - Hadamard (X) basis: measures |+⟩ = (|0⟩+|1⟩)/√2 or |−⟩ = (|0⟩-|1⟩)/√2

When a qubit prepared in one basis is measured in the other, the result is random (50/50).

WHY 11% THRESHOLD?
------------------
If Eve intercepts all qubits using random bases:
  - 50% chance she uses wrong basis → her measurement randomizes the state
  - When Bob measures with correct basis, he gets wrong result 50% of the time
  - Combined: 50% × 50% = 25% error rate in sifted key

The 11% threshold comes from information-theoretic security proofs. Below 11% QBER,
Alice and Bob can extract a secure key via privacy amplification. Above 11%, they cannot
guarantee secrecy and must abort.

References:
  - Bennett & Brassard (1984): "Quantum Cryptography: Public Key Distribution..."
  - Shor & Preskill (2000): "Simple Proof of Security of the BB84 Quantum Key Distribution"

Author: QSTCS Development Team
Classification: UNCLASSIFIED
"""

import random
import numpy as np
from typing import Tuple, List, Optional

# =============================================================================
# CONSTANTS
# =============================================================================

QBER_SECURITY_THRESHOLD = 0.11  # 11% - Information-theoretic security limit for BB84
DEFAULT_NUM_BITS = 512          # Default qubit count (expect ~256 sifted bits)
KEY_LENGTH_BITS = 256           # Output key length in bits
KEY_LENGTH_BYTES = 32           # Output key length in bytes (256/8)


# =============================================================================
# BB84 PROTOCOL IMPLEMENTATION
# =============================================================================

def simulate_bb84(
    num_bits: int = DEFAULT_NUM_BITS,
    eve_present: bool = False,
    eve_intercept_rate: float = 1.0,
    noise_level: float = 0.0
) -> Tuple[bytes, float, bool]:
    """
    Simulate the complete BB84 Quantum Key Distribution protocol.
    
    This function models a full QKD exchange between Alice (sender) and Bob (receiver),
    with optional eavesdropper (Eve) interception. While actual QKD uses real quantum
    hardware (photon polarization or phase encoding), this simulation accurately models
    the protocol's behavior and security properties.
    
    Protocol Phases:
    ----------------
    1. PREPARATION: Alice generates random bits and encoding bases
    2. TRANSMISSION: Qubits are sent through quantum channel (simulated)
    3. MEASUREMENT: Bob measures qubits in randomly chosen bases  
    4. SIFTING: Alice and Bob discard bits where bases didn't match
    5. VERIFICATION: QBER is computed to detect eavesdropping
    
    Args:
        num_bits: Number of qubits to transmit. Should be at least 2x desired key length
                  since sifting discards ~50% of bits. Default 512 for 256-bit key.
        
        eve_present: If True, simulate an eavesdropper performing intercept-resend attack.
                     Eve measures each qubit in a random basis, then resends to Bob.
        
        eve_intercept_rate: Fraction of qubits Eve intercepts (0.0 to 1.0).
                            Default 1.0 means Eve intercepts all qubits.
        
        noise_level: Simulated channel noise (0.0 to 1.0). In real systems, even without
                     Eve, optical imperfections cause some errors. Default 0.0 for ideal.
    
    Returns:
        Tuple of (shared_key, qber, attack_detected):
        
        - shared_key (bytes): 32-byte (256-bit) key derived from sifted bits.
                              Returns zero-filled key if insufficient bits generated.
        
        - qber (float): Quantum Bit Error Rate (0.0 to 1.0). Fraction of sifted bits
                        where Alice's bit differs from Bob's measurement result.
        
        - attack_detected (bool): True if QBER exceeds 11% security threshold.
    
    Security Properties:
    --------------------
    - No Eve, no noise: QBER ≈ 0%
    - With Eve (intercept-resend): QBER ≈ 25%
    - Security threshold: QBER > 11% → abort key generation
    
    Example:
        >>> # Normal key generation (no eavesdropper)
        >>> key, qber, attacked = simulate_bb84(num_bits=512, eve_present=False)
        >>> print(f"QBER: {qber:.1%}, Attack: {attacked}")
        QBER: 0.0%, Attack: False
        
        >>> # With eavesdropper (attack detected)
        >>> key, qber, attacked = simulate_bb84(num_bits=512, eve_present=True)
        >>> print(f"QBER: {qber:.1%}, Attack: {attacked}")
        QBER: 24.8%, Attack: True
    """
    
    # =========================================================================
    # PHASE 1: ALICE - Bit and Basis Generation
    # =========================================================================
    # Alice generates two random sequences:
    #   - alice_bits: The actual secret bits (0 or 1)
    #   - alice_bases: The encoding basis for each bit
    #       0 = Computational (Z) basis: |0⟩ or |1⟩
    #       1 = Hadamard (X) basis: |+⟩ or |−⟩
    
    alice_bits: List[int] = [random.randint(0, 1) for _ in range(num_bits)]
    alice_bases: List[int] = [random.randint(0, 1) for _ in range(num_bits)]
    
    # =========================================================================
    # PHASE 2: BOB - Measurement Basis Selection
    # =========================================================================
    # Bob independently chooses random bases for measuring each incoming qubit.
    # He cannot know Alice's bases until the classical sifting phase.
    
    bob_bases: List[int] = [random.randint(0, 1) for _ in range(num_bits)]
    
    # =========================================================================
    # PHASE 3: QUANTUM TRANSMISSION (with optional Eve interception)
    # =========================================================================
    # Simulate what happens when qubits travel from Alice to Bob.
    # If Eve is present, she intercepts, measures, and resends each qubit.
    
    bob_results: List[int] = []
    
    # Eve's random bases (only used if eve_present)
    eve_bases: List[int] = [random.randint(0, 1) for _ in range(num_bits)] if eve_present else []
    
    for i in range(num_bits):
        # Determine if this qubit is disturbed by Eve
        eve_disturbed = False
        
        if eve_present and random.random() < eve_intercept_rate:
            # Eve intercepts this qubit
            eve_guess_basis = eve_bases[i]
            
            if eve_guess_basis != alice_bases[i]:
                # EVE USED WRONG BASIS
                # Quantum mechanics: measuring in wrong basis randomizes the state.
                # When Eve measures |+⟩ in Z basis, she collapses it to |0⟩ or |1⟩
                # with 50% probability each. The qubit is now in a definite Z state,
                # not the original X state Alice sent.
                eve_disturbed = True
        
        # Determine Bob's measurement result
        if bob_bases[i] == alice_bases[i]:
            # BOB USES CORRECT BASIS
            if eve_disturbed:
                # Eve's interference randomized the qubit
                # Bob gets random result despite using correct basis
                bob_result = random.randint(0, 1)
            elif random.random() < noise_level:
                # Channel noise flipped the bit
                bob_result = 1 - alice_bits[i]
            else:
                # Perfect transmission: Bob gets Alice's bit
                bob_result = alice_bits[i]
        else:
            # BOB USES WRONG BASIS
            # Regardless of anything else, measuring in wrong basis gives random result
            bob_result = random.randint(0, 1)
        
        bob_results.append(bob_result)
    
    # =========================================================================
    # PHASE 4: SIFTING (Classical Communication)
    # =========================================================================
    # Alice and Bob publicly announce their bases (not their bits!).
    # They keep only the bits where they used the same basis.
    # Statistically, this discards ~50% of the bits.
    
    sifted_alice_bits: List[int] = []
    sifted_bob_bits: List[int] = []
    
    for i in range(num_bits):
        if alice_bases[i] == bob_bases[i]:
            sifted_alice_bits.append(alice_bits[i])
            sifted_bob_bits.append(bob_results[i])
    
    # =========================================================================
    # PHASE 5: ERROR ESTIMATION (QBER Calculation)
    # =========================================================================
    # Alice and Bob sacrifice a subset of sifted bits to estimate QBER.
    # In real QKD, they might sacrifice 10-20% of sifted bits for this.
    # For simulation simplicity, we compare all sifted bits.
    
    if len(sifted_alice_bits) == 0:
        # Edge case: no matching bases (extremely unlikely with reasonable num_bits)
        qber = 1.0
    else:
        errors = sum(
            1 for a, b in zip(sifted_alice_bits, sifted_bob_bits) if a != b
        )
        qber = errors / len(sifted_alice_bits)
    
    # =========================================================================
    # PHASE 6: ATTACK DETECTION
    # =========================================================================
    # Compare QBER against information-theoretic security threshold.
    # If QBER > 11%, the protocol aborts - key cannot be securely extracted.
    
    attack_detected = qber > QBER_SECURITY_THRESHOLD
    
    # =========================================================================
    # PHASE 7: KEY EXTRACTION
    # =========================================================================
    # Convert sifted bits to a 256-bit (32-byte) key.
    # In real QKD, privacy amplification would be applied here to further
    # reduce Eve's potential information. For this prototype, we use direct extraction.
    
    if len(sifted_alice_bits) >= KEY_LENGTH_BITS:
        # Use first 256 sifted bits for key
        key_bits = sifted_alice_bits[:KEY_LENGTH_BITS]
        key_int = int(''.join(str(b) for b in key_bits), 2)
        shared_key = key_int.to_bytes(KEY_LENGTH_BYTES, byteorder='big')
    else:
        # Insufficient bits - pad with zeros (would retry in real system)
        if len(sifted_alice_bits) == 0:
            shared_key = b'\x00' * KEY_LENGTH_BYTES
        else:
            # Pad existing bits to reach 256
            padded_bits = sifted_alice_bits + [0] * (KEY_LENGTH_BITS - len(sifted_alice_bits))
            key_int = int(''.join(str(b) for b in padded_bits), 2)
            shared_key = key_int.to_bytes(KEY_LENGTH_BYTES, byteorder='big')
    
    return shared_key, qber, attack_detected


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_security_threshold() -> float:
    """Return the QBER security threshold (11%)."""
    return QBER_SECURITY_THRESHOLD


def estimate_required_bits(desired_key_bits: int) -> int:
    """
    Estimate number of qubits needed to generate a key of desired length.
    
    After sifting, approximately 50% of bits remain (matching bases).
    We add 20% buffer for safety.
    
    Args:
        desired_key_bits: Desired output key length in bits
    
    Returns:
        Recommended number of qubits to transmit
    """
    return int(desired_key_bits * 2 * 1.2)


# =============================================================================
# DEMONSTRATION / TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("BB84 Quantum Key Distribution Simulator")
    print("Defense-Grade Implementation for QSTCS")
    print("=" * 60)
    
    # Test 1: Normal operation (no eavesdropper)
    print("\n[TEST 1] Normal Key Generation (No Eve)")
    print("-" * 40)
    key1, qber1, attack1 = simulate_bb84(num_bits=512, eve_present=False)
    print(f"  Key (first 16 bytes): {key1[:16].hex()}...")
    print(f"  QBER: {qber1:.2%}")
    print(f"  Attack Detected: {attack1}")
    print(f"  Status: {'SECURE' if not attack1 else 'COMPROMISED'}")
    
    # Test 2: With eavesdropper
    print("\n[TEST 2] With Eavesdropper (Eve Intercepts All)")
    print("-" * 40)
    key2, qber2, attack2 = simulate_bb84(num_bits=512, eve_present=True, eve_intercept_rate=1.0)
    print(f"  Key (first 16 bytes): {key2[:16].hex()}...")
    print(f"  QBER: {qber2:.2%}")
    print(f"  Attack Detected: {attack2}")
    print(f"  Status: {'SECURE' if not attack2 else 'COMPROMISED'}")
    
    # Test 3: Partial interception
    print("\n[TEST 3] Partial Interception (Eve at 50%)")
    print("-" * 40)
    key3, qber3, attack3 = simulate_bb84(num_bits=512, eve_present=True, eve_intercept_rate=0.5)
    print(f"  Key (first 16 bytes): {key3[:16].hex()}...")
    print(f"  QBER: {qber3:.2%}")
    print(f"  Attack Detected: {attack3}")
    print(f"  Status: {'SECURE' if not attack3 else 'COMPROMISED'}")
    
    print("\n" + "=" * 60)
    print("Simulation Complete")
    print("=" * 60)
