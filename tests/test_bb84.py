import unittest
from quantum_engine.bb84_simulator import simulate_bb84, QBER_SECURITY_THRESHOLD


class TestBB84Simulator(unittest.TestCase):
    def test_no_eve(self):
        key, qber, attack_detected = simulate_bb84(num_bits=512, eve_present=False)
        self.assertEqual(len(key), 32)
        self.assertLess(qber, 0.05)
        self.assertFalse(attack_detected)

    def test_with_eve(self):
        key, qber, attack_detected = simulate_bb84(num_bits=512, eve_present=True, eve_intercept_rate=1.0)
        self.assertEqual(len(key), 32)
        self.assertGreater(qber, 0.15)
        self.assertTrue(attack_detected)

    def test_threshold_value(self):
        self.assertEqual(QBER_SECURITY_THRESHOLD, 0.11)


if __name__ == "__main__":
    unittest.main()
