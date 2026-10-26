"""Bridge pytest collection to colcon's ament_python unittest invocation."""

from pathlib import Path
import unittest
import os

import pytest


class PhaseACodecAndTransportTests(unittest.TestCase):
    def test_pytest_codec_and_transport_suite(self) -> None:
        test_dir = Path(__file__).resolve().parent
        selected = [
            str(test_dir / 'test_crc16.py'),
            str(test_dir / 'test_cobs.py'),
            str(test_dir / 'test_uart_v1_valid_vectors.py'),
            str(test_dir / 'test_uart_v1_invalid_vectors.py'),
            str(test_dir / 'test_uart_rx_diagnostic.py'),
            str(test_dir / 'test_transport.py'),
            str(test_dir / 'test_bridge_session.py'),
            str(test_dir / 'test_hardware_config.py'),
            str(test_dir / 'test_wheel_odometry.py'),
            str(test_dir / 'test_heartbeat.py'),
            str(test_dir / 'test_uart_bridge_node.py'),
        ]
        if os.environ.get('WP07_U4_INTEROP_PEER'):
            repo_root = test_dir.parents[3]
            selected.append(str(repo_root / 'firmware_STM32/Test/test_uart_session_interop.py'))
        result = pytest.main(selected)
        self.assertEqual(result, 0)
