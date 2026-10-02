#ifndef MECANUM_CONTROL_SAFETY_SESSION_H
#define MECANUM_CONTROL_SAFETY_SESSION_H

/*
 * Pure logical CONFIG/COMMAND session owner.  This module receives decoded
 * codec structs and emits decisions only; it has no UART, timing, GPIO,
 * motor, PWM, PID, encoder, or E-stop hardware dependency.
 */

#include <stdbool.h>
#include <stdint.h>

#include "communication.h"

typedef enum {
    CONTROL_SAFETY_SESSION_BOOT_OR_UNCONFIGURED = 0,
    CONTROL_SAFETY_SESSION_CONFIG_ACCEPTED_MOTOR_DISABLED,
    CONTROL_SAFETY_SESSION_COMMAND_ACTIVE,
    CONTROL_SAFETY_SESSION_SAFE_STOP
} control_safety_session_state_t;

/* Internal-only diagnostics: never serialize these values over UART. */
typedef enum {
    CONTROL_SAFETY_SESSION_REJECT_NONE = 0,
    CONTROL_SAFETY_SESSION_REJECT_NO_CONFIGURED_SESSION,
    CONTROL_SAFETY_SESSION_REJECT_SAFE_STOP,
    CONTROL_SAFETY_SESSION_REJECT_WRONG_EPOCH,
    CONTROL_SAFETY_SESSION_REJECT_NONFINITE_COMMAND,
    CONTROL_SAFETY_SESSION_REJECT_DUPLICATE_SEQUENCE,
    CONTROL_SAFETY_SESSION_REJECT_BACKWARD_SEQUENCE,
    CONTROL_SAFETY_SESSION_REJECT_LOCAL_CONFIG_INVALID,
    CONTROL_SAFETY_SESSION_REJECT_HASH_MISMATCH
} control_safety_session_internal_reject_t;

typedef struct {
    bool config_status_available;
    mecanum_uart_v1_config_status_t config_status;
    bool command_accepted;
    bool watchdog_refresh_requested;
    bool logical_zero_command_requested;
    bool logical_motor_disable_requested;
    control_safety_session_internal_reject_t internal_reject_reason;
} control_safety_session_decision_t;

typedef struct {
    control_safety_session_state_t state;
    uint32_t configured_reset_epoch;
    uint8_t local_hardware_config_hash[32];
    bool local_config_valid;
    uint64_t mcu_boot_id;
    bool has_last_accepted_command;
    uint32_t last_accepted_command_sequence;
} control_safety_session_t;

/*
 * The current hardware profile is DRAFT, so the real firmware caller must
 * inject local_config_valid=false.  Host tests may inject true solely to test
 * this logical state machine.
 */
bool control_safety_session_init(
    control_safety_session_t *session,
    const uint8_t local_hardware_config_hash[32],
    bool local_config_valid,
    uint64_t mcu_boot_id);

bool control_safety_session_handle_config(
    control_safety_session_t *session,
    const mecanum_uart_v1_config_request_t *request,
    control_safety_session_decision_t *decision);

bool control_safety_session_handle_command(
    control_safety_session_t *session,
    const mecanum_uart_v1_command_t *command,
    control_safety_session_decision_t *decision);

bool control_safety_session_handle_watchdog_expired(
    control_safety_session_t *session,
    control_safety_session_decision_t *decision);

control_safety_session_state_t control_safety_session_get_state(
    const control_safety_session_t *session);

#endif /* MECANUM_CONTROL_SAFETY_SESSION_H */
