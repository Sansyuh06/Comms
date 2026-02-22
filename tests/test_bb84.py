# tests/test_bb84.py
import unittest
import numpy as np
from quantum_engine.bb84_simulator import simulate_bb84

class TestBB84Simulator(unittest.TestCase):
    def test_no_eve(self):
        """Test BB84 simulation without eavesdropper."""
        key, qber, attack_detected = simulate_bb84(num_bits=512, eve_present=False)
        
        # Check key length (should be 32 bytes = 256 bits)
        self.assertEqual(len(key), 32)
        
        # Check QBER (should be low, ideally 0 in noise-free sim, but let's say < 5%)
        print(f"No Eve QBER: {qber}")
        self.assertLess(qber, 0.05)
        
        # Check attack detection
        self.assertFalse(attack_detected)

    def test_with_eve(self):
        """Test BB84 simulation with eavesdropper."""
        key, qber, attack_detected = simulate_bb84(num_bits=512, eve_present=True, eve_intercept_rate=1.0)
        
        # Check key length
        self.assertEqual(len(key), 32)
        
        # Check QBER (should be high, around 25% for BB84 with intercept-resend)
        print(f"With Eve QBER: {qber}")
        self.assertGreater(qber, 0.15) # 25% expected, so > 15% is safe check
        
        # Check attack detection
        self.assertTrue(attack_detected)

if __name__ == '__main__':
    unittest.main()
