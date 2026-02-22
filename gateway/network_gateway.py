"""
Network Gateway
===============
Defense-Grade Implementation for QSTCS

The Network Gateway acts as the tactical network infrastructure connecting
field devices to the Key Management Service and to each other. It routes
encrypted message packets between devices.

DESIGN PRINCIPLES:
------------------
1. TRANSPARENCY: Gateway handles only ciphertext, never plaintext
2. ZERO-KNOWLEDGE: Gateway cannot decrypt messages even if compromised
3. LOGGING: All routing activity is logged for audit purposes
4. RESILIENCE: Message queue handles temporary disconnections

SECURITY MODEL:
---------------
The gateway operates on a zero-knowledge principle. Even if an adversary
compromises the gateway, they obtain only:
  - Message metadata (sender, recipient, timestamp)
  - Encrypted ciphertext (indistinguishable from random data)

Primary security relies on the quantum-derived symmetric keys, not the
gateway infrastructure. TLS transport provides defense-in-depth.

Author: QSTCS Development Team
Classification: UNCLASSIFIED
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque
import threading


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class RoutingRecord:
    """Record of a routed message for audit trail."""
    message_id: int
    sender: str
    recipient: str
    timestamp: datetime
    size_bytes: int
    status: str = "DELIVERED"


@dataclass
class DeviceRegistration:
    """Registered device information."""
    device_id: str
    registered_at: datetime
    last_seen: datetime
    message_count: int = 0


# =============================================================================
# NETWORK GATEWAY
# =============================================================================

class NetworkGateway:
    """
    Tactical network gateway for message routing.
    
    The gateway provides message routing services between field devices.
    It maintains a registry of connected devices and routes encrypted
    messages to their intended recipients.
    
    Zero-Knowledge Design:
    ----------------------
    The gateway never accesses message content. It routes opaque ciphertext
    packets, providing infrastructure security through network isolation
    while application security comes from quantum-derived keys.
    
    Thread Safety:
    --------------
    All operations are thread-safe using internal locks.
    
    Example:
        >>> gateway = NetworkGateway()
        >>> gateway.register_device("Alpha_Unit")
        >>> gateway.register_device("Bravo_Unit")
        >>> gateway.route_message(encrypted_packet)
    
    Attributes:
        routing_log: List of all routing records for audit
        registered_devices: Dictionary of connected devices
    """
    
    def __init__(self, gateway_id: str = "TacNet_Gateway_01"):
        """
        Initialize the network gateway.
        
        Args:
            gateway_id: Unique identifier for this gateway instance
        """
        self._lock = threading.Lock()
        self._gateway_id = gateway_id
        self._devices: Dict[str, DeviceRegistration] = {}
        self._routing_log: List[RoutingRecord] = []
        self._message_queue: Dict[str, deque] = {}  # Recipient -> queue of pending messages
        self._message_counter = 0
        
        print(f"[Gateway] {gateway_id} initialized")
    
    @property
    def gateway_id(self) -> str:
        """Gateway identifier."""
        return self._gateway_id
    
    @property
    def connected_devices(self) -> int:
        """Number of connected devices."""
        return len(self._devices)
    
    @property
    def total_messages_routed(self) -> int:
        """Total messages routed by this gateway."""
        return self._message_counter
    
    def register_device(self, device_id: str) -> bool:
        """
        Register a device with the gateway.
        
        Devices must register before they can send or receive messages.
        Registration creates a message queue for the device.
        
        Args:
            device_id: Unique device identifier
        
        Returns:
            True if newly registered, False if already registered
        """
        with self._lock:
            if device_id in self._devices:
                # Update last seen
                self._devices[device_id].last_seen = datetime.now()
                print(f"[Gateway] Device '{device_id}' reconnected")
                return False
            
            registration = DeviceRegistration(
                device_id=device_id,
                registered_at=datetime.now(),
                last_seen=datetime.now()
            )
            self._devices[device_id] = registration
            self._message_queue[device_id] = deque()
            
            print(f"[Gateway] Device '{device_id}' registered")
            return True
    
    def unregister_device(self, device_id: str) -> bool:
        """
        Unregister a device from the gateway.
        
        Args:
            device_id: Device to unregister
        
        Returns:
            True if device was found and removed
        """
        with self._lock:
            if device_id in self._devices:
                del self._devices[device_id]
                # Keep message queue in case device reconnects
                print(f"[Gateway] Device '{device_id}' unregistered")
                return True
            return False
    
    def route_message(
        self, 
        message_packet: Dict[str, Any],
        deliver_callback: Optional[callable] = None
    ) -> bool:
        """
        Route an encrypted message to its recipient.
        
        The gateway examines only the routing metadata (sender, recipient)
        and does not access the encrypted content. Messages are either
        delivered immediately via callback or queued for later retrieval.
        
        Args:
            message_packet: Encrypted message packet with routing info
            deliver_callback: Optional function to call with packet for immediate delivery
        
        Returns:
            True if message was routed successfully
        """
        with self._lock:
            sender = message_packet.get('sender', 'UNKNOWN')
            recipient = message_packet.get('recipient', 'UNKNOWN')
            
            # Validate sender is registered
            if sender not in self._devices and sender != 'UNKNOWN':
                print(f"[Gateway] ⚠️  Unregistered sender: {sender}")
            
            # Calculate message size (ciphertext only, not metadata)
            ciphertext = message_packet.get('ciphertext', '')
            size_bytes = len(ciphertext) // 2  # Hex string to bytes
            
            # Create routing record
            self._message_counter += 1
            record = RoutingRecord(
                message_id=self._message_counter,
                sender=sender,
                recipient=recipient,
                timestamp=datetime.now(),
                size_bytes=size_bytes
            )
            
            # Check if recipient is registered
            if recipient not in self._devices:
                record.status = "QUEUED"
                print(f"[Gateway] ⚡ Recipient '{recipient}' not online, message queued")
            else:
                self._devices[recipient].message_count += 1
            
            self._routing_log.append(record)
            
            # Queue message for recipient
            if recipient not in self._message_queue:
                self._message_queue[recipient] = deque()
            self._message_queue[recipient].append(message_packet)
            
            # Log routing
            print(f"[Gateway] Routed message #{self._message_counter}: {sender} → {recipient} ({size_bytes} bytes)")
            
            # Immediate delivery if callback provided
            if deliver_callback and recipient in self._devices:
                try:
                    deliver_callback(message_packet)
                except Exception as e:
                    print(f"[Gateway] Delivery callback failed: {e}")
            
            return True
    
    def get_pending_messages(self, device_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve pending messages for a device.
        
        Args:
            device_id: Device to check for messages
        
        Returns:
            List of pending message packets
        """
        with self._lock:
            if device_id not in self._message_queue:
                return []
            
            messages = list(self._message_queue[device_id])
            self._message_queue[device_id].clear()
            
            if messages:
                print(f"[Gateway] {len(messages)} message(s) delivered to '{device_id}'")
            
            return messages
    
    def get_routing_log(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent routing log entries.
        
        Args:
            limit: Maximum number of entries to return
        
        Returns:
            List of routing records as dictionaries
        """
        with self._lock:
            recent = self._routing_log[-limit:]
            return [
                {
                    'message_id': r.message_id,
                    'sender': r.sender,
                    'recipient': r.recipient,
                    'timestamp': r.timestamp.isoformat(),
                    'size_bytes': r.size_bytes,
                    'status': r.status
                }
                for r in recent
            ]
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get gateway status for monitoring.
        
        Returns:
            Dictionary with gateway statistics
        """
        with self._lock:
            return {
                'gateway_id': self._gateway_id,
                'connected_devices': len(self._devices),
                'total_messages_routed': self._message_counter,
                'device_list': list(self._devices.keys())
            }


# =============================================================================
# DEMONSTRATION
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Network Gateway - Demonstration")
    print("=" * 60)
    
    gateway = NetworkGateway("TacNet_Demo")
    
    # Register devices
    print("\n[DEMO] Device Registration")
    print("-" * 40)
    gateway.register_device("Alpha_Unit")
    gateway.register_device("Bravo_Unit")
    
    # Route a test message (simulated encrypted packet)
    print("\n[DEMO] Message Routing")
    print("-" * 40)
    test_packet = {
        'sender': 'Alpha_Unit',
        'recipient': 'Bravo_Unit',
        'nonce': 'a1b2c3d4e5f6a1b2c3d4e5f6',
        'ciphertext': 'encrypted_data_here_would_be_much_longer_in_practice',
        'timestamp': 1234567890
    }
    gateway.route_message(test_packet)
    
    # Retrieve messages
    print("\n[DEMO] Message Retrieval")
    print("-" * 40)
    pending = gateway.get_pending_messages("Bravo_Unit")
    print(f"  Retrieved {len(pending)} message(s)")
    
    # Show status
    print("\n[DEMO] Gateway Status")
    print("-" * 40)
    status = gateway.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
