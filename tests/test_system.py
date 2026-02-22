"""
QSTCS Test Suite
================
Automated verification tests for Quantum-Safe Tactical Communication System.

This module provides comprehensive tests for:
1. BB84 quantum key distribution simulator
2. Key Management Service
3. Soldier device encryption/decryption
4. End-to-end message flow

Run with: python -m pytest tests/ -v
Or:       python tests/test_system.py

Author: QSTCS Development Team
"""

import unittest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantum_engine.bb84_simulator import simulate_bb84, QBER_SECURITY_THRESHOLD
from kms.key_management_service import KeyManagementService
from devices.client import SoldierDevice


class TestBB84Simulator(unittest.TestCase):
    """Tests for the BB84 quantum key distribution simulator."""
    
    def test_normal_key_generation(self):
        """Test key generation without eavesdropper produces low QBER."""
        key, qber, attack_detected = simulate_bb84(
            num_bits=512,
            eve_present=False
        )
        
        # Key should be 32 bytes (256 bits)
        self.assertEqual(len(key), 32)
        
        # QBER should be very low (near 0) without Eve
        self.assertLess(qber, 0.05)
        
        # No attack should be detected
        self.assertFalse(attack_detected)
    
    def test_eve_attack_detection(self):
        """Test that eavesdropper is detected via high QBER."""
        key, qber, attack_detected = simulate_bb84(
            num_bits=512,
            eve_present=True,
            eve_intercept_rate=1.0
        )
        
        # Key should still be 32 bytes
        self.assertEqual(len(key), 32)
        
        # QBER should be approximately 25% with full interception
        self.assertGreater(qber, 0.15)
        self.assertLess(qber, 0.35)
        
        # Attack should be detected
        self.assertTrue(attack_detected)
    
    def test_partial_interception(self):
        """Test partial eavesdropping produces intermediate QBER."""
        key, qber, attack_detected = simulate_bb84(
            num_bits=1024,
            eve_present=True,
            eve_intercept_rate=0.5
        )
        
        # QBER should be approximately half of full interception
        # Expected: ~12.5% (half of 25%)
        self.assertGreater(qber, 0.05)
        self.assertLess(qber, 0.20)
    
    def test_security_threshold_value(self):
        """Verify security threshold is set correctly."""
        self.assertEqual(QBER_SECURITY_THRESHOLD, 0.11)
    
    def test_consistent_key_length(self):
        """Test that key length is consistent across runs."""
        for _ in range(10):
            key, _, _ = simulate_bb84(num_bits=256)
            self.assertEqual(len(key), 32)


class TestKeyManagementService(unittest.TestCase):
    """Tests for the Key Management Service."""
    
    def setUp(self):
        """Create fresh KMS for each test."""
        self.kms = KeyManagementService()
    
    def test_key_issuance(self):
        """Test that KMS issues valid keys."""
        key = self.kms.get_fresh_key("TestDevice")
        
        # Key should be 32 bytes
        self.assertEqual(len(key), 32)
        
        # Key should be bytes type
        self.assertIsInstance(key, bytes)
    
    def test_attack_blocks_key(self):
        """Test that detected attack blocks key issuance."""
        with self.assertRaises(Exception) as context:
            self.kms.get_fresh_key("TestDevice", force_eve_attack=True)
        
        self.assertIn("compromised", str(context.exception).lower())
    
    def test_metrics_tracking(self):
        """Test that KMS tracks metrics correctly."""
        # Initial state
        health = self.kms.check_link_health()
        self.assertEqual(health['total_keys_issued'], 0)
        self.assertEqual(health['attacks_detected'], 0)
        
        # Issue a key
        self.kms.get_fresh_key("Device1")
        health = self.kms.check_link_health()
        self.assertEqual(health['total_keys_issued'], 1)
        
        # Trigger attack
        try:
            self.kms.get_fresh_key("Device2", force_eve_attack=True)
        except:
            pass
        
        health = self.kms.check_link_health()
        self.assertEqual(health['attacks_detected'], 1)
    
    def test_key_sharing_demo_mode(self):
        """Test that second device gets same key for demo."""
        key1 = self.kms.get_fresh_key("DeviceA")
        key2 = self.kms.get_fresh_key("DeviceB")
        
        # Keys should match for demo mode
        self.assertEqual(key1, key2)
    
    def test_reset_functionality(self):
        """Test that reset clears all state."""
        self.kms.get_fresh_key("Device1")
        self.kms.reset_for_demo()
        
        health = self.kms.check_link_health()
        self.assertEqual(health['total_keys_issued'], 0)
        self.assertEqual(health['attacks_detected'], 0)


class TestSoldierDevice(unittest.TestCase):
    """Tests for the Soldier Device client."""
    
    def setUp(self):
        """Create fresh KMS and device for each test."""
        self.kms = KeyManagementService()
        self.device = SoldierDevice("TestSoldier", self.kms)
    
    def test_key_request(self):
        """Test device can request key from KMS."""
        result = self.device.request_key()
        
        self.assertTrue(result)
        self.assertTrue(self.device.has_key)
        self.assertEqual(len(self.device.current_key), 32)
    
    def test_encryption_without_key(self):
        """Test that encryption fails without key."""
        result = self.device.send_encrypted_message("Recipient", "Test message")
        
        self.assertIsNone(result)
    
    def test_encryption_with_key(self):
        """Test message encryption with valid key."""
        self.device.request_key()
        packet = self.device.send_encrypted_message("Recipient", "Test message")
        
        self.assertIsNotNone(packet)
        self.assertIn('sender', packet)
        self.assertIn('recipient', packet)
        self.assertIn('nonce', packet)
        self.assertIn('ciphertext', packet)
        self.assertIn('timestamp', packet)
        
        # Verify ciphertext is different from plaintext
        self.assertNotEqual(packet['ciphertext'], "Test message")


class TestEndToEndFlow(unittest.TestCase):
    """End-to-end integration tests."""
    
    def test_full_message_exchange(self):
        """Test complete message exchange between two devices."""
        kms = KeyManagementService()
        
        sender = SoldierDevice("Sender", kms)
        receiver = SoldierDevice("Receiver", kms)
        
        # Both devices get keys
        self.assertTrue(sender.request_key())
        self.assertTrue(receiver.request_key())
        
        # Sender encrypts message
        original_message = "This is a secret tactical message."
        packet = sender.send_encrypted_message("Receiver", original_message)
        
        self.assertIsNotNone(packet)
        
        # Receiver decrypts message
        decrypted = receiver.receive_encrypted_message(packet)
        
        self.assertEqual(decrypted, original_message)
    
    def test_attack_prevents_communication(self):
        """Test that attack detection prevents message exchange."""
        kms = KeyManagementService()
        device = SoldierDevice("Device", kms)
        
        # Attempt key request during attack
        result = device.request_key(force_attack=True)
        
        self.assertFalse(result)
        self.assertFalse(device.has_key)
    
    def test_multiple_messages(self):
        """Test sending multiple messages with same key."""
        kms = KeyManagementService()
        
        sender = SoldierDevice("Sender", kms)
        receiver = SoldierDevice("Receiver", kms)
        
        sender.request_key()
        receiver.request_key()
        
        messages = [
            "First message",
            "Second message with more content",
            "Third message"
        ]
        
        for original in messages:
            packet = sender.send_encrypted_message("Receiver", original)
            decrypted = receiver.receive_encrypted_message(packet)
            self.assertEqual(decrypted, original)
        
        # Verify message counts
        self.assertEqual(sender.messages_sent, 3)
        self.assertEqual(receiver.messages_received, 3)


def run_tests():
    """Run all tests with verbose output."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestBB84Simulator))
    suite.addTests(loader.loadTestsFromTestCase(TestKeyManagementService))
    suite.addTests(loader.loadTestsFromTestCase(TestSoldierDevice))
    suite.addTests(loader.loadTestsFromTestCase(TestEndToEndFlow))
    
    # Run with verbosity
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
