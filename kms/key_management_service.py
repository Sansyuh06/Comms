"""
Key Management Service (KMS)
============================
Defense-Grade Implementation for QSTCS

The KMS is the central authority for cryptographic key lifecycle management in the
Quantum-Safe Tactical Communication System. It bridges the quantum key distribution
layer (BB84 simulator) with the classical encryption layer (AES-256-GCM).

RESPONSIBILITIES:
-----------------
1. Receive key requests from authenticated field devices
2. Invoke BB84 quantum key distribution
3. Validate key integrity via QBER analysis
4. Derive session keys using HKDF-SHA256
5. Track active sessions and key usage
6. Detect and respond to eavesdropping attacks
7. Maintain link health status for SOC monitoring

SECURITY MODEL:
---------------
- KMS operates within a trusted security perimeter
- All key material exists only in volatile memory
- No persistent key storage reduces attack surface
- QBER threshold enforcement prevents compromised key issuance

KEY DERIVATION:
---------------
Raw BB84 keys are processed through HKDF (HMAC-based Key Derivation Function)
using SHA-256. This provides:
  - Key stretching/compression to exactly 256 bits
  - Domain separation via info parameter (device_id)
  - Defense-in-depth even if BB84 output has minor biases

Author: QSTCS Development Team
Classification: UNCLASSIFIED
"""

from quantum_engine.bb84_simulator import simulate_bb84, QBER_SECURITY_THRESHOLD
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import threading


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class LinkStatus(Enum):
    """Quantum link health status."""
    GREEN = "GREEN"     # Link secure, keys can be issued
    YELLOW = "YELLOW"   # Elevated QBER, proceed with caution
    RED = "RED"         # Attack detected, key issuance blocked


@dataclass
class SessionRecord:
    """Record of an active key session."""
    device_id: str
    key: bytes
    timestamp: datetime
    qber: float
    status: str = "ACTIVE"
    messages_encrypted: int = 0


@dataclass
class KMSMetrics:
    """KMS operational metrics for monitoring."""
    total_keys_issued: int = 0
    attacks_detected: int = 0
    active_sessions: int = 0
    last_qber: float = 0.0
    link_status: LinkStatus = LinkStatus.GREEN


# =============================================================================
# KEY MANAGEMENT SERVICE
# =============================================================================

class KeyManagementService:
    """
    Central Key Management Service for QSTCS.
    
    The KMS handles all key generation, derivation, and distribution for the
    tactical communication network. It enforces quantum security by validating
    QBER thresholds before issuing any keys.
    
    Thread Safety:
    --------------
    This implementation uses threading locks to ensure thread-safe operation
    when multiple devices request keys concurrently.
    
    Usage:
        >>> kms = KeyManagementService()
        >>> key = kms.get_fresh_key("Soldier_Alpha")
        >>> print(f"Key issued: {key.hex()[:32]}...")
    
    Attributes:
        sessions: Dict of active session records keyed by device_id
        metrics: Operational metrics for SOC dashboard
        last_key: Most recent key issued (for demo key sharing)
    """
    
    def __init__(self, qber_threshold: float = QBER_SECURITY_THRESHOLD):
        """
        Initialize the Key Management Service.
        
        Args:
            qber_threshold: Maximum acceptable QBER (default: 11%)
        """
        self._lock = threading.Lock()
        self._sessions: Dict[str, SessionRecord] = {}
        self._metrics = KMSMetrics()
        self._qber_threshold = qber_threshold
        self._last_key: Optional[bytes] = None
        self._last_key_device: Optional[str] = None
        
        print("[KMS] Key Management Service initialized")
        print(f"[KMS] QBER security threshold: {qber_threshold:.1%}")
    
    @property
    def link_status(self) -> str:
        """Current link status as string."""
        return self._metrics.link_status.value
    
    @property
    def attack_detected_count(self) -> int:
        """Total number of attacks detected."""
        return self._metrics.attacks_detected
    
    @property
    def total_keys_issued(self) -> int:
        """Total keys successfully issued."""
        return self._metrics.total_keys_issued
    
    def get_fresh_key(
        self, 
        device_id: str, 
        force_eve_attack: bool = False,
        num_bits: int = 512
    ) -> bytes:
        """
        Generate and issue a fresh encryption key for a device.
        
        This is the primary interface for devices to obtain quantum-derived
        cryptographic keys. The method:
        
        1. Runs BB84 quantum key distribution
        2. Validates QBER is below security threshold
        3. Derives AES-256 session key via HKDF
        4. Records session for tracking
        5. Returns key to device
        
        Key Sharing (Demo Mode):
        ------------------------
        For demonstration purposes, when a second device requests a key shortly
        after the first (e.g., Soldier_B after Soldier_A), the same session key
        is returned to enable encrypted communication between them.
        
        Args:
            device_id: Unique identifier for the requesting device
            force_eve_attack: If True, simulate eavesdropper for demo/testing
            num_bits: Number of qubits for BB84 (default: 512)
        
        Returns:
            32-byte (256-bit) AES session key
        
        Raises:
            Exception: If QBER exceeds threshold (attack detected)
        
        Example:
            >>> kms = KeyManagementService()
            >>> try:
            ...     key = kms.get_fresh_key("Alpha_Unit", force_eve_attack=True)
            ... except Exception as e:
            ...     print(f"Key exchange failed: {e}")
            Key exchange failed: QKD link compromised! QBER=25.0% exceeds 11% threshold
        """
        with self._lock:
            print(f"\n[KMS] Device '{device_id}' requesting fresh key...")
            
            # =================================================================
            # DEMO MODE: Key Sharing Between Devices
            # =================================================================
            # In real QKD, both parties participate in the protocol.
            # For this demo, we allow a second device to retrieve the same key.
            if self._last_key is not None and self._last_key_device != device_id:
                print(f"[KMS] Sharing session key with '{device_id}'")
                return self._last_key
            
            # =================================================================
            # PHASE 1: Quantum Key Distribution
            # =================================================================
            print(f"[KMS] Executing BB84 protocol ({num_bits} qubits)...")
            
            raw_key, qber, attack_detected = simulate_bb84(
                num_bits=num_bits,
                eve_present=force_eve_attack,
                eve_intercept_rate=1.0 if force_eve_attack else 0.0
            )
            
            self._metrics.last_qber = qber
            print(f"[KMS] BB84 complete. QBER = {qber:.2%}")
            
            # =================================================================
            # PHASE 2: Security Validation
            # =================================================================
            if attack_detected or qber > self._qber_threshold:
                self._metrics.link_status = LinkStatus.RED
                self._metrics.attacks_detected += 1
                print(f"[KMS] ⚠️  ATTACK DETECTED! QBER = {qber:.2%}")
                print(f"[KMS] Key issuance BLOCKED. Link status: RED")
                raise Exception(
                    f"QKD link compromised! QBER={qber:.1%} exceeds "
                    f"{self._qber_threshold:.0%} threshold"
                )
            
            # Update link status based on QBER
            if qber < 0.05:
                self._metrics.link_status = LinkStatus.GREEN
                print(f"[KMS] ✓ Link secure. QBER = {qber:.2%} (excellent)")
            elif qber < self._qber_threshold:
                self._metrics.link_status = LinkStatus.YELLOW
                print(f"[KMS] ⚡ Link secure. QBER = {qber:.2%} (elevated)")
            
            # =================================================================
            # PHASE 3: Key Derivation (HKDF-SHA256)
            # =================================================================
            # HKDF provides:
            # - Defense-in-depth if raw key has minor biases
            # - Domain separation via info parameter
            # - Consistent 256-bit output regardless of input length
            
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,  # 256 bits
                salt=None,  # Optional salt for extra randomness
                info=f"QSTCS-SessionKey-{device_id}".encode(),
                backend=default_backend()
            )
            session_key = hkdf.derive(raw_key)
            
            # =================================================================
            # PHASE 4: Session Recording
            # =================================================================
            session = SessionRecord(
                device_id=device_id,
                key=session_key,
                timestamp=datetime.now(),
                qber=qber,
                status="ACTIVE"
            )
            self._sessions[device_id] = session
            self._metrics.total_keys_issued += 1
            self._metrics.active_sessions = len(self._sessions)
            
            # Store for key sharing (demo mode)
            self._last_key = session_key
            self._last_key_device = device_id
            
            print(f"[KMS] ✓ Fresh key issued to '{device_id}'")
            print(f"[KMS]   Session key: {session_key.hex()[:32]}...")
            
            return session_key
    
    def check_link_health(self) -> Dict[str, Any]:
        """
        Get current link health status and metrics.
        
        Returns:
            Dictionary with:
            - status: Current link status (GREEN/YELLOW/RED)
            - total_keys_issued: Total successful key issuances
            - attacks_detected: Count of detected eavesdropping attempts
            - active_sessions: Number of currently active sessions
            - last_qber: Most recent QBER measurement
        """
        with self._lock:
            return {
                'status': self._metrics.link_status.value,
                'total_keys_issued': self._metrics.total_keys_issued,
                'attacks_detected': self._metrics.attacks_detected,
                'active_sessions': self._metrics.active_sessions,
                'last_qber': self._metrics.last_qber
            }
    
    def invalidate_session(self, device_id: str) -> bool:
        """
        Invalidate a device's session key.
        
        Called when a device disconnects or key rotation is required.
        
        Args:
            device_id: Device identifier
        
        Returns:
            True if session was found and invalidated, False otherwise
        """
        with self._lock:
            if device_id in self._sessions:
                self._sessions[device_id].status = "REVOKED"
                del self._sessions[device_id]
                self._metrics.active_sessions = len(self._sessions)
                print(f"[KMS] Session invalidated for '{device_id}'")
                return True
            return False
    
    def reset_for_demo(self) -> None:
        """Reset KMS state for demonstration purposes."""
        with self._lock:
            self._sessions.clear()
            self._metrics = KMSMetrics()
            self._last_key = None
            self._last_key_device = None
            print("[KMS] State reset for demonstration")


# =============================================================================
# DEMONSTRATION
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Key Management Service - Demonstration")
    print("=" * 60)
    
    kms = KeyManagementService()
    
    # Test 1: Normal key request
    print("\n[DEMO] Test 1: Normal Key Request")
    print("-" * 40)
    try:
        key1 = kms.get_fresh_key("Alpha_Unit")
        print(f"  Success: Key issued to Alpha_Unit")
    except Exception as e:
        print(f"  Failed: {e}")
    
    # Test 2: Second device gets same key (demo mode)
    print("\n[DEMO] Test 2: Key Sharing")
    print("-" * 40)
    try:
        key2 = kms.get_fresh_key("Bravo_Unit")
        print(f"  Keys match: {key1 == key2}")
    except Exception as e:
        print(f"  Failed: {e}")
    
    # Test 3: Attack detection
    print("\n[DEMO] Test 3: Attack Detection")
    print("-" * 40)
    kms.reset_for_demo()
    try:
        key3 = kms.get_fresh_key("Charlie_Unit", force_eve_attack=True)
        print(f"  Unexpected success")
    except Exception as e:
        print(f"  Attack blocked as expected: {str(e)[:50]}...")
    
    # Check metrics
    print("\n[DEMO] Final Metrics")
    print("-" * 40)
    health = kms.check_link_health()
    for key, value in health.items():
        print(f"  {key}: {value}")
