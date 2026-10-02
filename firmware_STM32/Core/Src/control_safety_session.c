#include "control_safety_session.h"

#include <string.h>

static void clear_decision(control_safety_session_decision_t *decision)
{
    memset(decision, 0, sizeof(*decision));
    decision->internal_reject_reason = CONTROL_SAFETY_SESSION_REJECT_NONE;
}

static void clear_accepted_command(control_safety_session_t *session)
{
    session->has_last_accepted_command = false;
    session->last_accepted_command_sequence = UINT32_C(0);
}

static void populate_config_status(
    const control_safety_session_t *session,
    const mecanum_uart_v1_config_request_t *request,
    uint8_t config_status,
    uint8_t reject_reason,
    control_safety_session_decision_t *decision)
{
    decision->config_status_available = true;
    decision->config_status.config_sequence = request->config_sequence;
    decision->config_status.reset_epoch = request->reset_epoch;
    memcpy(decision->config_status.hardware_config_hash,
           request->hardware_config_hash,
           sizeof(decision->config_status.hardware_config_hash));
    decision->config_status.mcu_boot_id = session->mcu_boot_id;
    decision->config_status.config_status = config_status;
    decision->config_status.reject_reason = reject_reason;
}

bool control_safety_session_init(
    control_safety_session_t *session,
    const uint8_t local_hardware_config_hash[32],
    bool local_config_valid,
    uint64_t mcu_boot_id)
{
    if ((session == NULL) || (local_hardware_config_hash == NULL)) {
        return false;
    }
    memset(session, 0, sizeof(*session));
    memcpy(session->local_hardware_config_hash, local_hardware_config_hash,
           sizeof(session->local_hardware_config_hash));
    session->state = CONTROL_SAFETY_SESSION_BOOT_OR_UNCONFIGURED;
    session->local_config_valid = local_config_valid;
    session->mcu_boot_id = mcu_boot_id;
    clear_accepted_command(session);
    return true;
}

bool control_safety_session_handle_config(
    control_safety_session_t *session,
    const mecanum_uart_v1_config_request_t *request,
    control_safety_session_decision_t *decision)
{
    if ((session == NULL) || (request == NULL) || (decision == NULL)) {
        return false;
    }
    clear_decision(decision);

    /* Local invalidity deliberately has precedence over hash mismatch. */
    if (!session->local_config_valid) {
        populate_config_status(session, request, MECANUM_UART_V1_CONFIG_REJECTED,
                               MECANUM_UART_V1_REJECT_LOCAL_CONFIG_INVALID,
                               decision);
        decision->internal_reject_reason =
            CONTROL_SAFETY_SESSION_REJECT_LOCAL_CONFIG_INVALID;
        return true;
    }
    if (memcmp(request->hardware_config_hash, session->local_hardware_config_hash,
               sizeof(session->local_hardware_config_hash)) != 0) {
        populate_config_status(session, request, MECANUM_UART_V1_CONFIG_REJECTED,
                               MECANUM_UART_V1_REJECT_HASH_MISMATCH, decision);
        decision->internal_reject_reason = CONTROL_SAFETY_SESSION_REJECT_HASH_MISMATCH;
        return true;
    }

    session->configured_reset_epoch = request->reset_epoch;
    clear_accepted_command(session);
    session->state = CONTROL_SAFETY_SESSION_CONFIG_ACCEPTED_MOTOR_DISABLED;
    decision->logical_motor_disable_requested = true;
    populate_config_status(session, request, MECANUM_UART_V1_CONFIG_ACCEPTED,
                           MECANUM_UART_V1_REJECT_NONE, decision);
    return true;
}

bool control_safety_session_handle_command(
    control_safety_session_t *session,
    const mecanum_uart_v1_command_t *command,
    control_safety_session_decision_t *decision)
{
    if ((session == NULL) || (command == NULL) || (decision == NULL)) {
        return false;
    }
    clear_decision(decision);

    if (session->state == CONTROL_SAFETY_SESSION_SAFE_STOP) {
        decision->internal_reject_reason = CONTROL_SAFETY_SESSION_REJECT_SAFE_STOP;
        return true;
    }
    if ((session->state != CONTROL_SAFETY_SESSION_CONFIG_ACCEPTED_MOTOR_DISABLED)
        && (session->state != CONTROL_SAFETY_SESSION_COMMAND_ACTIVE)) {
        decision->internal_reject_reason =
            CONTROL_SAFETY_SESSION_REJECT_NO_CONFIGURED_SESSION;
        return true;
    }
    if (command->reset_epoch != session->configured_reset_epoch) {
        decision->internal_reject_reason = CONTROL_SAFETY_SESSION_REJECT_WRONG_EPOCH;
        return true;
    }
    if (!mecanum_uart_v1_command_is_finite(command)) {
        decision->internal_reject_reason = CONTROL_SAFETY_SESSION_REJECT_NONFINITE_COMMAND;
        return true;
    }
    if (session->has_last_accepted_command) {
        if (command->command_sequence == session->last_accepted_command_sequence) {
            decision->internal_reject_reason =
                CONTROL_SAFETY_SESSION_REJECT_DUPLICATE_SEQUENCE;
            return true;
        }
        if (command->command_sequence < session->last_accepted_command_sequence) {
            decision->internal_reject_reason =
                CONTROL_SAFETY_SESSION_REJECT_BACKWARD_SEQUENCE;
            return true;
        }
    }

    session->has_last_accepted_command = true;
    session->last_accepted_command_sequence = command->command_sequence;
    session->state = CONTROL_SAFETY_SESSION_COMMAND_ACTIVE;
    decision->command_accepted = true;
    decision->watchdog_refresh_requested = true;
    return true;
}

bool control_safety_session_handle_watchdog_expired(
    control_safety_session_t *session,
    control_safety_session_decision_t *decision)
{
    if ((session == NULL) || (decision == NULL)) {
        return false;
    }
    clear_decision(decision);
    clear_accepted_command(session);
    session->state = CONTROL_SAFETY_SESSION_SAFE_STOP;
    decision->logical_zero_command_requested = true;
    decision->logical_motor_disable_requested = true;
    return true;
}

control_safety_session_state_t control_safety_session_get_state(
    const control_safety_session_t *session)
{
    if (session == NULL) {
        return CONTROL_SAFETY_SESSION_BOOT_OR_UNCONFIGURED;
    }
    return session->state;
}
