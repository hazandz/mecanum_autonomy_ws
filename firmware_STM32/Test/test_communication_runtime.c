#include "communication_runtime.h"
#include "FreeRTOS.h"
#include "queue.h"
#include "task.h"

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

USART_TypeDef fake_usart6;
static uint32_t fake_tick = UINT32_MAX - 3U;
static HAL_StatusTypeDef receive_status = HAL_OK, transmit_status = HAL_OK;
static uint8_t *active_rx;
static uint16_t active_rx_capacity;
static unsigned receive_calls, transmit_calls, abort_calls, yields;
static uint8_t transmitted[16][MECANUM_UART_V1_COBS_BUFFER_MINIMUM];
static uint16_t transmitted_size[16];
static uint32_t transmitted_timeout[16];
static bool in_isr, in_task;
static TaskHandle_t created_task, current_task;
static struct fake_queue { UBaseType_t length, item_size, head, count; uint8_t *storage; } queues[3];
static unsigned queue_count;

void fake_task_enter_critical(void) { assert(!in_isr); }
void fake_task_exit_critical(void) { assert(!in_isr); }
UBaseType_t fake_task_enter_critical_from_isr(void) { assert(in_isr); return 0U; }
void fake_task_exit_critical_from_isr(UBaseType_t mask) { assert(in_isr); (void)mask; }
void fake_yield_from_isr(BaseType_t woken) { assert(in_isr); (void)woken; ++yields; }
TaskHandle_t xTaskCreateStatic(void (*entry)(void *), const char *name, uint32_t depth,
                               void *arg, UBaseType_t priority, StackType_t *stack,
                               StaticTask_t *control)
{
    assert(entry != NULL && strcmp(name, "UARTComm") == 0 && depth == 512U);
    assert(arg == NULL && priority == 24U && stack != NULL && control != NULL);
    created_task = (TaskHandle_t)control;
    return created_task;
}
void vTaskNotifyGiveFromISR(TaskHandle_t task, BaseType_t *woken) { assert(in_isr && task != NULL); *woken = pdTRUE; }
uint32_t ulTaskNotifyTake(BaseType_t clear, TickType_t ticks) { (void)clear; (void)ticks; return 0U; }
TaskHandle_t xTaskGetCurrentTaskHandle(void) { return current_task; }
QueueHandle_t xQueueCreateStatic(UBaseType_t length, UBaseType_t item_size, uint8_t *storage, StaticQueue_t *control)
{
    assert(length > 0U && item_size > 0U && storage != NULL && control != NULL && queue_count < 3U);
    struct fake_queue *q = &queues[queue_count++];
    q->length = length; q->item_size = item_size; q->storage = storage; q->head = 0U; q->count = 0U;
    return q;
}
static BaseType_t queue_send(QueueHandle_t q, const void *item)
{
    UBaseType_t tail;
    if (q->count == q->length) return pdFAIL;
    tail = (q->head + q->count) % q->length;
    memcpy(q->storage + tail * q->item_size, item, q->item_size); ++q->count; return pdPASS;
}
BaseType_t xQueueSend(QueueHandle_t q, const void *item, TickType_t wait)
{ assert(!in_isr && wait == 0U); return queue_send(q, item); }
BaseType_t xQueueSendFromISR(QueueHandle_t q, const void *item, BaseType_t *woken)
{ assert(in_isr); *woken = pdTRUE; return queue_send(q, item); }
BaseType_t xQueueReceive(QueueHandle_t q, void *item, TickType_t wait)
{
    assert(!in_isr && wait == 0U);
    if (q->count == 0U) return pdFAIL;
    memcpy(item, q->storage + q->head * q->item_size, q->item_size);
    q->head = (q->head + 1U) % q->length; --q->count; return pdPASS;
}
BaseType_t xQueueReset(QueueHandle_t q) { q->head = 0U; q->count = 0U; return pdPASS; }
uint32_t HAL_GetTick(void) { return fake_tick; }
HAL_StatusTypeDef HAL_UARTEx_ReceiveToIdle_IT(UART_HandleTypeDef *uart, uint8_t *data, uint16_t size)
{
    assert(!in_isr || uart != NULL);
    assert(uart != NULL && uart->Instance == USART6);
    active_rx = data; active_rx_capacity = size; ++receive_calls; return receive_status;
}
HAL_StatusTypeDef HAL_UART_AbortReceive(UART_HandleTypeDef *uart)
{ assert(!in_isr && uart != NULL); ++abort_calls; return HAL_OK; }
HAL_StatusTypeDef HAL_UART_Transmit(UART_HandleTypeDef *uart, uint8_t *data, uint16_t size, uint32_t timeout)
{
    assert(in_task && !in_isr && uart != NULL && transmit_calls < 16U);
    assert(size <= sizeof(transmitted[0]));
    memcpy(transmitted[transmit_calls], data, size); transmitted_size[transmit_calls] = size;
    transmitted_timeout[transmit_calls] = timeout; ++transmit_calls; return transmit_status;
}

static size_t make_config_frame(uint8_t *wire)
{
    mecanum_uart_v1_config_request_t config = {0};
    uint8_t payload[MECANUM_UART_V1_CONFIG_REQUEST_PAYLOAD_LENGTH];
    size_t size = 0U;
    config.config_sequence = 17U; config.reset_epoch = UINT32_MAX;
    memset(config.hardware_config_hash, 0xA5, sizeof(config.hardware_config_hash));
    assert(mecanum_uart_v1_serialize_config_request(&config, payload, sizeof(payload)) == MECANUM_UART_V1_OK);
    assert(mecanum_uart_v1_build_wire_frame(MECANUM_UART_V1_MESSAGE_CONFIG, payload, sizeof(payload),
                                            wire, MECANUM_UART_V1_COBS_BUFFER_MINIMUM, &size) == MECANUM_UART_V1_OK);
    return size;
}
static size_t make_custom_frame(uint16_t version, uint8_t type, const uint8_t *payload,
                                uint8_t payload_length, uint8_t *wire)
{
    uint8_t raw[MECANUM_UART_V1_RAW_BUFFER_MINIMUM];
    size_t raw_length = 4U + payload_length + 2U, encoded_length = 0U;
    uint16_t crc;
    raw[0] = (uint8_t)(version & 0xffU); raw[1] = (uint8_t)(version >> 8U);
    raw[2] = type; raw[3] = payload_length;
    if (payload_length != 0U) memcpy(&raw[4], payload, payload_length);
    crc = mecanum_uart_v1_crc16_ccitt_false(raw, 4U + payload_length);
    raw[4U + payload_length] = (uint8_t)(crc & 0xffU);
    raw[5U + payload_length] = (uint8_t)(crc >> 8U);
    assert(mecanum_uart_v1_cobs_encode(raw, raw_length, wire,
        MECANUM_UART_V1_COBS_BUFFER_MINIMUM - 1U, &encoded_length) == MECANUM_UART_V1_OK);
    wire[encoded_length++] = 0U;
    return encoded_length;
}
static UART_HandleTypeDef uart;
static void receive_chunk(const uint8_t *bytes, uint16_t size, uint32_t tick)
{
    memcpy(active_rx, bytes, size); fake_tick = tick;
    in_isr = true; HAL_UARTEx_RxEventCallback(&uart, size); in_isr = false;
}
static void service_task(void)
{
    current_task = created_task;
    communication_runtime_service_once();
    current_task = NULL;
}

static int run_fault_case(const char *name)
{
    uint8_t byte = 0x55U;
    uint8_t wire[MECANUM_UART_V1_COBS_BUFFER_MINIMUM];
    mecanum_uart_v1_config_status_t status = {0};
    unsigned i;
    if (strcmp(name, "rearm-busy") == 0) {
        receive_status = HAL_BUSY;
        receive_chunk(&byte, 1U, 1U);
    } else if (strcmp(name, "rearm-error") == 0) {
        receive_status = HAL_ERROR;
        receive_chunk(&byte, 1U, 1U);
    } else if (strcmp(name, "invalid-size") == 0) {
        in_isr = true; HAL_UARTEx_RxEventCallback(&uart, 129U); in_isr = false;
    } else if (strncmp(name, "rx-error-", 9U) == 0) {
        if (strcmp(name + 9U, "pe") == 0) uart.ErrorCode = HAL_UART_ERROR_PE;
        else if (strcmp(name + 9U, "fe") == 0) uart.ErrorCode = HAL_UART_ERROR_FE;
        else if (strcmp(name + 9U, "ne") == 0) uart.ErrorCode = HAL_UART_ERROR_NE;
        else uart.ErrorCode = HAL_UART_ERROR_ORE;
        in_isr = true; HAL_UARTEx_RxEventCallback(&uart, 8U); in_isr = false;
        assert(receive_calls == 1U); /* No rearm when RxEvent sees the pending error. */
        in_isr = true; HAL_UART_ErrorCallback(&uart); in_isr = false;
        uart.ErrorCode = HAL_UART_ERROR_NONE; /* HAL may clear it after the RX callback. */
    } else if (strcmp(name, "tx-timeout") == 0) {
        assert(communication_runtime_enqueue_config_status(&status));
        transmit_status = HAL_TIMEOUT;
        in_task = true; service_task(); in_task = false;
        assert(transmit_calls == 1U && transmitted_timeout[0] == 10U);
    } else if (strcmp(name, "tx-error") == 0) {
        assert(communication_runtime_enqueue_config_status(&status));
        transmit_status = HAL_ERROR;
        in_task = true; service_task(); in_task = false;
        assert(transmit_calls == 1U && transmitted_timeout[0] == 10U);
    } else if (strcmp(name, "tx-full") == 0) {
        for (i = 0U; i < COMMUNICATION_RUNTIME_TX_QUEUE_LENGTH; ++i)
            assert(communication_runtime_enqueue_config_status(&status));
        assert(!communication_runtime_enqueue_config_status(&status));
    } else if (strcmp(name, "rx-full") == 0) {
        for (i = 0U; i < COMMUNICATION_RUNTIME_RX_PENDING_CHUNKS; ++i) receive_chunk(&byte, 1U, i);
        assert(communication_runtime_is_usable());
        receive_chunk(&byte, 1U, 5U);
    } else if (strcmp(name, "candidate-full") == 0) {
        size_t frame_size = make_config_frame(wire), cursor = 0U;
        size_t total = frame_size * 9U;
        uint8_t stream[512];
        for (i = 0U; i < 9U; ++i) memcpy(&stream[i * frame_size], wire, frame_size);
        assert(total <= sizeof(stream));
        while (cursor < total) {
            uint16_t part = (uint16_t)(((total - cursor) > 128U) ? 128U : (total - cursor));
            receive_chunk(&stream[cursor], part, (uint32_t)cursor);
            cursor += part;
        }
        in_task = true; service_task(); in_task = false;
        assert(!communication_runtime_is_usable());
    } else return 2;
    assert(!communication_runtime_is_usable());
    in_task = true; service_task(); in_task = false;
    assert(abort_calls == 1U);
    in_task = true; service_task(); in_task = false;
    assert(abort_calls == 1U);
    assert(!communication_runtime_enqueue_config_status(&status));
    { communication_candidate_t candidate; assert(!communication_runtime_take_candidate(&candidate)); }
    assert(transmit_calls <= 1U); /* No retry or replay after transport failure. */
    return 0;
}

int main(int argc, char **argv)
{
    uint8_t wire[MECANUM_UART_V1_COBS_BUFFER_MINIMUM];
    size_t wire_size, i;
    communication_candidate_t candidate;
    mecanum_uart_v1_config_status_t status = {0};
    mecanum_uart_v1_telemetry_t telemetry = {0};
    UART_HandleTypeDef foreign = { &(USART_TypeDef){0}, 0U };
    uart.Instance = USART6; uart.ErrorCode = HAL_UART_ERROR_NONE;
    assert(!communication_runtime_start(&foreign));
    assert(!communication_runtime_is_usable());
    assert(communication_runtime_start(&uart));
    assert(receive_calls == 1U && active_rx_capacity == 128U && transmit_calls == 0U);
    if (argc == 2) return run_fault_case(argv[1]);

    wire_size = make_config_frame(wire);
    /* Bytewise fragmentation, preserving wraparound RX tick as a raw HAL tick. */
    for (i = 0U; i < wire_size; ++i) {
        receive_chunk(&wire[i], 1U, UINT32_MAX - 2U + (uint32_t)i);
        service_task();
    }
    service_task();
    assert(communication_runtime_take_candidate(&candidate));
    assert(candidate.type == COMMUNICATION_CANDIDATE_CONFIG_REQUEST);
    assert(candidate.value.config_request.config_sequence == 17U);
    assert(candidate.value.config_request.reset_epoch == UINT32_MAX);
    assert(candidate.rx_tick == (uint32_t)(UINT32_MAX - 2U + (uint32_t)wire_size - 1U));
    assert(transmit_calls == 0U); /* U3 accepts no CONFIG and emits no pre-owner response. */

    /* Full 128-byte callback carries two coalesced frames and copies before rearm. */
    {
        uint8_t full_chunk[128] = {0};
        size_t frame_size = make_config_frame(wire);
        assert(frame_size * 2U <= sizeof(full_chunk));
        memcpy(full_chunk, wire, frame_size);
        memcpy(&full_chunk[frame_size], wire, frame_size);
        receive_chunk(full_chunk, sizeof(full_chunk), 123U);
        memset(active_rx, 0xCC, active_rx_capacity);
        service_task();
        assert(communication_runtime_take_candidate(&candidate) && candidate.rx_tick == 123U);
        assert(communication_runtime_take_candidate(&candidate) && candidate.rx_tick == 123U);
    }

    /* Runtime validates protocol/type/length/direction; only request/command ingress is queued. */
    {
        uint8_t payload[MECANUM_UART_V1_CONFIG_REQUEST_PAYLOAD_LENGTH] = {0};
        size_t frame_size;
        frame_size = make_custom_frame(2U, MECANUM_UART_V1_MESSAGE_CONFIG, payload, 40U, wire);
        receive_chunk(wire, (uint16_t)frame_size, 125U); service_task();
        frame_size = make_custom_frame(1U, 0x7fU, payload, 0U, wire);
        receive_chunk(wire, (uint16_t)frame_size, 126U); service_task();
        frame_size = make_custom_frame(1U, MECANUM_UART_V1_MESSAGE_CONFIG, payload, 39U, wire);
        receive_chunk(wire, (uint16_t)frame_size, 127U); service_task();
        wire[0] = 0xffU; wire[1] = 0U;
        receive_chunk(wire, 2U, 128U); service_task();
        frame_size = make_custom_frame(1U, MECANUM_UART_V1_MESSAGE_TELEMETRY,
            (const uint8_t[65]){0}, 65U, wire);
        receive_chunk(wire, (uint16_t)frame_size, 129U); service_task();
        frame_size = make_custom_frame(1U, MECANUM_UART_V1_MESSAGE_CONFIG,
            (const uint8_t[50]){0}, 50U, wire);
        receive_chunk(wire, (uint16_t)frame_size, 130U); service_task();
        assert(!communication_runtime_take_candidate(&candidate));
    }

    /* Oversize bytes are discarded through the next delimiter, then parser resynchronizes. */
    {
        uint8_t overlong[128];
        size_t frame_size = make_config_frame(wire);
        memset(overlong, 0x55, sizeof(overlong));
        receive_chunk(overlong, sizeof(overlong), 131U); service_task();
        { uint8_t after[1U + MECANUM_UART_V1_COBS_BUFFER_MINIMUM];
          after[0] = 0U; memcpy(&after[1], wire, frame_size);
          receive_chunk(after, (uint16_t)(frame_size + 1U), 132U); service_task(); }
        assert(communication_runtime_take_candidate(&candidate));
    }

    /* Sequence zero remains a typed transport candidate; U4 owns semantic rejection. */
    {
        mecanum_uart_v1_command_t command = {0U, 9U, 1.0F, 0.0F, -1.0F};
        uint8_t command_payload[MECANUM_UART_V1_COMMAND_PAYLOAD_LENGTH];
        size_t command_wire_length;
        assert(mecanum_uart_v1_serialize_command(&command, command_payload, sizeof(command_payload)) == MECANUM_UART_V1_OK);
        assert(mecanum_uart_v1_build_wire_frame(MECANUM_UART_V1_MESSAGE_COMMAND, command_payload,
            sizeof(command_payload), wire, sizeof(wire), &command_wire_length) == MECANUM_UART_V1_OK);
        receive_chunk(wire, (uint16_t)command_wire_length, 133U); service_task();
        assert(communication_runtime_take_candidate(&candidate));
        assert(candidate.type == COMMUNICATION_CANDIDATE_COMMAND);
        assert(candidate.value.command.command_sequence == 0U);
    }

    /* CRC/COBS rejection does not poison the next delimited valid frame. */
    {
        uint8_t stream[2U * MECANUM_UART_V1_COBS_BUFFER_MINIMUM];
        size_t frame_size = make_config_frame(wire);
        memcpy(stream, wire, frame_size);
        stream[2] ^= 0x01U;
        memcpy(&stream[frame_size], wire, frame_size);
        receive_chunk(stream, (uint16_t)(2U * frame_size), 124U);
        service_task();
        assert(communication_runtime_take_candidate(&candidate));
        assert(!communication_runtime_take_candidate(&candidate));
    }

    /* Foreign callbacks do not affect the bound channel. */
    in_isr = true; HAL_UARTEx_RxEventCallback(&foreign, 1U); in_isr = false;
    assert(communication_runtime_is_usable());

    /* Outbound structs are copied by value and serialized by the sole task path. */
    status.config_sequence = 8U; status.reset_epoch = 9U; status.mcu_boot_id = 10U;
    status.config_status = MECANUM_UART_V1_CONFIG_ACCEPTED;
    assert(communication_runtime_enqueue_config_status(&status));
    status.config_sequence = 99U;
    telemetry.telemetry_sequence = 1U; telemetry.mcu_boot_id = 10U; telemetry.reset_epoch = 9U;
    telemetry.estop_aux_active = 1U;
    assert(communication_runtime_enqueue_telemetry(&telemetry));
    communication_runtime_service_once(); /* Non-owner caller cannot service or transmit. */
    assert(transmit_calls == 0U);
    memset(&telemetry, 0, sizeof(telemetry));
    in_task = true; service_task(); service_task(); in_task = false;
    assert(transmit_calls == 2U && transmitted_timeout[0] == 10U && transmitted_timeout[1] == 10U);
    { mecanum_uart_v1_frame_t decoded;
      assert(transmitted[0][transmitted_size[0] - 1U] == 0U);
      assert(mecanum_uart_v1_decode_wire_frame(transmitted[0], transmitted_size[0], &decoded) == MECANUM_UART_V1_OK);
      assert(decoded.message_type == MECANUM_UART_V1_MESSAGE_CONFIG);
      assert(mecanum_uart_v1_parse_config_status(decoded.payload, decoded.payload_length, &status) == MECANUM_UART_V1_OK);
      assert(status.config_sequence == 8U);
      assert(mecanum_uart_v1_decode_wire_frame(transmitted[1], transmitted_size[1], &decoded) == MECANUM_UART_V1_OK);
      assert(decoded.message_type == MECANUM_UART_V1_MESSAGE_TELEMETRY); }

    /* Four pending callback chunks are accepted; the fifth latches transport failure. */
    for (i = 0U; i < 4U; ++i) receive_chunk(wire, 1U, (uint32_t)i);
    assert(communication_runtime_is_usable());
    receive_chunk(wire, 1U, 5U);
    assert(!communication_runtime_is_usable());
    in_task = true; service_task(); in_task = false;
    assert(abort_calls == 1U);
    assert(!communication_runtime_take_candidate(&candidate));
    assert(!communication_runtime_enqueue_config_status(&status));
    assert(transmit_calls == 2U);
    printf("runtime fake-HAL/RTOS assertions passed: rx=%u tx=%u yields=%u\n", receive_calls, transmit_calls, yields);
    return 0;
}
