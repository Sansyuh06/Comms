"""
Soldier Device Client
=====================
Defense-Grade Implementation for QSTCS

This module implements the tactical field device client for the Quantum-Safe
Tactical Communication System. Each client represents a soldier's device
(laptop, ruggedized tablet, mobile unit) capable of secure communication.

CAPABILITIES:
-------------
1. Request quantum-derived keys from KMS
2. Encrypt outgoing messages with AES-256-GCM
3. Decrypt incoming messages and verify authenticity
4. Track message statistics

ENCRYPTION DETAILS:
-------------------
AES-256-GCM (Galois/Counter Mode) provides:
  - 256-bit key strength (quantum-resistant symmetric security)
  - Authenticated encryption (confidentiality + integrity)
  - 96-bit nonce for uniqueness
  - 128-bit authentication tag for tamper detection

MESSAGE FORMAT:
---------------
Encrypted messages are packaged as dictionaries containing:
  - sender: Device ID of sender
  - recipient: Intended recipient device ID
  - nonce: 12-byte random nonce (hex encoded)
  - ciphertext: Encrypted message (hex encoded)
  - timestamp: Unix timestamp of encryption

Author: QSTCS Development Team
Classification: UNCLASSIFIED
"""

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from typing import Optional, Dict, Any
import os
import time


# =============================================================================
# SOLDIER DEVICE CLIENT
# =============================================================================

class SoldierDevice:
    """
    Tactical field device client for secure communication.
    
    Each SoldierDevice instance represents a single field unit capable of
    requesting quantum-derived keys and performing authenticated encryption.
    
    Thread Safety:
    --------------
    Individual device instances are not thread-safe. Each thread should use
    its own device instance or implement external synchronization.
    
    Example:
        >>> from kms.key_management_service import KeyManagementService
        >>> kms = KeyManagementService()
        >>> device = SoldierDevice("Alpha_Unit", kms)
        >>> device.request_key()
        >>> msg = device.send_encrypted_message("Bravo_Unit", "Rally point: Grid 1234")
    
    Attributes:
        device_id: Unique identifier for this device
        current_key: Currently active session key (or None)
        messages_sent: Count of messages encrypted by this device
        messages_received: Count of messages decrypted by this device
    """
    
    def __init__(self, device_id: str, kms_service):
        """
        Initialize a soldier device.
        
        Args:
            device_id: Unique identifier for this device (e.g., "Alpha_Unit")
            kms_service: Reference to the Key Management Service
        """
        self.device_id = device_id
        self._kms = kms_service
        self._current_key: Optional[bytes] = None
        self._messages_sent = 0
        self._messages_received = 0
        
        print(f"[{self.device_id}] Device initialized")
    
    @property
    def current_key(self) -> Optional[bytes]:
        """Currently active session key."""
        return self._current_key
    
    @property
    def messages_sent(self) -> int:
        """Number of messages sent."""
        return self._messages_sent
    
    @property
    def messages_received(self) -> int:
        """Number of messages received."""
        return self._messages_received
    
    @property
    def has_key(self) -> bool:
        """Check if device has an active key."""
        return self._current_key is not None
    
    def request_key(self, force_attack: bool = False) -> bool:
        """
        Request a fresh encryption key from the KMS.
        
        This method contacts the Key Management Service to obtain a
        quantum-derived session key. The KMS will run BB84 QKD and
        validate the QBER before issuing the key.
        
        Args:
            force_attack: If True, simulate eavesdropper for testing
        
        Returns:
            True if key was successfully obtained, False otherwise
        
        Example:
            >>> device.request_key()
            [Alpha_Unit] Requesting key from KMS...
            [KMS] Device 'Alpha_Unit' requesting fresh key...
            [Alpha_Unit] ✓ Key established
            True
        """
        print(f"[{self.device_id}] Requesting key from KMS...")
        
        try:
            self._current_key = self._kms.get_fresh_key(
                self.device_id, 
                force_eve_attack=force_attack
            )
            print(f"[{self.device_id}] ✓ Key established")
            return True
        except Exception as e:
            print(f"[{self.device_id}] ❌ Key request failed: {e}")
            self._current_key = None
            return False
    
    def send_encrypted_message(
        self, 
        recipient_id: str, 
        plaintext: str
    ) -> Optional[Dict[str, Any]]:
        """
        Encrypt and prepare a message for transmission.
        
        Uses AES-256-GCM authenticated encryption to protect the message.
        The returned packet contains all information needed for the recipient
        to decrypt and verify the message.
        
        AES-GCM Security Properties:
        - Confidentiality: Message content is encrypted
        - Integrity: Any tampering is detected via auth tag
        - Authenticity: Only the holder of the key can create valid ciphertext
        
        Args:
            recipient_id: Device ID of intended recipient
            plaintext: Message content to encrypt
        
        Returns:
            Message packet dictionary ready for transmission, or None if no key
        
        Example:
            >>> packet = device.send_encrypted_message("Bravo_Unit", "Grid 1234")
            [Alpha_Unit] ✓ Encrypted message for 'Bravo_Unit'
            [Alpha_Unit]   Plaintext:  'Grid 1234'
            [Alpha_Unit]   Ciphertext: 4a8f2c1e9d3b7a...
        """
        if not self.has_key:
            print(f"[{self.device_id}] ❌ No key available. Call request_key() first.")
            return None
        
        # Initialize AES-GCM cipher with session key
        cipher = AESGCM(self._current_key)
        
        # Generate random 96-bit nonce
        # CRITICAL: Nonce must NEVER be reused with the same key
        nonce = os.urandom(12)
        
        # Encrypt with authentication
        # AAD (Additional Authenticated Data) could include sender/recipient
        # for binding, but we use None for simplicity
        plaintext_bytes = plaintext.encode('utf-8')
        ciphertext = cipher.encrypt(nonce, plaintext_bytes, None)
        
        # Package for transmission
        message_packet = {
            'sender': self.device_id,
            'recipient': recipient_id,
            'nonce': nonce.hex(),
            'ciphertext': ciphertext.hex(),
            'timestamp': int(time.time())
        }
        
        self._messages_sent += 1
        
        print(f"[{self.device_id}] ✓ Encrypted message for '{recipient_id}'")
        print(f"[{self.device_id}]   Plaintext:  '{plaintext}'")
        print(f"[{self.device_id}]   Ciphertext: {ciphertext.hex()[:32]}...")
        
        return message_packet
    
    def receive_encrypted_message(
        self, 
        message_packet: Dict[str, Any]
    ) -> Optional[str]:
        """
        Decrypt and verify an incoming message.
        
        Uses AES-256-GCM to decrypt the ciphertext and verify the
        authentication tag. If the message was tampered with, decryption
        will fail and return None.
        
        Args:
            message_packet: Encrypted message packet from sender
        
        Returns:
            Decrypted plaintext string, or None if decryption fails
        
        Raises:
            InvalidTag: If authentication fails (message was tampered)
        
        Example:
            >>> plaintext = device.receive_encrypted_message(packet)
            [Bravo_Unit] ✓ Message from 'Alpha_Unit' verified
            [Bravo_Unit]   Plaintext: 'Grid 1234'
            'Grid 1234'
        """
        if not self.has_key:
            print(f"[{self.device_id}] ❌ No key available for decryption")
            return None
        
        try:
            # Extract components
            sender = message_packet['sender']
            nonce = bytes.fromhex(message_packet['nonce'])
            ciphertext = bytes.fromhex(message_packet['ciphertext'])
            
            # Initialize cipher and decrypt
            cipher = AESGCM(self._current_key)
            plaintext_bytes = cipher.decrypt(nonce, ciphertext, None)
            plaintext = plaintext_bytes.decode('utf-8')
            
            self._messages_received += 1
            
            print(f"[{self.device_id}] ✓ Message from '{sender}' verified")
            print(f"[{self.device_id}]   Plaintext: '{plaintext}'")
            
            return plaintext
            
        except Exception as e:
            print(f"[{self.device_id}] ❌ Decryption failed: {e}")
            return None
    
    def clear_key(self) -> None:
        """
        Clear the current session key from memory.
        
        Should be called when:
        - Device is going offline
        - Key rotation is required
        - Session is ending
        """
        self._current_key = None
        print(f"[{self.device_id}] Session key cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get device statistics.
        
        Returns:
            Dictionary with device statistics
        """
        return {
            'device_id': self.device_id,
            'has_active_key': self.has_key,
            'messages_sent': self._messages_sent,
            'messages_received': self._messages_received
        }


# =============================================================================
# DEMONSTRATION
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Soldier Device Client - Demonstration")
    print("=" * 60)
    
    # Import KMS
    from kms.key_management_service import KeyManagementService
    
    # Initialize system
    kms = KeyManagementService()
    
    # Create two soldier devices
    soldier_a = SoldierDevice("Alpha_Unit", kms)
    soldier_b = SoldierDevice("Bravo_Unit", kms)
    
    print("\n[DEMO] Secure Message Exchange")
    print("-" * 40)
    
    # Alpha requests key and sends message
    if soldier_a.request_key():
        message = "Enemy spotted at Grid 1234. Request immediate support."
        packet = soldier_a.send_encrypted_message("Bravo_Unit", message)
        
        # Bravo requests key and decrypts
        if soldier_b.request_key():
            decrypted = soldier_b.receive_encrypted_message(packet)
            
            print("\n[DEMO] Verification")
            print("-" * 40)
            print(f"  Original:  '{message}'")
            print(f"  Decrypted: '{decrypted}'")
            print(f"  Match: {message == decrypted}")
    
    # Show stats
    print("\n[DEMO] Device Statistics")
    print("-" * 40)
    for device in [soldier_a, soldier_b]:
        stats = device.get_stats()
        print(f"  {stats['device_id']}: Sent={stats['messages_sent']}, Received={stats['messages_received']}")
