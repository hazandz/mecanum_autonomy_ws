#ifndef MECANUM_CONTROL_SAFETY_RUNTIME_H
#define MECANUM_CONTROL_SAFETY_RUNTIME_H

#include "control_safety_session.h"

#include <stdbool.h>
#include <stdint.h>

#define CONTROL_SAFETY_RUNTIME_TASK_PRIORITY 40U
#define CONTROL_SAFETY_RUNTIME_TASK_STACK_WORDS 512U
#define CONTROL_SAFETY_RUNTIME_PERIOD_MS 5U
#define CONTROL_SAFETY_RUNTIME_CANDIDATE_BUDGET 8U
#define CONTROL_SAFETY_RUNTIME_WATCHDOG_MS 200U

#define MECANUM_FAULT_TRANSPORT UINT32_C(1)
#define MECANUM_FAULT_MCU_COMMAND_TIMEOUT UINT32_C(256)
#define MECANUM_FAULT_MCU_COMMAND_INVALID UINT32_C(512)

typedef struct {
    control_safety_session_state_t state;
    bool configured;
    bool telemetry_allowed;
    bool motor_enabled;
    uint64_t mcu_boot_id;
    uint32_t reset_epoch;
    uint32_t last_accepted_command_sequence;
    uint32_t mcu_fault_bits;
} control_safety_snapshot_t;

bool control_safety_runtime_start(const uint8_t local_hash[32], bool communication_config_valid,
                                  uint64_t boot_id);
void control_safety_runtime_service_once(void);
bool control_safety_runtime_copy_snapshot(control_safety_snapshot_t *snapshot);

#endif
