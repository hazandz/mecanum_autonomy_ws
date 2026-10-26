#include "control_safety_runtime.h"

#include "command_watchdog.h"
#include "communication_runtime.h"
#include "FreeRTOS.h"
#include "queue.h"
#include "task.h"

#include <string.h>

static control_safety_session_t session;
static command_watchdog_t watchdog;
static StaticTask_t task_control;
static StackType_t task_stack[CONTROL_SAFETY_RUNTIME_TASK_STACK_WORDS];
static TaskHandle_t owner_task;
static bool started;
static bool telemetry_allowed;
static uint32_t mcu_fault_bits;
static uint32_t snapshot_revision;

static void control_safety_task(void *argument)
{
    TickType_t last_wake = xTaskGetTickCount();
    (void)argument;
    for (;;) {
        control_safety_runtime_service_once();
        vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(CONTROL_SAFETY_RUNTIME_PERIOD_MS));
    }
}

bool control_safety_runtime_start(const uint8_t local_hash[32], bool config_valid,
                                  uint64_t boot_id)
{
    if ((__get_IPSR() != 0U) || started || (local_hash == NULL) || (boot_id == 0U)) return false;
    if (!control_safety_session_init(&session, local_hash, config_valid, boot_id)) return false;
    command_watchdog_init(&watchdog, CONTROL_SAFETY_RUNTIME_WATCHDOG_MS);
    telemetry_allowed = false;
    mcu_fault_bits = 0U;
    snapshot_revision = 0U;
    owner_task = xTaskCreateStatic(control_safety_task, "CtrlSafe",
        CONTROL_SAFETY_RUNTIME_TASK_STACK_WORDS, NULL,
        CONTROL_SAFETY_RUNTIME_TASK_PRIORITY, task_stack, &task_control);
    if (owner_task == NULL) return false;
    started = true;
    return true;
}

static void watchdog_expiry_check(uint32_t now)
{
    control_safety_session_decision_t decision;
    if ((session.state != CONTROL_SAFETY_SESSION_SAFE_STOP)
        && command_watchdog_expired(&watchdog, now)) {
        (void)control_safety_session_handle_watchdog_expired(&session, &decision);
        mcu_fault_bits |= MECANUM_FAULT_MCU_COMMAND_TIMEOUT;
    }
}

static void transport_failure(void)
{
    if ((mcu_fault_bits & MECANUM_FAULT_TRANSPORT) == 0U) {
        control_safety_session_decision_t decision;
        if (session.state != CONTROL_SAFETY_SESSION_SAFE_STOP) {
            (void)control_safety_session_handle_watchdog_expired(&session, &decision);
        }
        control_safety_session_invalidate_transport(&session);
        telemetry_allowed = false;
        command_watchdog_disarm(&watchdog);
        mcu_fault_bits |= MECANUM_FAULT_TRANSPORT;
    }
    (void)communication_runtime_request_recovery();
}

static void process_config(const communication_candidate_t *candidate)
{
    control_safety_session_decision_t decision;
    bool accepted;
    accepted = control_safety_session_handle_config(&session,
        &candidate->value.config_request, &decision);
    if (!accepted || !decision.config_status_available) return;
    if (decision.config_status.config_status == MECANUM_UART_V1_CONFIG_ACCEPTED) {
        command_watchdog_disarm(&watchdog);
        telemetry_allowed = false;
    }
    if (!communication_runtime_enqueue_config_status(&decision.config_status)) {
        transport_failure();
        return;
    }
    if (decision.config_status.config_status == MECANUM_UART_V1_CONFIG_ACCEPTED) {
        mcu_fault_bits = 0U;
        telemetry_allowed = true;
    }
}

static void process_command(const communication_candidate_t *candidate, uint32_t now)
{
    control_safety_session_decision_t decision;
    uint32_t age = (uint32_t)(now - candidate->rx_tick);
    if (age >= CONTROL_SAFETY_RUNTIME_WATCHDOG_MS) {
        mcu_fault_bits |= MECANUM_FAULT_MCU_COMMAND_INVALID;
        return;
    }
    if (!control_safety_session_handle_command(&session, &candidate->value.command, &decision)) return;
    if (decision.command_accepted) {
        if (!command_watchdog_accept(&watchdog, candidate->rx_tick, now)) return;
        mcu_fault_bits &= ~MECANUM_FAULT_MCU_COMMAND_INVALID;
    } else if (decision.internal_reject_reason != CONTROL_SAFETY_SESSION_REJECT_SAFE_STOP
               && decision.internal_reject_reason != CONTROL_SAFETY_SESSION_REJECT_NO_CONFIGURED_SESSION) {
        mcu_fault_bits |= MECANUM_FAULT_MCU_COMMAND_INVALID;
    }
}

void control_safety_runtime_service_once(void)
{
    uint8_t budget = CONTROL_SAFETY_RUNTIME_CANDIDATE_BUDGET;
    communication_candidate_t candidate;
    if ((__get_IPSR() != 0U) || !started
        || (xTaskGetCurrentTaskHandle() != owner_task)) return;
    taskENTER_CRITICAL();
    ++snapshot_revision;
    taskEXIT_CRITICAL();
    if (!communication_runtime_is_started()) return;
    if (communication_runtime_is_faulted()) {
        transport_failure();
        return;
    }
    if (!communication_runtime_is_usable()) return; /* Startup prepare precedes RX arm. */
    watchdog_expiry_check(HAL_GetTick());
    while ((budget-- > 0U) && communication_runtime_take_candidate(&candidate)) {
        uint32_t now = HAL_GetTick();
        watchdog_expiry_check(now); /* Expiry is checked before every queued candidate. */
        if (candidate.type == COMMUNICATION_CANDIDATE_CONFIG_REQUEST) {
            process_config(&candidate);
        } else if (candidate.type == COMMUNICATION_CANDIDATE_COMMAND) {
            process_command(&candidate, now);
        }
        if (communication_runtime_is_faulted()) {
            transport_failure();
            return;
        }
    }
}

bool control_safety_runtime_copy_snapshot(control_safety_snapshot_t *out)
{
    if ((__get_IPSR() != 0U) || !started || (out == NULL)) return false;
    taskENTER_CRITICAL();
    out->state = session.state;
    out->configured = session.configured;
    out->telemetry_allowed = telemetry_allowed;
    out->motor_enabled = false;
    out->mcu_boot_id = session.mcu_boot_id;
    out->reset_epoch = session.configured_reset_epoch;
    out->last_accepted_command_sequence = session.last_accepted_command_sequence;
    out->mcu_fault_bits = mcu_fault_bits;
    out->snapshot_revision = snapshot_revision;
    taskEXIT_CRITICAL();
    return true;
}

bool control_safety_runtime_enqueue_telemetry_if_current(
    const control_safety_snapshot_t *expected,
    const mecanum_uart_v1_telemetry_t *telemetry)
{
    bool queued = false;
    if ((__get_IPSR() != 0U) || expected == NULL || telemetry == NULL || !started) return false;
    /* Giao dịch queue-copy ngắn; không serialize hoặc truyền trong critical section. */
    taskENTER_CRITICAL();
    if (snapshot_revision == expected->snapshot_revision
        && session.configured && telemetry_allowed
        && session.configured_reset_epoch == expected->reset_epoch
        && session.mcu_boot_id == expected->mcu_boot_id
        && session.last_accepted_command_sequence == expected->last_accepted_command_sequence
        && mcu_fault_bits == expected->mcu_fault_bits) {
        queued = communication_runtime_enqueue_telemetry(telemetry);
    }
    taskEXIT_CRITICAL();
    return queued;
}
