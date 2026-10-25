"""Exclude preserved pre-simplification forensic suites from active pytest."""

collect_ignore = [
    "test_run_step07_nav2_baseline_run001.py",
    "test_run_step07_nav2_baseline_run002.py",
    "test_run_step07_nav2_baseline_run003.py",
    "test_step07_runtime_guard.py",
    "test_step07_run002_runtime_guard.py",
    "test_step07_run003_runtime_guard.py",
    "test_step07_gate_b_evidence_validator.py",
]
