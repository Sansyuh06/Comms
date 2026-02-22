"""
QSTCS Main Entry Point
======================
Quantum-Safe Tactical Communication System

This script provides a complete demonstration of the system's capabilities,
showcasing the end-to-end secure message flow from quantum key generation
through encrypted message delivery.

DEMO SCENARIO:
--------------
1. Initialize Key Management Service
2. Deploy two field soldier devices
3. Establish quantum-safe keys via BB84
4. Send encrypted message from Alpha to Bravo
5. Demonstrate attack detection when Eve is present

Run with: python main.py

Author: QSTCS Development Team
Classification: UNCLASSIFIED
"""

import sys
import os
import time

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kms.key_management_service import KeyManagementService
from devices.client import SoldierDevice
from gateway.network_gateway import NetworkGateway


def print_banner():
    """Print system banner."""
    print()
    print("=" * 70)
    print("   QUANTUM-SAFE TACTICAL COMMUNICATION SYSTEM (QSTCS)")
    print("   Defense-Grade Prototype | Classification: UNCLASSIFIED")
    print("=" * 70)
    print()


def print_section(title: str):
    """Print section header."""
    print()
    print("-" * 70)
    print(f"  {title}")
    print("-" * 70)


def run_demo():
    """Execute the complete system demonstration."""
    
    print_banner()
    
    # =========================================================================
    # PHASE 1: System Initialization
    # =========================================================================
    print_section("PHASE 1: System Initialization")
    
    print("\n[System] Initializing Key Management Service...")
    kms = KeyManagementService()
    
    print("\n[System] Initializing Network Gateway...")
    gateway = NetworkGateway("TacNet_Primary")
    
    print("\n[System] Deploying Field Devices...")
    soldier_a = SoldierDevice("Soldier_Alpha", kms)
    soldier_b = SoldierDevice("Soldier_Bravo", kms)
    
    # Register devices with gateway
    gateway.register_device("Soldier_Alpha")
    gateway.register_device("Soldier_Bravo")
    
    print("\n[System] ✓ All components initialized successfully")
    
    # =========================================================================
    # PHASE 2: Secure Key Establishment
    # =========================================================================
    print_section("PHASE 2: Quantum Key Establishment (BB84)")
    
    print("\n[Scenario] Soldier Alpha requests secure communication channel...")
    
    if soldier_a.request_key():
        print("\n[System] ✓ Quantum-derived key established for Soldier Alpha")
    else:
        print("\n[System] ✗ Key establishment failed")
        return
    
    # Small delay for demonstration
    time.sleep(0.5)
    
    # =========================================================================
    # PHASE 3: Encrypted Message Exchange
    # =========================================================================
    print_section("PHASE 3: Encrypted Message Exchange")
    
    # Compose tactical message
    tactical_message = "FLASH: Enemy armor observed at Grid 842156. " \
                      "Estimated strength: 2x T-90 MBT. Request CAS support. " \
                      "AUTHENTICATE: BRAVO-SEVEN-NINER."
    
    print(f"\n[Soldier_Alpha] Preparing tactical message...")
    print(f"                Message: '{tactical_message[:50]}...'")
    
    # Encrypt and send
    message_packet = soldier_a.send_encrypted_message("Soldier_Bravo", tactical_message)
    
    if not message_packet:
        print("\n[System] ✗ Message encryption failed")
        return
    
    # Route through gateway
    print()
    gateway.route_message(message_packet)
    
    # Small delay for demonstration
    time.sleep(0.5)
    
    # =========================================================================
    # PHASE 4: Message Receipt and Decryption
    # =========================================================================
    print_section("PHASE 4: Message Receipt and Decryption")
    
    print("\n[Soldier_Bravo] Requesting secure channel key...")
    
    if soldier_b.request_key():
        print("\n[Soldier_Bravo] Decrypting incoming message...")
        
        # Retrieve from gateway
        pending_messages = gateway.get_pending_messages("Soldier_Bravo")
        
        if pending_messages:
            decrypted = soldier_b.receive_encrypted_message(pending_messages[0])
            
            if decrypted == tactical_message:
                print("\n[System] ✓ MESSAGE VERIFIED - Content matches original")
            else:
                print("\n[System] ⚠ Message content mismatch!")
    else:
        print("\n[System] ✗ Key establishment failed for Soldier Bravo")
        return
    
    # =========================================================================
    # PHASE 5: Attack Detection Demonstration
    # =========================================================================
    print_section("PHASE 5: Attack Detection Demonstration")
    
    print("\n[Scenario] Eve (eavesdropper) intercepts quantum channel...")
    print("[Scenario] Soldier Charlie attempts to establish secure link...\n")
    
    soldier_c = SoldierDevice("Soldier_Charlie", kms)
    kms.reset_for_demo()  # Reset for fresh attack demo
    
    try:
        # This will fail due to Eve's interception
        kms.get_fresh_key("Soldier_Charlie", force_eve_attack=True)
        print("\n[System] ⚠ Unexpected: Key was issued despite attack")
    except Exception as e:
        print(f"\n[System] ✓ ATTACK BLOCKED: {str(e)[:60]}...")
        print("[System] ✓ Quantum link flagged as COMPROMISED")
        print("[System] ✓ No key material was distributed")
    
    # =========================================================================
    # SUMMARY
    # =========================================================================
    print_section("DEMONSTRATION SUMMARY")
    
    health = kms.check_link_health()
    gateway_status = gateway.get_status()
    
    print(f"""
    System Status:
    --------------
    Link Status:        {health['status']}
    Keys Issued:        {health['total_keys_issued']}
    Attacks Detected:   {health['attacks_detected']}
    Active Sessions:    {health['active_sessions']}
    
    Gateway Status:
    ---------------
    Gateway ID:         {gateway_status['gateway_id']}
    Connected Devices:  {gateway_status['connected_devices']}
    Messages Routed:    {gateway_status['total_messages_routed']}
    
    Device Statistics:
    ------------------
    Soldier_Alpha:      Sent={soldier_a.messages_sent}, Received={soldier_a.messages_received}
    Soldier_Bravo:      Sent={soldier_b.messages_sent}, Received={soldier_b.messages_received}
    """)
    
    print_section("DEMONSTRATION COMPLETE")
    print("""
    The demonstration showcased:
    
    1. ✓ BB84 Quantum Key Distribution
       - Simulated quantum protocol for key generation
       - QBER calculation for security validation
    
    2. ✓ Secure Key Management
       - HKDF-SHA256 key derivation
       - Session tracking and link health monitoring
    
    3. ✓ Authenticated Encryption
       - AES-256-GCM for message confidentiality and integrity
       - Unique nonce per message
    
    4. ✓ Attack Detection
       - QBER threshold enforcement (11%)
       - Automatic key generation abort when compromised
    
    To launch the interactive dashboard:
        streamlit run dashboard/dashboard_ui.py
    """)


def main():
    """Main entry point."""
    try:
        run_demo()
    except KeyboardInterrupt:
        print("\n\n[System] Demo interrupted by user")
    except Exception as e:
        print(f"\n\n[System] Error: {e}")
        raise


if __name__ == "__main__":
    main()
