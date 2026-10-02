#ifndef MECANUM_COMMUNICATION_H
#define MECANUM_COMMUNICATION_H

/*
 * Stateless UART v1 codec only.
 *
 * This interface performs byte framing and payload conversion.  It does not
 * own CONFIG acceptance, reset epochs, command sequence eligibility,
 * watchdogs, UART hardware, motor output, PID, PWM, or E-stop handling.
 */

#include <limits.h>
#include <float.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "../../Config/protocol_version.h"

#if defined(__STDC_VERSION__) && (__STDC_VERSION__ >= 201112L)
_Static_assert(CHAR_BIT == 8, "UART v1 requires 8-bit bytes");
_Static_assert(sizeof(float) == 4, "UART v1 float32_le requires binary32 characteristics");
_Static_assert(FLT_RADIX == 2, "UART v1 float32_le requires binary radix");
_Static_assert(FLT_MANT_DIG == 24, "UART v1 float32_le requires 24-bit precision");
_Static_assert(FLT_MAX_EXP == 128, "UART v1 float32_le requires binary32 maximum exponent");
_Static_assert(FLT_MIN_EXP == -125, "UART v1 float32_le requires binary32 minimum exponent");
#endif

#define MECANUM_UART_V1_MESSAGE_COMMAND UINT8_C(0x01)
#define MECANUM_UART_V1_MESSAGE_TELEMETRY UINT8_C(0x02)
#define MECANUM_UART_V1_MESSAGE_CONFIG UINT8_C(0x03)

#define MECANUM_UART_V1_COMMAND_PAYLOAD_LENGTH UINT8_C(20)
#define MECANUM_UART_V1_TELEMETRY_PAYLOAD_LENGTH UINT8_C(65)
#define MECANUM_UART_V1_CONFIG_REQUEST_PAYLOAD_LENGTH UINT8_C(40)
#define MECANUM_UART_V1_CONFIG_STATUS_PAYLOAD_LENGTH UINT8_C(50)

#define MECANUM_UART_V1_CONFIG_ACCEPTED UINT8_C(0x01)
#define MECANUM_UART_V1_CONFIG_REJECTED UINT8_C(0x02)
#define MECANUM_UART_V1_REJECT_NONE UINT8_C(0x00)
#define MECANUM_UART_V1_REJECT_HASH_MISMATCH UINT8_C(0x01)
#define MECANUM_UART_V1_REJECT_LOCAL_CONFIG_INVALID UINT8_C(0x02)

#define MECANUM_UART_V1_HEADER_LENGTH ((size_t)4U)
#define MECANUM_UART_V1_CRC_LENGTH ((size_t)2U)
#define MECANUM_UART_V1_MAX_PAYLOAD_LENGTH ((size_t)65U)
#define MECANUM_UART_V1_RAW_BUFFER_MINIMUM ((size_t)96U)
#define MECANUM_UART_V1_COBS_BUFFER_MINIMUM ((size_t)98U)
#define MECANUM_UART_V1_WIRE_DELIMITER UINT8_C(0x00)

typedef enum {
    MECANUM_UART_V1_OK = 0,
    MECANUM_UART_V1_ERROR_ARGUMENT,
    MECANUM_UART_V1_ERROR_BUFFER_TOO_SMALL,
    MECANUM_UART_V1_ERROR_COBS,
    MECANUM_UART_V1_ERROR_DELIMITER,
    MECANUM_UART_V1_ERROR_CRC,
    MECANUM_UART_V1_ERROR_PROTOCOL_VERSION,
    MECANUM_UART_V1_ERROR_MESSAGE_TYPE,
    MECANUM_UART_V1_ERROR_PAYLOAD_LENGTH
} mecanum_uart_v1_status_t;

typedef struct {
    uint32_t command_sequence;
    uint32_t reset_epoch;
    float vx_mps;
    float vy_mps;
    float wz_radps;
} mecanum_uart_v1_command_t;

typedef struct {
    uint32_t telemetry_sequence;
    uint64_t mcu_boot_id;
    uint32_t reset_epoch;
    uint64_t mcu_monotonic_time_us;
    int64_t ticks_fl;
    int64_t ticks_fr;
    int64_t ticks_rl;
    int64_t ticks_rr;
    uint32_t last_accepted_command_sequence;
    uint32_t mcu_fault_bits;
    uint8_t estop_aux_active;
} mecanum_uart_v1_telemetry_t;

typedef struct {
    uint32_t config_sequence;
    uint32_t reset_epoch;
    uint8_t hardware_config_hash[32];
} mecanum_uart_v1_config_request_t;

typedef struct {
    uint32_t config_sequence;
    uint32_t reset_epoch;
    uint8_t hardware_config_hash[32];
    uint64_t mcu_boot_id;
    uint8_t config_status;
    uint8_t reject_reason;
} mecanum_uart_v1_config_status_t;

typedef struct {
    uint16_t protocol_version;
    uint8_t message_type;
    uint8_t payload_length;
    uint8_t payload[MECANUM_UART_V1_MAX_PAYLOAD_LENGTH];
} mecanum_uart_v1_frame_t;

uint16_t mecanum_uart_v1_crc16_ccitt_false(const uint8_t *bytes, size_t length);

mecanum_uart_v1_status_t mecanum_uart_v1_cobs_encode(
    const uint8_t *input, size_t input_length, uint8_t *output,
    size_t output_capacity, size_t *output_length);
mecanum_uart_v1_status_t mecanum_uart_v1_cobs_decode(
    const uint8_t *input, size_t input_length, uint8_t *output,
    size_t output_capacity, size_t *output_length);

mecanum_uart_v1_status_t mecanum_uart_v1_serialize_command(
    const mecanum_uart_v1_command_t *command, uint8_t *payload,
    size_t payload_capacity);
mecanum_uart_v1_status_t mecanum_uart_v1_parse_command(
    const uint8_t *payload, size_t payload_length,
    mecanum_uart_v1_command_t *command);
bool mecanum_uart_v1_command_is_finite(const mecanum_uart_v1_command_t *command);

mecanum_uart_v1_status_t mecanum_uart_v1_serialize_telemetry(
    const mecanum_uart_v1_telemetry_t *telemetry, uint8_t *payload,
    size_t payload_capacity);
mecanum_uart_v1_status_t mecanum_uart_v1_parse_telemetry(
    const uint8_t *payload, size_t payload_length,
    mecanum_uart_v1_telemetry_t *telemetry);

mecanum_uart_v1_status_t mecanum_uart_v1_serialize_config_request(
    const mecanum_uart_v1_config_request_t *request, uint8_t *payload,
    size_t payload_capacity);
mecanum_uart_v1_status_t mecanum_uart_v1_parse_config_request(
    const uint8_t *payload, size_t payload_length,
    mecanum_uart_v1_config_request_t *request);

mecanum_uart_v1_status_t mecanum_uart_v1_serialize_config_status(
    const mecanum_uart_v1_config_status_t *status, uint8_t *payload,
    size_t payload_capacity);
mecanum_uart_v1_status_t mecanum_uart_v1_parse_config_status(
    const uint8_t *payload, size_t payload_length,
    mecanum_uart_v1_config_status_t *status);

mecanum_uart_v1_status_t mecanum_uart_v1_build_raw_frame(
    uint8_t message_type, const uint8_t *payload, size_t payload_length,
    uint8_t *raw_frame, size_t raw_capacity, size_t *raw_length);
mecanum_uart_v1_status_t mecanum_uart_v1_build_wire_frame(
    uint8_t message_type, const uint8_t *payload, size_t payload_length,
    uint8_t *wire_frame, size_t wire_capacity, size_t *wire_length);
mecanum_uart_v1_status_t mecanum_uart_v1_decode_wire_frame(
    const uint8_t *wire_frame, size_t wire_length,
    mecanum_uart_v1_frame_t *decoded_frame);

#endif /* MECANUM_COMMUNICATION_H */
