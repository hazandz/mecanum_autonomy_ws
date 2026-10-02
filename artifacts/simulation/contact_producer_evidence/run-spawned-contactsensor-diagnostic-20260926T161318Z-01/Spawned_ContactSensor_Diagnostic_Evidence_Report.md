# S3 D3 Spawned ContactSensor Diagnostic Evidence Report

Run: `run-spawned-contactsensor-diagnostic-20260926T161318Z-01`

Final classification: **DIAGNOSTIC_INCOMPLETE_SENSOR_QUERY**

## Scope evidence

- Approval ID: `S3.3.20_SPAWNED_CONTACTSENSOR_DIAGNOSTIC_RUN`.
- No separate diagnostic/raw-contact bridge, ROS collector, raw-contact collector, or analyzer was started. The existing launch-owned `ros_gz_bridge` remained observable on `/cmd_vel` in the retained read-only graph snapshot; it was neither configured nor controlled by this diagnostic.
- No `/cmd_vel` publication, teleop, Nav2, PPO, Gymnasium, SB3, pose/reset/pause/step/spawn/delete/world-control, service/action, or hardware operation was performed.
- Every query record is retained under `queries/`: 01_models.json.

## Result

```json
{
  "approval_guard_consume_reason": "ready",
  "approval_guard_consumed": true,
  "bridge_processes_started": 0,
  "collectors_started": 0,
  "collision_identity_status": "DIAGNOSTIC_INCOMPLETE_COLLISION_IDENTITY",
  "commands_published": 0,
  "control_services_called": 0,
  "hardware_operations": 0,
  "reason": "model identity query failed or did not confirm exactly one model",
  "run_id": "run-spawned-contactsensor-diagnostic-20260926T161318Z-01",
  "stage": "model_query",
  "status": "DIAGNOSTIC_INCOMPLETE_SENSOR_QUERY"
}
```

## Retained non-claims

This diagnostic does not establish a collision event, ContactLatch, collision policy/filter, raw contact payload delivery, reward, termination, Gym/training, or hardware readiness. Endpoint discovery is not a collision fact.
