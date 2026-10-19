"""Static ROSIDL contract for the lifecycle/action-reset barrier."""
from mecanum_nav_rl_interfaces.msg import SafetyLifecycleState


def test_primary_and_barrier_states_are_explicit() -> None:
    assert SafetyLifecycleState.PRIMARY_UNCONFIGURED == 0
    assert SafetyLifecycleState.PRIMARY_INACTIVE == 1
    assert SafetyLifecycleState.PRIMARY_ACTIVE == 2
    assert SafetyLifecycleState.BARRIER_INIT == 0
    assert SafetyLifecycleState.BARRIER_READY == 1
    assert SafetyLifecycleState.BARRIER_NON_READY == 2
    assert SafetyLifecycleState.BARRIER_FAULT == 3


def test_lifecycle_identity_and_barrier_fields_are_exact() -> None:
    assert list(SafetyLifecycleState.get_fields_and_field_types().items()) == [
        ("header", "std_msgs/Header"),
        ("episode_generation", "uint64"),
        ("reset_epoch", "uint32"),
        ("runtime_generation", "uint32"),
        ("sequence", "uint64"),
        ("primary_state", "uint8"),
        ("barrier_state", "uint8"),
        ("barrier_stamp", "builtin_interfaces/Time"),
        ("motion_permitted", "boolean"),
        ("reason", "string"),
    ]
