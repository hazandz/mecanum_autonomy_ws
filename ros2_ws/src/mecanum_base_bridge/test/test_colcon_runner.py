"""Bridge pytest collection to colcon's ament_python unittest invocation."""

from pathlib import Path
import unittest

import pytest


class PhaseACodecTests(unittest.TestCase):
    def test_pytest_codec_suite(self) -> None:
        test_dir = Path(__file__).resolve().parent
        result = pytest.main([
            str(test_dir / 'test_crc16.py'),
            str(test_dir / 'test_cobs.py'),
            str(test_dir / 'test_uart_v1_valid_vectors.py'),
            str(test_dir / 'test_uart_v1_invalid_vectors.py'),
            str(test_dir / 'test_uart_rx_diagnostic.py'),
        ])
        self.assertEqual(result, 0)
