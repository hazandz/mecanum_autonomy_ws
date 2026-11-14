import math
from dataclasses import replace

import pytest

from mecanum_base_bridge.slam_manual_teleop import (
    SPEED_LEVELS,
    BodyCommand,
    SlamBenchMotionProfile,
    SlamManualTeleop,
    limit_command_to_wheel_cps,
    wheel_target_cps,
)


@pytest.fixture
def profile():
    # Synthetic direct-drive ratio=1 and a high cap isolate mapping math offline.
    return SlamBenchMotionProfile(
        wheel_diameter_m=0.097,
        wheelbase_m=0.216,
        track_m=0.190,
        ticks_per_wheel_revolution=937.2,
        motor_output_rpm=172.0,
        wheel_rpm_per_output_rpm=1.0,
        max_wheel_cps=100_000.0,
    )


@pytest.fixture
def teleop(profile):
    return SlamManualTeleop(profile, motion_enabled=True)


def joy(*pressed):
    buttons = [0] * 6
    for index in pressed:
        buttons[index] = 1
    return [0.0, 0.0], buttons


def expected_level_speed(profile, level):
    return profile.max_translation_mps * SPEED_LEVELS[level]


def test_five_fixed_tiers_start_at_twenty_percent_and_buttons_step_once(teleop):
    assert SPEED_LEVELS == (0.2, 0.4, 0.6, 0.8, 1.0)
    assert teleop.level == 0 and teleop.level_percent == 20
    axes, l1 = joy(4)
    for expected in (40, 60, 80, 100):
        teleop.update(axes, l1)
        assert teleop.level_percent == expected
        teleop.update(axes, l1)
        assert teleop.level_percent == expected
        teleop.update(axes, [0] * 6)
    teleop.update(axes, l1)
    assert teleop.level_percent == 100  # upper boundary does not wrap


def test_r1_decreases_one_level_on_rising_edge_and_stops_at_twenty_percent(teleop):
    axes, l1 = joy(4)
    for _ in range(4):
        teleop.update(axes, l1)
        teleop.update(axes, [0] * 6)
    axes, r1 = joy(5)
    for expected in (80, 60, 40, 20, 20):
        teleop.update(axes, r1)
        assert teleop.level_percent == expected
        teleop.update(axes, [0] * 6)


def test_l1_r1_never_move_by_themselves_and_simultaneous_press_cancels(teleop):
    axes, l1 = joy(4)
    assert teleop.update(axes, l1) == BodyCommand()
    teleop.update(axes, [0] * 6)
    axes, both = joy(4, 5)
    old_level = teleop.level
    assert teleop.update(axes, both) == BodyCommand()
    assert teleop.level == old_level


def test_analog_twelve_hour_is_full_forward_and_fixed_above_deadzone(teleop, profile):
    shallow = teleop.update([0.0, -0.3], [0] * 6)
    deep = teleop.update([0.0, -1.0], [0] * 6)
    expected = expected_level_speed(profile, 0)
    assert shallow == pytest.approx(BodyCommand(expected, 0.0, 0.0))
    assert deep == pytest.approx(shallow)


@pytest.mark.parametrize("angle_deg", (30.0, 60.0))
def test_analog_right_diagonals_translate_in_direction_and_turn_right(
    teleop, profile, angle_deg,
):
    theta = math.radians(angle_deg)
    command = teleop.update([math.sin(theta), -math.cos(theta)], [0] * 6)
    speed = expected_level_speed(profile, 0)
    expected = BodyCommand(speed * math.cos(theta),
                           -speed * math.sin(theta),
                           -speed / profile.rotation_radius_m * math.sin(theta))
    assert command == pytest.approx(expected)


@pytest.mark.parametrize("angle_deg", (30.0, 60.0))
def test_analog_left_diagonals_are_symmetric(teleop, profile, angle_deg):
    theta = math.radians(angle_deg)
    command = teleop.update([-math.sin(theta), -math.cos(theta)], [0] * 6)
    speed = expected_level_speed(profile, 0)
    expected = BodyCommand(speed * math.cos(theta),
                           speed * math.sin(theta),
                           speed / profile.rotation_radius_m * math.sin(theta))
    assert command == pytest.approx(expected)


@pytest.mark.parametrize(("axis_x", "turn_sign"), ((1.0, -1.0), (-1.0, 1.0)))
def test_analog_three_and_nine_hour_turn_in_place(teleop, profile, axis_x, turn_sign):
    command = teleop.update([axis_x, 0.0], [0] * 6)
    expected_wz = turn_sign * expected_level_speed(profile, 0) / profile.rotation_radius_m
    assert command.vx == 0.0
    assert command.vy == 0.0
    assert command.wz == pytest.approx(expected_wz)


def test_deadzone_and_short_smooth_activation_ramp(teleop, profile):
    assert teleop.update([0.0, -profile.deadzone_radius], [0] * 6) == BodyCommand()
    half_radius = (profile.deadzone_radius + profile.full_command_radius) / 2.0
    command = teleop.update([0.0, -half_radius], [0] * 6)
    assert command.vx == pytest.approx(expected_level_speed(profile, 0) * 0.5)
    full = teleop.update([0.0, -profile.full_command_radius], [0] * 6)
    assert full.vx == pytest.approx(expected_level_speed(profile, 0))


def test_sideways_transition_is_continuous_and_fades_translation_to_zero(teleop, profile):
    speed = expected_level_speed(profile, 0)
    fade_start = math.radians(profile.sideways_fade_start_deg)
    near_start = teleop.update([math.sin(fade_start + 1e-5),
                                -math.cos(fade_start + 1e-5)], [0] * 6)
    assert math.hypot(near_start.vx, near_start.vy) == pytest.approx(speed, rel=1e-8)

    half_fade_angle = math.radians((profile.sideways_fade_start_deg + 90.0) / 2.0)
    half_fade = teleop.update([math.sin(half_fade_angle), -math.cos(half_fade_angle)], [0] * 6)
    assert math.hypot(half_fade.vx, half_fade.vy) == pytest.approx(speed * 0.5)

    horizontal = teleop.update([1.0, 0.0], [0] * 6)
    assert horizontal.vx == 0.0 and horizontal.vy == 0.0
    assert horizontal.wz == pytest.approx(-speed / profile.rotation_radius_m)


@pytest.mark.parametrize(("button", "expected"), [
    (3, (1, 0)),   # Y: tiến
    (0, (-1, 0)),  # A: lùi
    (2, (0, 1)),   # X: trái
    (1, (0, -1)),  # B: phải
])
def test_face_button_cardinal_directions_ignore_analog(teleop, profile, button, expected):
    command = teleop.update([1.0, -1.0], joy(button)[1])
    speed = expected_level_speed(profile, 0)
    assert command.vx == pytest.approx(expected[0] * speed)
    assert command.vy == pytest.approx(expected[1] * speed)
    assert command.wz == 0.0


@pytest.mark.parametrize(("pressed", "expected"), [
    ((2, 3), (1, 1)),   # XY: tiến-trái
    ((1, 3), (1, -1)),  # YB: tiến-phải
    ((0, 1), (-1, -1)), # AB: lùi-phải
    ((0, 2), (-1, 1)),  # XA: lùi-trái
])
def test_face_button_diagonals_keep_tier_magnitude(teleop, profile, pressed, expected):
    command = teleop.update([0.0, 0.0], joy(*pressed)[1])
    speed = expected_level_speed(profile, 0)
    assert math.hypot(command.vx, command.vy) == pytest.approx(speed)
    assert math.copysign(1.0, command.vx) == expected[0]
    assert math.copysign(1.0, command.vy) == expected[1]
    assert command.wz == 0.0


def test_opposing_face_buttons_suppress_analog_after_cancellation(teleop, profile):
    axes = [0.0, -1.0]
    both_longitudinal = joy(0, 3)[1]
    assert teleop.update(axes, both_longitudinal) == BodyCommand()

    both_longitudinal_and_x = joy(0, 2, 3)[1]
    command = teleop.update(axes, both_longitudinal_and_x)
    assert command.vx == 0.0
    assert command.vy == pytest.approx(expected_level_speed(profile, 0))
    assert command.wz == 0.0


def test_face_button_with_l1_uses_new_tier_and_suppresses_stick(teleop, profile):
    buttons = joy(3, 4)[1]
    command = teleop.update([1.0, 0.0], buttons)
    assert teleop.level_percent == 40
    assert command.vx == pytest.approx(expected_level_speed(profile, 1))
    assert command.vy == 0.0 and command.wz == 0.0


def test_wheel_target_limit_scales_all_axes_together(profile):
    capped = replace(profile, max_wheel_cps=1400.0)
    request = BodyCommand(vx=0.8, vy=0.35, wz=1.4)
    raw_targets = wheel_target_cps(request, capped)
    limited = limit_command_to_wheel_cps(request, capped)
    final_targets = wheel_target_cps(limited, capped)
    assert max(abs(value) for value in raw_targets) > 1400.0
    assert max(abs(value) for value in final_targets) == pytest.approx(1400.0)
    ratios = (limited.vx / request.vx, limited.vy / request.vy, limited.wz / request.wz)
    assert ratios[0] == pytest.approx(ratios[1]) == pytest.approx(ratios[2])


def test_all_five_tiers_obey_wheel_target_cap_even_with_turn(profile):
    capped = replace(profile, max_wheel_cps=1400.0)
    teleop = SlamManualTeleop(capped, motion_enabled=True)
    axes = [math.sin(math.radians(60)), -math.cos(math.radians(60))]
    buttons = [0] * 6
    for expected_level in range(5):
        command = teleop.update(axes, buttons)
        assert max(abs(value) for value in wheel_target_cps(command, capped)) <= 1400.0 + 1e-9
        if expected_level < 4:
            teleop.update([0.0, 0.0], joy(4)[1])
            teleop.update([0.0, 0.0], [0] * 6)


def test_172_rpm_nominal_exceeds_experimental_pid_target_ceiling(profile):
    assert profile.max_translation_mps == pytest.approx(0.8735721972)
    nominal_cps = profile.motor_output_rpm * profile.ticks_per_wheel_revolution / 60.0
    assert nominal_cps == pytest.approx(2686.64)
    capped = replace(profile, max_wheel_cps=1400.0)
    command = SlamManualTeleop(capped, motion_enabled=True).update([0.0, -1.0], [0] * 6)
    assert max(abs(value) for value in wheel_target_cps(command, capped)) <= 1400.0 + 1e-9


def test_bad_axes_and_button_values_fail_zero(teleop):
    for invalid in ([0.0], [0.0, float("nan")], [float("inf"), 0.0],
                    [2.0, 0.0], None):
        assert teleop.update(invalid, [0] * 6) == BodyCommand()
    assert teleop.update([0.0, -1.0], [0, 0, 0, 0, "bad", 0]) == BodyCommand()


def test_missing_buttons_disconnect_and_invalid_configuration_fail_zero(profile):
    teleop = SlamManualTeleop(profile, motion_enabled=True)
    assert teleop.update([0.0, -1.0], [0] * 5) == BodyCommand()
    assert teleop.disconnected() == BodyCommand()
    assert SlamManualTeleop(profile).update([0.0, -1.0], [0] * 6) == BodyCommand()
    assert SlamManualTeleop(None, motion_enabled=True).update(
        [0.0, -1.0], [0] * 6) == BodyCommand()

    missing_ratio = replace(profile, wheel_rpm_per_output_rpm=0.0)
    assert not missing_ratio.valid
    assert SlamManualTeleop(missing_ratio, motion_enabled=True).update(
        [0.0, -1.0], [0] * 6) == BodyCommand()
    bad_geometry = replace(profile, wheel_diameter_m=float("nan"))
    assert SlamManualTeleop(bad_geometry, motion_enabled=True).update(
        [0.0, -1.0], [0] * 6) == BodyCommand()
