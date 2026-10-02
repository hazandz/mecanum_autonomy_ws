#include "communication.h"

#include <math.h>
#include <string.h>

static uint16_t read_u16_le(const uint8_t *bytes)
{
    return (uint16_t)((uint16_t)bytes[0] | ((uint16_t)bytes[1] << 8U));
}

static uint32_t read_u32_le(const uint8_t *bytes)
{
    return (uint32_t)bytes[0]
           | ((uint32_t)bytes[1] << 8U)
           | ((uint32_t)bytes[2] << 16U)
           | ((uint32_t)bytes[3] << 24U);
}

static uint64_t read_u64_le(const uint8_t *bytes)
{
    uint64_t value = UINT64_C(0);
    size_t index;

    for (index = 0U; index < 8U; ++index) {
        value |= ((uint64_t)bytes[index] << (index * 8U));
    }
    return value;
}

static int64_t read_i64_le(const uint8_t *bytes)
{
    const uint64_t bits = read_u64_le(bytes);
    const uint64_t sign_bit = UINT64_C(1) << 63U;

    if ((bits & sign_bit) == UINT64_C(0)) {
        return (int64_t)bits;
    }
    if (bits == sign_bit) {
        return INT64_MIN;
    }
    return -(int64_t)((~bits) + UINT64_C(1));
}

static void write_u16_le(uint8_t *bytes, uint16_t value)
{
    bytes[0] = (uint8_t)(value & UINT16_C(0x00ff));
    bytes[1] = (uint8_t)(value >> 8U);
}

static void write_u32_le(uint8_t *bytes, uint32_t value)
{
    bytes[0] = (uint8_t)(value & UINT32_C(0x000000ff));
    bytes[1] = (uint8_t)((value >> 8U) & UINT32_C(0x000000ff));
    bytes[2] = (uint8_t)((value >> 16U) & UINT32_C(0x000000ff));
    bytes[3] = (uint8_t)((value >> 24U) & UINT32_C(0x000000ff));
}

static void write_u64_le(uint8_t *bytes, uint64_t value)
{
    size_t index;

    for (index = 0U; index < 8U; ++index) {
        bytes[index] = (uint8_t)(value >> (index * 8U));
    }
}

static uint64_t i64_to_bits(int64_t value)
{
    if (value >= INT64_C(0)) {
        return (uint64_t)value;
    }
    if (value == INT64_MIN) {
        return UINT64_C(1) << 63U;
    }
    return (~(uint64_t)(-value)) + UINT64_C(1);
}

static void write_i64_le(uint8_t *bytes, int64_t value)
{
    write_u64_le(bytes, i64_to_bits(value));
}

static float read_float32_le(const uint8_t *bytes)
{
    const uint32_t bits = read_u32_le(bytes);
    float value;

    memcpy(&value, &bits, sizeof(value));
    return value;
}

static void write_float32_le(uint8_t *bytes, float value)
{
    uint32_t bits;

    memcpy(&bits, &value, sizeof(bits));
    write_u32_le(bytes, bits);
}

static bool is_known_message_type(uint8_t message_type)
{
    return (message_type == MECANUM_UART_V1_MESSAGE_COMMAND)
           || (message_type == MECANUM_UART_V1_MESSAGE_TELEMETRY)
           || (message_type == MECANUM_UART_V1_MESSAGE_CONFIG);
}

static bool is_exact_payload_length(uint8_t message_type, size_t payload_length)
{
    if (message_type == MECANUM_UART_V1_MESSAGE_COMMAND) {
        return payload_length == MECANUM_UART_V1_COMMAND_PAYLOAD_LENGTH;
    }
    if (message_type == MECANUM_UART_V1_MESSAGE_TELEMETRY) {
        return payload_length == MECANUM_UART_V1_TELEMETRY_PAYLOAD_LENGTH;
    }
    if (message_type == MECANUM_UART_V1_MESSAGE_CONFIG) {
        return (payload_length == MECANUM_UART_V1_CONFIG_REQUEST_PAYLOAD_LENGTH)
               || (payload_length == MECANUM_UART_V1_CONFIG_STATUS_PAYLOAD_LENGTH);
    }
    return false;
}

uint16_t mecanum_uart_v1_crc16_ccitt_false(const uint8_t *bytes, size_t length)
{
    uint16_t crc = UINT16_C(0xffff);
    size_t index;

    if ((bytes == NULL) && (length != 0U)) {
        return UINT16_C(0);
    }
    for (index = 0U; index < length; ++index) {
        uint8_t bit;
        crc ^= (uint16_t)bytes[index] << 8U;
        for (bit = 0U; bit < 8U; ++bit) {
            crc = ((crc & UINT16_C(0x8000)) != UINT16_C(0))
                      ? (uint16_t)((crc << 1U) ^ UINT16_C(0x1021))
                      : (uint16_t)(crc << 1U);
        }
    }
    return crc;
}

mecanum_uart_v1_status_t mecanum_uart_v1_cobs_encode(
    const uint8_t *input, size_t input_length, uint8_t *output,
    size_t output_capacity, size_t *output_length)
{
    size_t input_index = 0U;
    size_t output_index = 1U;
    size_t code_index = 0U;
    uint8_t code = UINT8_C(1);

    if ((input == NULL) || (output == NULL) || (output_length == NULL)) {
        return MECANUM_UART_V1_ERROR_ARGUMENT;
    }
    if (output_capacity == 0U) {
        return MECANUM_UART_V1_ERROR_BUFFER_TOO_SMALL;
    }
    while (input_index < input_length) {
        if (input[input_index] == UINT8_C(0)) {
            if (code_index >= output_capacity) {
                return MECANUM_UART_V1_ERROR_BUFFER_TOO_SMALL;
            }
            output[code_index] = code;
            code_index = output_index;
            ++output_index;
            code = UINT8_C(1);
        } else {
            if (output_index >= output_capacity) {
                return MECANUM_UART_V1_ERROR_BUFFER_TOO_SMALL;
            }
            output[output_index] = input[input_index];
            ++output_index;
            ++code;
            if (code == UINT8_C(0xff)) {
                if (code_index >= output_capacity) {
                    return MECANUM_UART_V1_ERROR_BUFFER_TOO_SMALL;
                }
                output[code_index] = code;
                code_index = output_index;
                ++output_index;
                code = UINT8_C(1);
            }
        }
        ++input_index;
    }
    if (code_index >= output_capacity) {
        return MECANUM_UART_V1_ERROR_BUFFER_TOO_SMALL;
    }
    output[code_index] = code;
    *output_length = output_index;
    return MECANUM_UART_V1_OK;
}

mecanum_uart_v1_status_t mecanum_uart_v1_cobs_decode(
    const uint8_t *input, size_t input_length, uint8_t *output,
    size_t output_capacity, size_t *output_length)
{
    size_t input_index = 0U;
    size_t output_index = 0U;

    if ((input == NULL) || (output == NULL) || (output_length == NULL)
        || (input_length == 0U)) {
        return MECANUM_UART_V1_ERROR_ARGUMENT;
    }
    while (input_index < input_length) {
        uint8_t code = input[input_index];
        size_t copy_count;
        size_t offset;

        if (code == UINT8_C(0)) {
            return MECANUM_UART_V1_ERROR_COBS;
        }
        ++input_index;
        copy_count = (size_t)code - 1U;
        if (copy_count > (input_length - input_index)) {
            return MECANUM_UART_V1_ERROR_COBS;
        }
        if (copy_count > (output_capacity - output_index)) {
            return MECANUM_UART_V1_ERROR_BUFFER_TOO_SMALL;
        }
        for (offset = 0U; offset < copy_count; ++offset) {
            output[output_index + offset] = input[input_index + offset];
        }
        input_index += copy_count;
        output_index += copy_count;
        if ((code != UINT8_C(0xff)) && (input_index < input_length)) {
            if (output_index >= output_capacity) {
                return MECANUM_UART_V1_ERROR_BUFFER_TOO_SMALL;
            }
            output[output_index] = UINT8_C(0);
            ++output_index;
        }
    }
    *output_length = output_index;
    return MECANUM_UART_V1_OK;
}

mecanum_uart_v1_status_t mecanum_uart_v1_serialize_command(
    const mecanum_uart_v1_command_t *command, uint8_t *payload,
    size_t payload_capacity)
{
    if ((command == NULL) || (payload == NULL)) {
        return MECANUM_UART_V1_ERROR_ARGUMENT;
    }
    if (payload_capacity < MECANUM_UART_V1_COMMAND_PAYLOAD_LENGTH) {
        return MECANUM_UART_V1_ERROR_BUFFER_TOO_SMALL;
    }
    write_u32_le(&payload[0], command->command_sequence);
    write_u32_le(&payload[4], command->reset_epoch);
    write_float32_le(&payload[8], command->vx_mps);
    write_float32_le(&payload[12], command->vy_mps);
    write_float32_le(&payload[16], command->wz_radps);
    return MECANUM_UART_V1_OK;
}

mecanum_uart_v1_status_t mecanum_uart_v1_parse_command(
    const uint8_t *payload, size_t payload_length,
    mecanum_uart_v1_command_t *command)
{
    if ((payload == NULL) || (command == NULL)) {
        return MECANUM_UART_V1_ERROR_ARGUMENT;
    }
    if (payload_length != MECANUM_UART_V1_COMMAND_PAYLOAD_LENGTH) {
        return MECANUM_UART_V1_ERROR_PAYLOAD_LENGTH;
    }
    command->command_sequence = read_u32_le(&payload[0]);
    command->reset_epoch = read_u32_le(&payload[4]);
    command->vx_mps = read_float32_le(&payload[8]);
    command->vy_mps = read_float32_le(&payload[12]);
    command->wz_radps = read_float32_le(&payload[16]);
    return MECANUM_UART_V1_OK;
}

bool mecanum_uart_v1_command_is_finite(const mecanum_uart_v1_command_t *command)
{
    return (command != NULL) && isfinite(command->vx_mps)
           && isfinite(command->vy_mps) && isfinite(command->wz_radps);
}

mecanum_uart_v1_status_t mecanum_uart_v1_serialize_telemetry(
    const mecanum_uart_v1_telemetry_t *telemetry, uint8_t *payload,
    size_t payload_capacity)
{
    if ((telemetry == NULL) || (payload == NULL)) {
        return MECANUM_UART_V1_ERROR_ARGUMENT;
    }
    if (payload_capacity < MECANUM_UART_V1_TELEMETRY_PAYLOAD_LENGTH) {
        return MECANUM_UART_V1_ERROR_BUFFER_TOO_SMALL;
    }
    write_u32_le(&payload[0], telemetry->telemetry_sequence);
    write_u64_le(&payload[4], telemetry->mcu_boot_id);
    write_u32_le(&payload[12], telemetry->reset_epoch);
    write_u64_le(&payload[16], telemetry->mcu_monotonic_time_us);
    write_i64_le(&payload[24], telemetry->ticks_fl);
    write_i64_le(&payload[32], telemetry->ticks_fr);
    write_i64_le(&payload[40], telemetry->ticks_rl);
    write_i64_le(&payload[48], telemetry->ticks_rr);
    write_u32_le(&payload[56], telemetry->last_accepted_command_sequence);
    write_u32_le(&payload[60], telemetry->mcu_fault_bits);
    payload[64] = telemetry->estop_aux_active;
    return MECANUM_UART_V1_OK;
}

mecanum_uart_v1_status_t mecanum_uart_v1_parse_telemetry(
    const uint8_t *payload, size_t payload_length,
    mecanum_uart_v1_telemetry_t *telemetry)
{
    if ((payload == NULL) || (telemetry == NULL)) {
        return MECANUM_UART_V1_ERROR_ARGUMENT;
    }
    if (payload_length != MECANUM_UART_V1_TELEMETRY_PAYLOAD_LENGTH) {
        return MECANUM_UART_V1_ERROR_PAYLOAD_LENGTH;
    }
    telemetry->telemetry_sequence = read_u32_le(&payload[0]);
    telemetry->mcu_boot_id = read_u64_le(&payload[4]);
    telemetry->reset_epoch = read_u32_le(&payload[12]);
    telemetry->mcu_monotonic_time_us = read_u64_le(&payload[16]);
    telemetry->ticks_fl = read_i64_le(&payload[24]);
    telemetry->ticks_fr = read_i64_le(&payload[32]);
    telemetry->ticks_rl = read_i64_le(&payload[40]);
    telemetry->ticks_rr = read_i64_le(&payload[48]);
    telemetry->last_accepted_command_sequence = read_u32_le(&payload[56]);
    telemetry->mcu_fault_bits = read_u32_le(&payload[60]);
    telemetry->estop_aux_active = payload[64];
    return MECANUM_UART_V1_OK;
}

mecanum_uart_v1_status_t mecanum_uart_v1_serialize_config_request(
    const mecanum_uart_v1_config_request_t *request, uint8_t *payload,
    size_t payload_capacity)
{
    if ((request == NULL) || (payload == NULL)) {
        return MECANUM_UART_V1_ERROR_ARGUMENT;
    }
    if (payload_capacity < MECANUM_UART_V1_CONFIG_REQUEST_PAYLOAD_LENGTH) {
        return MECANUM_UART_V1_ERROR_BUFFER_TOO_SMALL;
    }
    write_u32_le(&payload[0], request->config_sequence);
    write_u32_le(&payload[4], request->reset_epoch);
    memcpy(&payload[8], request->hardware_config_hash,
           sizeof(request->hardware_config_hash));
    return MECANUM_UART_V1_OK;
}

mecanum_uart_v1_status_t mecanum_uart_v1_parse_config_request(
    const uint8_t *payload, size_t payload_length,
    mecanum_uart_v1_config_request_t *request)
{
    if ((payload == NULL) || (request == NULL)) {
        return MECANUM_UART_V1_ERROR_ARGUMENT;
    }
    if (payload_length != MECANUM_UART_V1_CONFIG_REQUEST_PAYLOAD_LENGTH) {
        return MECANUM_UART_V1_ERROR_PAYLOAD_LENGTH;
    }
    request->config_sequence = read_u32_le(&payload[0]);
    request->reset_epoch = read_u32_le(&payload[4]);
    memcpy(request->hardware_config_hash, &payload[8],
           sizeof(request->hardware_config_hash));
    return MECANUM_UART_V1_OK;
}

mecanum_uart_v1_status_t mecanum_uart_v1_serialize_config_status(
    const mecanum_uart_v1_config_status_t *status, uint8_t *payload,
    size_t payload_capacity)
{
    if ((status == NULL) || (payload == NULL)) {
        return MECANUM_UART_V1_ERROR_ARGUMENT;
    }
    if (payload_capacity < MECANUM_UART_V1_CONFIG_STATUS_PAYLOAD_LENGTH) {
        return MECANUM_UART_V1_ERROR_BUFFER_TOO_SMALL;
    }
    write_u32_le(&payload[0], status->config_sequence);
    write_u32_le(&payload[4], status->reset_epoch);
    memcpy(&payload[8], status->hardware_config_hash,
           sizeof(status->hardware_config_hash));
    write_u64_le(&payload[40], status->mcu_boot_id);
    payload[48] = status->config_status;
    payload[49] = status->reject_reason;
    return MECANUM_UART_V1_OK;
}

mecanum_uart_v1_status_t mecanum_uart_v1_parse_config_status(
    const uint8_t *payload, size_t payload_length,
    mecanum_uart_v1_config_status_t *status)
{
    if ((payload == NULL) || (status == NULL)) {
        return MECANUM_UART_V1_ERROR_ARGUMENT;
    }
    if (payload_length != MECANUM_UART_V1_CONFIG_STATUS_PAYLOAD_LENGTH) {
        return MECANUM_UART_V1_ERROR_PAYLOAD_LENGTH;
    }
    status->config_sequence = read_u32_le(&payload[0]);
    status->reset_epoch = read_u32_le(&payload[4]);
    memcpy(status->hardware_config_hash, &payload[8],
           sizeof(status->hardware_config_hash));
    status->mcu_boot_id = read_u64_le(&payload[40]);
    status->config_status = payload[48];
    status->reject_reason = payload[49];
    return MECANUM_UART_V1_OK;
}

mecanum_uart_v1_status_t mecanum_uart_v1_build_raw_frame(
    uint8_t message_type, const uint8_t *payload, size_t payload_length,
    uint8_t *raw_frame, size_t raw_capacity, size_t *raw_length)
{
    const size_t required_length = MECANUM_UART_V1_HEADER_LENGTH
                                   + payload_length
                                   + MECANUM_UART_V1_CRC_LENGTH;
    uint16_t crc;

    if ((payload == NULL) || (raw_frame == NULL) || (raw_length == NULL)) {
        return MECANUM_UART_V1_ERROR_ARGUMENT;
    }
    if (!is_known_message_type(message_type)) {
        return MECANUM_UART_V1_ERROR_MESSAGE_TYPE;
    }
    if (!is_exact_payload_length(message_type, payload_length)) {
        return MECANUM_UART_V1_ERROR_PAYLOAD_LENGTH;
    }
    if ((raw_capacity < required_length)
        || (required_length > MECANUM_UART_V1_RAW_BUFFER_MINIMUM)) {
        return MECANUM_UART_V1_ERROR_BUFFER_TOO_SMALL;
    }
    write_u16_le(&raw_frame[0], MECANUM_UART_V1_PROTOCOL_VERSION);
    raw_frame[2] = message_type;
    raw_frame[3] = (uint8_t)payload_length;
    memcpy(&raw_frame[4], payload, payload_length);
    crc = mecanum_uart_v1_crc16_ccitt_false(raw_frame,
                                             MECANUM_UART_V1_HEADER_LENGTH + payload_length);
    write_u16_le(&raw_frame[4U + payload_length], crc);
    *raw_length = required_length;
    return MECANUM_UART_V1_OK;
}

mecanum_uart_v1_status_t mecanum_uart_v1_build_wire_frame(
    uint8_t message_type, const uint8_t *payload, size_t payload_length,
    uint8_t *wire_frame, size_t wire_capacity, size_t *wire_length)
{
    uint8_t raw_frame[MECANUM_UART_V1_RAW_BUFFER_MINIMUM];
    size_t raw_length;
    size_t encoded_length;
    mecanum_uart_v1_status_t result;

    if ((wire_frame == NULL) || (wire_length == NULL)) {
        return MECANUM_UART_V1_ERROR_ARGUMENT;
    }
    result = mecanum_uart_v1_build_raw_frame(message_type, payload,
                                              payload_length, raw_frame,
                                              sizeof(raw_frame), &raw_length);
    if (result != MECANUM_UART_V1_OK) {
        return result;
    }
    if (wire_capacity < 2U) {
        return MECANUM_UART_V1_ERROR_BUFFER_TOO_SMALL;
    }
    result = mecanum_uart_v1_cobs_encode(raw_frame, raw_length, wire_frame,
                                          wire_capacity - 1U, &encoded_length);
    if (result != MECANUM_UART_V1_OK) {
        return result;
    }
    if (encoded_length >= wire_capacity) {
        return MECANUM_UART_V1_ERROR_BUFFER_TOO_SMALL;
    }
    wire_frame[encoded_length] = MECANUM_UART_V1_WIRE_DELIMITER;
    *wire_length = encoded_length + 1U;
    return MECANUM_UART_V1_OK;
}

mecanum_uart_v1_status_t mecanum_uart_v1_decode_wire_frame(
    const uint8_t *wire_frame, size_t wire_length,
    mecanum_uart_v1_frame_t *decoded_frame)
{
    uint8_t raw_frame[MECANUM_UART_V1_RAW_BUFFER_MINIMUM];
    size_t raw_length;
    size_t payload_length;
    uint16_t stored_crc;
    uint16_t calculated_crc;
    mecanum_uart_v1_status_t result;

    if ((wire_frame == NULL) || (decoded_frame == NULL)) {
        return MECANUM_UART_V1_ERROR_ARGUMENT;
    }
    if ((wire_length < 2U) || (wire_length > MECANUM_UART_V1_COBS_BUFFER_MINIMUM)) {
        return MECANUM_UART_V1_ERROR_BUFFER_TOO_SMALL;
    }
    if (wire_frame[wire_length - 1U] != MECANUM_UART_V1_WIRE_DELIMITER) {
        return MECANUM_UART_V1_ERROR_DELIMITER;
    }
    result = mecanum_uart_v1_cobs_decode(wire_frame, wire_length - 1U,
                                          raw_frame, sizeof(raw_frame),
                                          &raw_length);
    if (result != MECANUM_UART_V1_OK) {
        return result;
    }
    if (raw_length < (MECANUM_UART_V1_HEADER_LENGTH + MECANUM_UART_V1_CRC_LENGTH)) {
        return MECANUM_UART_V1_ERROR_PAYLOAD_LENGTH;
    }
    if (read_u16_le(&raw_frame[0]) != MECANUM_UART_V1_PROTOCOL_VERSION) {
        return MECANUM_UART_V1_ERROR_PROTOCOL_VERSION;
    }
    if (!is_known_message_type(raw_frame[2])) {
        return MECANUM_UART_V1_ERROR_MESSAGE_TYPE;
    }
    payload_length = (size_t)raw_frame[3];
    if (!is_exact_payload_length(raw_frame[2], payload_length)
        || (raw_length != (MECANUM_UART_V1_HEADER_LENGTH + payload_length
                           + MECANUM_UART_V1_CRC_LENGTH))) {
        return MECANUM_UART_V1_ERROR_PAYLOAD_LENGTH;
    }
    stored_crc = read_u16_le(&raw_frame[MECANUM_UART_V1_HEADER_LENGTH + payload_length]);
    calculated_crc = mecanum_uart_v1_crc16_ccitt_false(
        raw_frame, MECANUM_UART_V1_HEADER_LENGTH + payload_length);
    if (stored_crc != calculated_crc) {
        return MECANUM_UART_V1_ERROR_CRC;
    }
    decoded_frame->protocol_version = MECANUM_UART_V1_PROTOCOL_VERSION;
    decoded_frame->message_type = raw_frame[2];
    decoded_frame->payload_length = (uint8_t)payload_length;
    memcpy(decoded_frame->payload, &raw_frame[4], payload_length);
    return MECANUM_UART_V1_OK;
}
