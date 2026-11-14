import math

import pytest

from mecanum_base_bridge.slam_manual_teleop import (
    BodyCommand, SlamManualTeleop, map_joystick,
)


@pytest.fixture
def teleop():
    # Synthetic offline fixture only: 0.2..0.6 m/s and 1.0 rad/s.
    return SlamManualTeleop((0.2, 0.4, 0.6), yaw_scale=1.0)


def joy(*pressed):
    buttons = [0] * 6
    for index in pressed:
        buttons[index] = 1
    return [0.0, 0.0], buttons


@pytest.mark.parametrize(("buttons", "expected"), [
    ((2, 3), (1, 1)),   # X+Y: forward-left
    ((1, 3), (1, -1)),  # Y+B: forward-right
    ((0, 1), (-1, -1)), # A+B: reverse-right
    ((0, 2), (-1, 1)),  # X+A: reverse-left
])
def test_diagonal_combinations_keep_both_components(teleop, buttons, expected):
    axes, keys = joy(*buttons)
    command = teleop.update(axes, keys)
    norm = math.hypot(command.vx, command.vy)
    assert math.copysign(1, command.vx) == expected[0]
    assert math.copysign(1, command.vy) == expected[1]
    assert norm == pytest.approx(0.2)


def test_stick_drives_longitudinal_and_yaw_only(teleop):
    command = teleop.update([0.0, -1.0], [0] * 6)
    assert command.vx == pytest.approx(0.2)
    assert command.vy == 0.0
    assert command.wz == 0.0


@pytest.mark.parametrize("angle_deg", (30.0, 60.0))
def test_stick_right_diagonals_translate_and_turn_toward_stick(teleop, angle_deg):
    angle = math.radians(angle_deg)
    command = teleop.update([math.sin(angle), -math.cos(angle)], [0] * 6)
    assert command.vx == pytest.approx(0.2 * math.cos(angle) ** 2)
    assert command.vy == pytest.approx(-0.2 * math.cos(angle) * math.sin(angle))
    assert command.wz == pytest.approx(-math.sin(angle))


@pytest.mark.parametrize("angle_deg", (30.0, 60.0))
def test_stick_left_diagonals_are_symmetric(teleop, angle_deg):
    angle = math.radians(angle_deg)
    command = teleop.update([-math.sin(angle), -math.cos(angle)], [0] * 6)
    assert command.vx == pytest.approx(0.2 * math.cos(angle) ** 2)
    assert command.vy == pytest.approx(0.2 * math.cos(angle) * math.sin(angle))
    assert command.wz == pytest.approx(math.sin(angle))


@pytest.mark.parametrize(("axis_x", "expected_wz"), ((1.0, -1.0), (-1.0, 1.0)))
def test_horizontal_stick_turns_in_place_without_lateral_slip(teleop, axis_x, expected_wz):
    command = teleop.update([axis_x, 0.0], [0] * 6)
    assert command.vx == 0.0
    assert command.vy == 0.0
    assert command.wz == pytest.approx(expected_wz)


@pytest.mark.parametrize(("button", "expected"), [
    (3, (1, 0)),  # Y: forward
    (0, (-1, 0)), # A: reverse
    (2, (0, 1)),  # X: strafe left
    (1, (0, -1)), # B: strafe right
])
def test_face_buttons_cardinal_directions(teleop, button, expected):
    axes, keys = joy(button)
    command = teleop.update(axes, keys)
    assert command.vx == pytest.approx(expected[0] * 0.2)
    assert command.vy == pytest.approx(expected[1] * 0.2)
    assert command.wz == 0.0


def test_pure_mapper_is_independent_of_teleop_state():
    axes, keys = joy(2, 3)
    assert map_joystick(axes, keys, 0.2, 1.0) == map_joystick(axes, keys, 0.2, 1.0)


def test_r1_keeps_existing_speed_decrease_behavior(teleop):
    axes, keys = joy(4)
    teleop.update(axes, keys)
    teleop.update(axes, [0] * 6)
    axes, keys = joy(5)
    assert teleop.update(axes, keys).vx == 0.0
    assert teleop.level == 0


def test_speed_changes_once_on_rising_edge_and_holds(teleop):
    axes, keys = joy(4)
    assert teleop.update(axes, keys).vx == 0.0
    assert teleop.level == 1
    assert teleop.update(axes, keys).vx == 0.0
    assert teleop.level == 1
    teleop.update(axes, [0] * 6)
    teleop.update(axes, keys)
    assert teleop.level == 2


@pytest.mark.parametrize("axes", ([0.0], [0.0, float("nan")], [float("inf"), 0.0], [2.0, 0.0]))
def test_invalid_or_short_joy_fails_zero(teleop, axes):
    assert teleop.update(axes, [0] * 6) == BodyCommand()


def test_missing_buttons_and_disconnect_fail_zero(teleop):
    assert teleop.update([0.0, 1.0], [0] * 5) == BodyCommand()
    assert teleop.disconnected() == BodyCommand()


def test_release_returns_command_to_zero(teleop):
    axes, keys = joy(3)
    assert teleop.update(axes, keys).vx > 0
    assert teleop.update([0.0, 0.0], [0] * 6) == BodyCommand()


def test_empty_speed_profile_is_disarmed():
    assert SlamManualTeleop().update([1.0, 1.0], [0, 0, 0, 1, 0, 0]) == BodyCommand()
    assert SlamManualTeleop(yaw_scale=1.0).update([1.0, 0.0], [0] * 6) == BodyCommand()
