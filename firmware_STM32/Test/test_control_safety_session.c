#include "control_safety_session.h"

#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static const uint8_t fixture_hash[32] = {
    0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
    0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f,
    0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17,
    0x18, 0x19, 0x1a, 0x1b, 0x1c, 0x1d, 0x1e, 0x1f
};

static control_safety_session_t make_session(bool local_config_valid)
{
    control_safety_session_t session;

    assert(control_safety_session_init(&session, fixture_hash, local_config_valid,
                                       UINT64_C(0x0102030405060708)));
    return session;
}

static mecanum_uart_v1_config_request_t make_request(uint32_t sequence, uint32_t epoch)
{
    mecanum_uart_v1_config_request_t request;

    request.config_sequence = sequence;
    request.reset_epoch = epoch;
    memcpy(request.hardware_config_hash, fixture_hash, sizeof(request.hardware_config_hash));
    return request;
}

static mecanum_uart_v1_command_t make_command(uint32_t sequence, uint32_t epoch)
{
    mecanum_uart_v1_command_t command = {
        sequence, epoch, 1.25F, -0.5F, 0.75F
    };

    return command;
}

static void configure_valid_session(control_safety_session_t *session, uint32_t epoch)
{
    control_safety_session_decision_t decision;
    const mecanum_uart_v1_config_request_t request = make_request(UINT32_C(0x01020304), epoch);

    assert(control_safety_session_handle_config(session, &request, &decision));
    assert(decision.config_status_available);
    assert(decision.config_status.config_status == MECANUM_UART_V1_CONFIG_ACCEPTED);
    assert(decision.config_status.reject_reason == MECANUM_UART_V1_REJECT_NONE);
    assert(decision.config_status.config_sequence == request.config_sequence);
    assert(decision.config_status.reset_epoch == request.reset_epoch);
    assert(memcmp(decision.config_status.hardware_config_hash, request.hardware_config_hash,
                  sizeof(request.hardware_config_hash)) == 0);
    assert(decision.config_status.mcu_boot_id == UINT64_C(0x0102030405060708));
    assert(decision.logical_motor_disable_requested);
    assert(control_safety_session_get_state(session)
           == CONTROL_SAFETY_SESSION_CONFIG_ACCEPTED_MOTOR_DISABLED);
}

static void test_valid_config_and_repeated_config(void)
{
    control_safety_session_t session = make_session(true);
    control_safety_session_decision_t decision;
    const uint32_t epoch = UINT32_C(0x11223344);
    const mecanum_uart_v1_command_t command = make_command(UINT32_C(0x10203040), epoch);
    const mecanum_uart_v1_config_request_t repeated = make_request(UINT32_C(0x01020305), epoch);

    configure_valid_session(&session, epoch);
    assert(control_safety_session_handle_command(&session, &command, &decision));
    assert(decision.command_accepted && decision.watchdog_refresh_requested);
    assert(session.has_last_accepted_command);
    assert(control_safety_session_get_state(&session) == CONTROL_SAFETY_SESSION_COMMAND_ACTIVE);
    assert(control_safety_session_handle_config(&session, &repeated, &decision));
    assert(decision.config_status_available);
    assert(decision.config_status.config_status == MECANUM_UART_V1_CONFIG_ACCEPTED);
    assert(decision.logical_motor_disable_requested);
    assert(!session.has_last_accepted_command);
    assert(session.last_accepted_command_sequence == UINT32_C(0));
    assert(control_safety_session_get_state(&session)
           == CONTROL_SAFETY_SESSION_CONFIG_ACCEPTED_MOTOR_DISABLED);
}

static void test_config_rejections_preserve_session(void)
{
    control_safety_session_t session = make_session(true);
    control_safety_session_t before;
    control_safety_session_decision_t decision;
    mecanum_uart_v1_config_request_t wrong_hash;
    const uint32_t epoch = UINT32_C(0x11223344);

    configure_valid_session(&session, epoch);
    assert(control_safety_session_handle_command(
        &session, &(mecanum_uart_v1_command_t){UINT32_C(0x10203040), epoch, 0.0F, 0.0F, 0.0F},
        &decision));
    before = session;
    wrong_hash = make_request(UINT32_C(0x01020305), epoch);
    wrong_hash.hardware_config_hash[0] = UINT8_C(0xff);
    assert(control_safety_session_handle_config(&session, &wrong_hash, &decision));
    assert(decision.config_status_available);
    assert(decision.config_status.config_status == MECANUM_UART_V1_CONFIG_REJECTED);
    assert(decision.config_status.reject_reason == MECANUM_UART_V1_REJECT_HASH_MISMATCH);
    assert(decision.internal_reject_reason == CONTROL_SAFETY_SESSION_REJECT_HASH_MISMATCH);
    assert(memcmp(&session, &before, sizeof(session)) == 0);

    session = make_session(false);
    wrong_hash = make_request(UINT32_C(0x01020306), epoch);
    wrong_hash.hardware_config_hash[0] = UINT8_C(0xff);
    before = session;
    assert(control_safety_session_handle_config(&session, &wrong_hash, &decision));
    assert(decision.config_status_available);
    assert(decision.config_status.config_status == MECANUM_UART_V1_CONFIG_REJECTED);
    assert(decision.config_status.reject_reason
           == MECANUM_UART_V1_REJECT_LOCAL_CONFIG_INVALID);
    assert(decision.internal_reject_reason
           == CONTROL_SAFETY_SESSION_REJECT_LOCAL_CONFIG_INVALID);
    assert(memcmp(&session, &before, sizeof(session)) == 0);
}

static void test_command_rejections_and_golden_i7_i9(void)
{
    control_safety_session_t session = make_session(true);
    control_safety_session_decision_t decision;
    const uint32_t epoch = UINT32_C(0x11223344);
    mecanum_uart_v1_command_t command;
    control_safety_session_t before;
    uint32_t accepted_sequence;

    command = make_command(UINT32_C(0x10203040), epoch);
    before = session;
    assert(control_safety_session_handle_command(&session, &command, &decision));
    assert(!decision.command_accepted && !decision.watchdog_refresh_requested);
    assert(decision.internal_reject_reason
           == CONTROL_SAFETY_SESSION_REJECT_NO_CONFIGURED_SESSION);
    assert(!decision.config_status_available);
    assert(memcmp(&session, &before, sizeof(session)) == 0);

    configure_valid_session(&session, epoch);
    assert(control_safety_session_handle_command(&session, &command, &decision));
    assert(decision.command_accepted && decision.watchdog_refresh_requested);
    accepted_sequence = session.last_accepted_command_sequence;

    /* Golden I7: duplicate sequence. */
    before = session;
    assert(control_safety_session_handle_command(&session, &command, &decision));
    assert(decision.internal_reject_reason
           == CONTROL_SAFETY_SESSION_REJECT_DUPLICATE_SEQUENCE);
    assert(!decision.command_accepted && !decision.watchdog_refresh_requested);
    assert(session.last_accepted_command_sequence == accepted_sequence);
    assert(!decision.config_status_available);
    assert(memcmp(&session, &before, sizeof(session)) == 0);

    /* Golden I8: backward sequence. */
    command.command_sequence = UINT32_C(0x1020303f);
    before = session;
    assert(control_safety_session_handle_command(&session, &command, &decision));
    assert(decision.internal_reject_reason
           == CONTROL_SAFETY_SESSION_REJECT_BACKWARD_SEQUENCE);
    assert(!decision.command_accepted && !decision.watchdog_refresh_requested);
    assert(session.last_accepted_command_sequence == accepted_sequence);
    assert(!decision.config_status_available);
    assert(memcmp(&session, &before, sizeof(session)) == 0);

    /* Golden I9: wrong reset epoch. */
    command = make_command(UINT32_C(0x10203041), UINT32_C(0x11223345));
    before = session;
    assert(control_safety_session_handle_command(&session, &command, &decision));
    assert(decision.internal_reject_reason == CONTROL_SAFETY_SESSION_REJECT_WRONG_EPOCH);
    assert(!decision.command_accepted && !decision.watchdog_refresh_requested);
    assert(session.last_accepted_command_sequence == accepted_sequence);
    assert(!decision.config_status_available);
    assert(memcmp(&session, &before, sizeof(session)) == 0);
}

static void test_nonfinite_watchdog_and_recovery(void)
{
    control_safety_session_t session = make_session(true);
    control_safety_session_decision_t decision;
    const uint32_t epoch = UINT32_C(0x11223344);
    mecanum_uart_v1_command_t command = make_command(UINT32_C(0x10203040), epoch);
    const mecanum_uart_v1_config_request_t recovery = make_request(UINT32_C(0x01020307), epoch);
    control_safety_session_t before;

    configure_valid_session(&session, epoch);
    command.vx_mps = NAN; /* Golden I6 semantic non-finite command. */
    before = session;
    assert(control_safety_session_handle_command(&session, &command, &decision));
    assert(decision.internal_reject_reason
           == CONTROL_SAFETY_SESSION_REJECT_NONFINITE_COMMAND);
    assert(!decision.command_accepted && !decision.watchdog_refresh_requested);
    assert(!session.has_last_accepted_command);
    assert(memcmp(&session, &before, sizeof(session)) == 0);
    command.vx_mps = INFINITY;
    before = session;
    assert(control_safety_session_handle_command(&session, &command, &decision));
    assert(decision.internal_reject_reason
           == CONTROL_SAFETY_SESSION_REJECT_NONFINITE_COMMAND);
    assert(memcmp(&session, &before, sizeof(session)) == 0);

    command = make_command(UINT32_C(0x10203040), epoch);
    assert(control_safety_session_handle_command(&session, &command, &decision));
    assert(control_safety_session_handle_watchdog_expired(&session, &decision));
    assert(control_safety_session_get_state(&session) == CONTROL_SAFETY_SESSION_SAFE_STOP);
    assert(!session.has_last_accepted_command);
    assert(decision.logical_zero_command_requested);
    assert(decision.logical_motor_disable_requested);
    assert(!decision.config_status_available);
    assert(control_safety_session_handle_watchdog_expired(&session, &decision));
    assert(control_safety_session_get_state(&session) == CONTROL_SAFETY_SESSION_SAFE_STOP);
    assert(decision.logical_zero_command_requested && decision.logical_motor_disable_requested);

    before = session;
    assert(control_safety_session_handle_command(&session, &command, &decision));
    assert(decision.internal_reject_reason == CONTROL_SAFETY_SESSION_REJECT_SAFE_STOP);
    assert(!decision.command_accepted && !decision.watchdog_refresh_requested);
    assert(!decision.config_status_available);
    assert(memcmp(&session, &before, sizeof(session)) == 0);

    assert(control_safety_session_handle_config(&session, &recovery, &decision));
    assert(decision.config_status.config_status == MECANUM_UART_V1_CONFIG_ACCEPTED);
    assert(decision.logical_motor_disable_requested);
    assert(control_safety_session_get_state(&session)
           == CONTROL_SAFETY_SESSION_CONFIG_ACCEPTED_MOTOR_DISABLED);
    assert(!session.has_last_accepted_command);
}

int main(void)
{
    test_valid_config_and_repeated_config();
    test_config_rejections_preserve_session();
    test_command_rejections_and_golden_i7_i9();
    test_nonfinite_watchdog_and_recovery();

    puts("ControlSafety/session host tests passed: CONFIG, I6-I9, watchdog, and recovery.");
    return 0;
}
