#!/usr/bin/env python3
import unittest
from TestComparison import Comparison as p


class ProtocolTests(unittest.TestCase):
    def test_stable_series(self):
        self.assertTrue(p.summarize([90, 90.1, 89.9] * 4)['stationary'])

    def test_warming_inside_retained_window_is_rejected(self):
        self.assertFalse(p.summarize([60, 70, 80] + [90] * 9)['stationary'])
    def test_drift(self):
        result = p.summarize([90 - 0.25 * i for i in range(12)])
        self.assertFalse(result['stationary'])
        self.assertTrue(any('drift' in message for message in result['failures']))
    def test_outlier_is_not_trimmed(self):
        result = p.summarize([90] * 11 + [120])
        self.assertFalse(result['stationary'])
        self.assertEqual(result['maximum'], 120)
    def test_invalid_numbers(self):
        for value in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                p.summarize([90] * 11 + [value])


if __name__ == '__main__':
    unittest.main()
