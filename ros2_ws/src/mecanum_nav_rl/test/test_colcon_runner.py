"""Bridge the emulator pytest suite into ament_python unittest discovery."""

from pathlib import Path
import unittest

import pytest


class CoreSimulationTests(unittest.TestCase):
    """Run the core-only simulation and observation suites through colcon."""

    def test_pytest_suites(self) -> None:
        """Require every registered core-only pytest suite to pass."""

        test_paths = (
            Path(__file__).with_name("test_simulated_odometry_emulator.py"),
            Path(__file__).with_name("test_observation_encoder.py"),
            Path(__file__).with_name("test_lidar_angular_binning.py"),
            Path(__file__).with_name("test_goal_features.py"),
            Path(__file__).with_name("test_measured_twist.py"),
            Path(__file__).with_name("test_previous_command.py"),
            Path(__file__).with_name("test_snapshot_synchronizer.py"),
            Path(__file__).with_name("test_observation_assembly.py"),
            Path(__file__).with_name("test_ppo_action_decoder.py"),
            Path(__file__).with_name("test_previous_action_history.py"),
            Path(__file__).with_name("test_episode_lifecycle.py"),
            Path(__file__).with_name("test_scenario_artifact.py"),
            Path(__file__).with_name("test_training_task_oracle.py"),
            Path(__file__).with_name("test_config_v3_schema.py"),
            Path(__file__).with_name("test_config_v3_compiler.py"),
            Path(__file__).with_name("test_config_v3_assets.py"),
            Path(__file__).with_name("test_v3_composition.py"),
            Path(__file__).with_name("test_v3_asset_selection.py"),
            Path(__file__).with_name("test_v3_asset_envelope.py"),
        )
        self.assertEqual(pytest.main([str(path) for path in test_paths]), 0)
