import importlib.util
from pathlib import Path

import pytest

RUNNER = Path(__file__).with_name("run_step07_nav2_baseline_run001.py")
spec = importlib.util.spec_from_file_location("step07_runner_under_test", RUNNER)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_all_runtime_acceptance_and_clean_ordered_teardown_passes_only_after_teardown():
    record = {}
    runtime = {"clock": True, "tf": True, "vectors": True}
    result = runner.finalise_after_teardown(record, runtime,
        {"completed": True, "clean": True, "order_correct": True})
    assert result["terminal_outcome"].endswith("PASS_PENDING_INDEPENDENT_EVIDENCE_AUDIT")
    assert result["finalized_after_teardown"] is True
    assert all(result["acceptance"].values())
    assert result["failure_reason_literals"] == []


def test_teardown_failure_has_distinct_literal_after_runtime_pass():
    result = runner.finalise_after_teardown({}, {"clock": True, "tf": True},
        {"completed": True, "clean": False, "order_correct": True})
    assert result["terminal_outcome"].endswith("FAIL_NO_RETRY_GUARD_CONSUMED")
    assert "PROCESS_GROUP_TEARDOWN_FAILED" in result["failure_reason_literals"]
    assert result["acceptance"]["process_group_teardown_clean"] is False


def test_runtime_failure_has_runtime_literal_and_still_records_teardown():
    result = runner.finalise_after_teardown({}, {"clock": False, "tf": True},
        {"completed": True, "clean": True, "order_correct": True})
    assert result["terminal_outcome"].endswith("FAIL_NO_RETRY_GUARD_CONSUMED")
    assert "RUNTIME_ACCEPTANCE_FAILED:clock" in result["failure_reason_literals"]
    assert result["acceptance"]["process_group_teardown_clean"] is True


def test_no_all_true_acceptance_can_have_fail_terminal():
    result = runner.finalise_after_teardown({}, {"clock": True, "tf": True},
        {"completed": True, "clean": True, "order_correct": True})
    assert all(result["acceptance"].values())
    assert result["terminal_outcome"].endswith("PASS_PENDING_INDEPENDENT_EVIDENCE_AUDIT")


def test_runner_requires_all_five_owner_authorization_arguments():
    source = RUNNER.read_text(encoding="utf-8")
    for name in ("owner-authorization", "owner-authorization-scope", "owner-authorization-run-id",
                 "owner-authorization-review-commit", "owner-authorization-integration-base"):
        assert f'"--{name}"' in source
    main_start = source.index("def main():")
    assert source.index("acquire_guard(", main_start) < source.index("bootstrap_command, composite_command", main_start)


def test_cpp_observer_must_exit_and_write_output_before_json_is_validated():
    source = RUNNER.read_text(encoding="utf-8")
    assert source.index("cpp.wait(timeout=1850)") < source.index("load_json(observer_path)")
    assert 'raise RuntimeError(f"CPP_OBSERVER_FAILED:{cpp.returncode}")' in source


def test_bootstrap_and_composite_commands_are_one_shot_and_separate():
    source = RUNNER.read_text(encoding="utf-8")
    assert source.count('name="bootstrap"') == 1
    assert source.count('name="composite"') == 1
    assert source.count("bootstrap_calls = 1") == 1
    assert source.count("composite_calls = 1") == 1
    assert source.index('name="bootstrap"') < source.index('name="composite"')
    assert source.index("bootstrap_member[\"readiness\"] = _wait_bootstrap_ready") < source.index('name="composite"')
    assert source.index("composite_member[\"readiness\"] = _wait_ready") > source.index('name="composite"')
    assert source.count("validate_started_process_group(bootstrap_proc, bootstrap_member)") == 3
    assert '"bootstrap_composite_process_groups_distinct": False' in source
    assert 'runtime_acceptance["bootstrap_composite_process_groups_distinct"] = True' in source
    assert 'runtime_acceptance["bootstrap_readiness"] = True' in source
    assert 'runtime_acceptance["composite_readiness"] = True' in source
    with pytest.raises(RuntimeError, match="PROCESS_GROUP_MISSING"):
        runner.validate_distinct_process_groups(None, {"pid": 22, "pgid": 22, "initial_snapshot": {"live_member_pids": [22]}})
    bootstrap = {"pid": 22, "pgid": 22, "initial_snapshot": {"live_member_pids": [22]}}
    composite = {"pid": 22, "pgid": 22, "initial_snapshot": {"live_member_pids": [22]}}
    with pytest.raises(RuntimeError, match="NOT_DISTINCT"):
        runner.validate_distinct_process_groups(bootstrap, composite)
    stale = {"pid": 24, "pgid": 24, "initial_snapshot": {"live_member_pids": []}}
    with pytest.raises(RuntimeError, match="STALE_OR_INVALID"):
        runner.validate_distinct_process_groups(stale, {"pid": 25, "pgid": 25, "initial_snapshot": {"live_member_pids": [25]}})


def test_launch_commands_start_bootstrap_separately_then_disable_composite_bootstrap(tmp_path):
    fuel = tmp_path / "fuel"
    fuel.mkdir()
    bootstrap, composite = runner.campaign_launch_commands(
        {"canonical_map_yaml": "/repo/artifacts/maps/warehouse_map2/map.yaml"},
        partition="mecanum_step7_nav2_run001_f7f98c6", fuel_root=fuel,
        repository_root=tmp_path,
    )
    assert bootstrap[:4] == ["ros2", "launch", "ROBOT_URDF_final_description", "sim_eval_nav2_baseline_bootstrap.launch.py"]
    assert composite[:4] == ["ros2", "launch", "mecanum_nav_bringup", "sim_eval_nav2_baseline_system.launch.py"]
    assert "start_bootstrap:=false" in composite
    assert sum(item.startswith("gz_partition:=") for item in bootstrap) == 1
    assert sum(item.startswith("gz_partition:=") for item in composite) == 1
    assert "initial_pose_map_x:=0.0" in bootstrap and "initial_pose_map_x:=0.0" in composite
    assert "sim_estop_release_authorized:=true" in composite


def test_teardown_stops_composite_before_bootstrap_and_checks_both_groups():
    source = RUNNER.read_text(encoding="utf-8")
    main_start = source.index("def main():")
    teardown_start = source.index("finally:", main_start)
    assert source.index("composite_teardown = _stop_owned_process", teardown_start) < source.index(
        "bootstrap_teardown = _stop_owned_process", teardown_start)
    assert 'teardown["order"] = ["composite", "bootstrap"]' in source
    assert '"live_member_pids"' in source and '"zombie_member_pids"' in source
    assert "bootstrap_calls == 1" in source and "composite_calls == 1" in source
