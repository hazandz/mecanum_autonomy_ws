"""Static ownership and fail-closed checks, without ROS or Gazebo startup."""
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]


def test_backend_is_cpp17_native_and_receipt_is_the_only_actuator_carrier(
) -> None:
    """Check native C++ ownership and the receipt-only command carrier."""
    cmake = (_ROOT / 'CMakeLists.txt').read_text()
    source = (_ROOT / 'src/backend_system.cpp').read_text()
    assert 'CMAKE_CXX_STANDARD 17' in cmake
    assert 'FinalIssuedCommandReceipt' in source
    assert (
        'SetLinearVelocity' in source and 'SetAngularVelocity' in source
    )
    assert 'captured_twist_ = *msg' in source
    assert 'captured_twist_' in source and 'final_command' in source
    assert 'gate_->Invalidate("actuator_watchdog_expired")' in source
    assert 'local_zero_override_' in source
    assert 'rclcpp::init(' not in source


def test_contact_source_does_not_treat_unverified_component_as_healthy_empty(
) -> None:
    """Unverified contact components and queue overflow fail closed."""
    source = (_ROOT / 'src/backend_system.cpp').read_text()
    core = (_ROOT / 'src/contact_coverage.cpp').read_text()
    assert 'contact_capability_verified_' in source
    assert '"contact_capability_unverified"' in core
    assert 'queue_overflow' in (
        (_ROOT / 'src/receipt_gate.cpp').read_text()
    )


def test_backend_does_not_implement_b23_lifecycle_or_publish_twist() -> None:
    """Backend does not become the B2.3 lifecycle or Twist publisher."""
    source = (_ROOT / 'src/backend_system.cpp').read_text()
    assert 'create_publisher<geometry_msgs::msg::Twist>' not in source
    assert 'observation0' in source
    assert 'CreateLifecycle' not in source
    assert 'FinalTwistPublisher' not in source
