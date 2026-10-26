#include "communication_runtime.h"
#include "control_safety_runtime.h"
#include "FreeRTOS.h"
#include "queue.h"
#include "task.h"

#include <assert.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

USART_TypeDef fake_usart6;
static UART_HandleTypeDef uart;
static uint32_t fake_tick = UINT32_MAX - 3U;
static HAL_StatusTypeDef receive_status = HAL_OK, transmit_status = HAL_OK;
static uint8_t *active_rx;
static uint16_t active_rx_capacity;
static unsigned receive_calls, transmit_calls, abort_calls, yields;
static uint8_t transmitted[16][MECANUM_UART_V1_COBS_BUFFER_MINIMUM];
static uint16_t transmitted_size[16];
static uint32_t transmitted_timeout[16];
static bool in_isr, in_task;
static TaskHandle_t created_task, control_task, current_task;
static unsigned critical_api_calls, queue_api_calls, task_api_calls, queue_create_calls, task_create_calls;
typedef enum { INJECT_NONE, INJECT_CANDIDATE_RECEIVE, INJECT_TX_RECEIVE,
               INJECT_STATUS_SEND, INJECT_TELEMETRY_SEND } inject_target_t;
static inject_target_t inject_fault_after_dequeue, inject_fault_after_send;
static bool inject_fault_during_transmit;
static bool inject_fault_during_rearm;
static struct fake_queue { UBaseType_t length, item_size, head, count; uint8_t *storage; } queues[3];
static struct fake_queue *candidate_queue_fake, *tx_queue_fake;
static unsigned queue_count;

uint32_t __get_IPSR(void) { return in_isr ? 16U : 0U; }
void fake_task_enter_critical(void) { assert(!in_isr); ++critical_api_calls; }
void fake_task_exit_critical(void) { assert(!in_isr); ++critical_api_calls; }
UBaseType_t fake_task_enter_critical_from_isr(void) { assert(in_isr); return 0U; }
void fake_task_exit_critical_from_isr(UBaseType_t mask) { assert(in_isr); (void)mask; }
void fake_yield_from_isr(BaseType_t woken) { assert(in_isr); (void)woken; ++yields; }
static void inject_uart_fault(void)
{
    uart.ErrorCode = HAL_UART_ERROR_ORE;
    in_isr = true; HAL_UART_ErrorCallback(&uart); in_isr = false;
    uart.ErrorCode = HAL_UART_ERROR_NONE;
}
TaskHandle_t xTaskCreateStatic(void (*entry)(void *), const char *name, uint32_t depth,
                               void *arg, UBaseType_t priority, StackType_t *stack,
                               StaticTask_t *control)
{
    assert(!in_isr); ++task_create_calls;
    assert(entry != NULL && depth == 512U);
    assert(arg == NULL && stack != NULL && control != NULL);
    if (strcmp(name, "UARTComm") == 0) {
        assert(priority == 24U);
        created_task = (TaskHandle_t)control;
        return created_task;
    }
    assert(strcmp(name, "CtrlSafe") == 0 && priority == 40U);
    control_task = (TaskHandle_t)control;
    return control_task;
}
void vTaskNotifyGiveFromISR(TaskHandle_t task, BaseType_t *woken) { assert(in_isr && task != NULL); *woken = pdTRUE; }
uint32_t ulTaskNotifyTake(BaseType_t clear, TickType_t ticks) { (void)clear; (void)ticks; return 0U; }
TaskHandle_t xTaskGetCurrentTaskHandle(void) { assert(!in_isr); ++task_api_calls; return current_task; }
TickType_t xTaskGetTickCount(void) { assert(!in_isr); return fake_tick; }
void vTaskDelayUntil(TickType_t *last_wake, TickType_t increment)
{ assert(!in_isr && last_wake != NULL); *last_wake += increment; }
QueueHandle_t xQueueCreateStatic(UBaseType_t length, UBaseType_t item_size, uint8_t *storage, StaticQueue_t *control)
{
    assert(!in_isr); ++queue_create_calls;
    assert(length > 0U && item_size > 0U && storage != NULL && control != NULL && queue_count < 3U);
    struct fake_queue *q = &queues[queue_count++];
    if (queue_count == 2U) candidate_queue_fake = q;
    if (queue_count == 3U) tx_queue_fake = q;
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
{
    BaseType_t result;
    assert(!in_isr && wait == 0U); ++queue_api_calls;
    result = queue_send(q, item);
    if ((result == pdPASS) && (q == tx_queue_fake)
        && ((inject_fault_after_send == INJECT_STATUS_SEND)
            || (inject_fault_after_send == INJECT_TELEMETRY_SEND))) {
        inject_fault_after_send = INJECT_NONE;
        inject_uart_fault();
    }
    return result;
}
BaseType_t xQueueSendFromISR(QueueHandle_t q, const void *item, BaseType_t *woken)
{ assert(in_isr); *woken = pdTRUE; return queue_send(q, item); }
BaseType_t xQueueReceive(QueueHandle_t q, void *item, TickType_t wait)
{
    assert(!in_isr && wait == 0U); ++queue_api_calls;
    if (q->count == 0U) return pdFAIL;
    memcpy(item, q->storage + q->head * q->item_size, q->item_size);
    q->head = (q->head + 1U) % q->length; --q->count;
    if (((inject_fault_after_dequeue == INJECT_CANDIDATE_RECEIVE) && (q == candidate_queue_fake))
        || ((inject_fault_after_dequeue == INJECT_TX_RECEIVE) && (q == tx_queue_fake))) {
        inject_fault_after_dequeue = INJECT_NONE;
        inject_uart_fault();
    }
    return pdPASS;
}
BaseType_t xQueueReset(QueueHandle_t q) { assert(!in_isr); ++queue_api_calls; q->head = 0U; q->count = 0U; return pdPASS; }
uint32_t HAL_GetTick(void) { return fake_tick; }
HAL_StatusTypeDef HAL_UARTEx_ReceiveToIdle_IT(UART_HandleTypeDef *uart, uint8_t *data, uint16_t size)
{
    assert(!in_isr || uart != NULL);
    assert(uart != NULL && uart->Instance == USART6);
    active_rx = data; active_rx_capacity = size; ++receive_calls;
    if (inject_fault_during_rearm) {
        inject_fault_during_rearm = false;
        uart->ErrorCode = HAL_UART_ERROR_ORE;
        in_isr = true; HAL_UART_ErrorCallback(uart); in_isr = false;
        uart->ErrorCode = HAL_UART_ERROR_NONE;
    }
    return receive_status;
}
HAL_StatusTypeDef HAL_UART_AbortReceive(UART_HandleTypeDef *uart)
{ assert(!in_isr && uart != NULL); ++abort_calls; return HAL_OK; }
HAL_StatusTypeDef HAL_UART_Transmit(UART_HandleTypeDef *uart, uint8_t *data, uint16_t size, uint32_t timeout)
{
    assert(in_task && !in_isr && uart != NULL && transmit_calls < 16U);
    assert(size <= sizeof(transmitted[0]));
    memcpy(transmitted[transmit_calls], data, size); transmitted_size[transmit_calls] = size;
    transmitted_timeout[transmit_calls] = timeout; ++transmit_calls;
    if (inject_fault_during_transmit) {
        inject_fault_during_transmit = false;
        uart->ErrorCode = HAL_UART_ERROR_ORE;
        in_isr = true; HAL_UART_ErrorCallback(uart); in_isr = false;
        uart->ErrorCode = HAL_UART_ERROR_NONE;
    }
    return transmit_status;
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

static void service_control_task(void)
{
    current_task = control_task;
    control_safety_runtime_service_once();
    current_task = NULL;
}

static size_t make_command_frame(uint32_t sequence, uint32_t epoch, uint8_t *wire)
{
    mecanum_uart_v1_command_t command = {sequence, epoch, 0.25F, -0.5F, 0.75F};
    uint8_t payload[MECANUM_UART_V1_COMMAND_PAYLOAD_LENGTH];
    size_t size = 0U;
    assert(mecanum_uart_v1_serialize_command(&command, payload, sizeof(payload)) == MECANUM_UART_V1_OK);
    assert(mecanum_uart_v1_build_wire_frame(MECANUM_UART_V1_MESSAGE_COMMAND, payload,
        sizeof(payload), wire, MECANUM_UART_V1_COBS_BUFFER_MINIMUM, &size) == MECANUM_UART_V1_OK);
    return size;
}

static int run_control_safety_case(void)
{
    uint8_t hash[32], wire[MECANUM_UART_V1_COBS_BUFFER_MINIMUM], byte = 0x55U;
    size_t size;
    control_safety_snapshot_t snapshot;
    mecanum_uart_v1_frame_t frame;
    mecanum_uart_v1_config_status_t status;
    unsigned reads;
    memset(hash, 0xA5, sizeof(hash));
    uart.Instance = USART6; uart.ErrorCode = HAL_UART_ERROR_NONE;
    assert(communication_runtime_prepare(&uart));
    assert(control_safety_runtime_start(hash, true, UINT64_C(123)));
    assert(communication_runtime_arm_rx()); /* Tạo owner/task/queue trước khi arm RX. */

    size = make_config_frame(wire);
    receive_chunk(wire, (uint16_t)size, 100U);
    in_task = true; service_task(); in_task = false;
    service_control_task();
    assert(control_safety_runtime_copy_snapshot(&snapshot));
    assert(snapshot.configured && snapshot.telemetry_allowed && !snapshot.motor_enabled);
    assert(snapshot.state == CONTROL_SAFETY_SESSION_CONFIG_ACCEPTED_MOTOR_DISABLED);
    in_task = true; service_task(); in_task = false;
    assert(transmit_calls == 1U);
    assert(mecanum_uart_v1_decode_wire_frame(transmitted[0], transmitted_size[0], &frame) == MECANUM_UART_V1_OK);
    assert(mecanum_uart_v1_parse_config_status(frame.payload, frame.payload_length, &status) == MECANUM_UART_V1_OK);
    assert(status.config_status == MECANUM_UART_V1_CONFIG_ACCEPTED && status.mcu_boot_id == 123U);
    assert(status.reset_epoch == UINT32_MAX && status.config_sequence == 17U);

    /* Bỏ command cũ trong queue, không đổi accepted history. */
    size = make_command_frame(1U, UINT32_MAX, wire);
    receive_chunk(wire, (uint16_t)size, 110U);
    in_task = true; service_task(); in_task = false;
    fake_tick = 310U;
    service_control_task();
    assert(control_safety_runtime_copy_snapshot(&snapshot));
    assert(snapshot.last_accepted_command_sequence == 0U);
    assert((snapshot.mcu_fault_bits & MECANUM_FAULT_MCU_COMMAND_INVALID) != 0U);

    /* Từ chối sequence 0; command dương mới xóa invalid indication. */
    size = make_command_frame(0U, UINT32_MAX, wire);
    receive_chunk(wire, (uint16_t)size, 311U);
    in_task = true; service_task(); in_task = false;
    fake_tick = 312U; service_control_task();
    assert(control_safety_runtime_copy_snapshot(&snapshot));
    assert(snapshot.last_accepted_command_sequence == 0U);
    assert((snapshot.mcu_fault_bits & MECANUM_FAULT_MCU_COMMAND_INVALID) != 0U);
    size = make_command_frame(1U, UINT32_MAX, wire);
    receive_chunk(wire, (uint16_t)size, 313U);
    in_task = true; service_task(); in_task = false;
    fake_tick = 314U; service_control_task();
    assert(control_safety_runtime_copy_snapshot(&snapshot));
    assert(snapshot.last_accepted_command_sequence == 1U);
    assert((snapshot.mcu_fault_bits & MECANUM_FAULT_MCU_COMMAND_INVALID) == 0U);

    /* Watchdog timeout giữ configured session và accepted history. */
    fake_tick = 512U; service_control_task();
    assert(control_safety_runtime_copy_snapshot(&snapshot));
    assert(snapshot.state == CONTROL_SAFETY_SESSION_COMMAND_ACTIVE);
    fake_tick = 513U; service_control_task();
    assert(control_safety_runtime_copy_snapshot(&snapshot));
    assert(snapshot.state == CONTROL_SAFETY_SESSION_SAFE_STOP);
    assert(snapshot.configured && snapshot.telemetry_allowed);
    assert(snapshot.last_accepted_command_sequence == 1U);
    assert((snapshot.mcu_fault_bits & MECANUM_FAULT_MCU_COMMAND_TIMEOUT) != 0U);

    /* CONFIG hợp lệ cùng epoch là cách duy nhất thoát watchdog SAFE_STOP. */
    size = make_config_frame(wire);
    receive_chunk(wire, (uint16_t)size, 515U);
    in_task = true; service_task(); in_task = false;
    fake_tick = 516U; service_control_task();
    assert(control_safety_runtime_copy_snapshot(&snapshot));
    assert(snapshot.state == CONTROL_SAFETY_SESSION_CONFIG_ACCEPTED_MOTOR_DISABLED);
    assert(snapshot.last_accepted_command_sequence == 0U && snapshot.mcu_fault_bits == 0U);

    /* Recovery UART giữ boot ID nhưng vô hiệu session và bỏ công việc đang chờ. */
    for (unsigned i = 0U; i < COMMUNICATION_RUNTIME_RX_PENDING_CHUNKS; ++i) receive_chunk(&byte, 1U, 600U + i);
    receive_chunk(&byte, 1U, 605U);
    fake_tick = 700U; service_control_task();
    assert(control_safety_runtime_copy_snapshot(&snapshot));
    assert(snapshot.state == CONTROL_SAFETY_SESSION_SAFE_STOP && !snapshot.configured);
    assert(!snapshot.telemetry_allowed && snapshot.mcu_boot_id == 123U);
    assert((snapshot.mcu_fault_bits & MECANUM_FAULT_TRANSPORT) != 0U);
    inject_fault_during_rearm = true;
    in_task = true; service_task(); in_task = false;
    assert(!communication_runtime_is_usable()); /* HAL_OK không xóa được lỗi ISR chen vào. */
    reads = receive_calls;
    fake_tick = 1699U; in_task = true; service_task(); in_task = false;
    assert(receive_calls == reads); /* giới hạn lần thử lại tối thiểu một giây */
    fake_tick = 1700U; in_task = true; service_task(); in_task = false;
    assert(communication_runtime_is_usable());
    assert(control_safety_runtime_copy_snapshot(&snapshot));
    assert(!snapshot.configured && !snapshot.telemetry_allowed && snapshot.mcu_boot_id == 123U);
    size = make_command_frame(2U, UINT32_MAX, wire);
    receive_chunk(wire, (uint16_t)size, 1701U);
    in_task = true; service_task(); in_task = false;
    fake_tick = 1702U; service_control_task();
    assert(control_safety_runtime_copy_snapshot(&snapshot));
    assert(!snapshot.configured && snapshot.last_accepted_command_sequence == 0U);
    return 0;
}

static int run_interop_peer(const char *hash_hex, const char *boot_text)
{
    char line[256];
    uint8_t hash[32];
    uint64_t boot_id = (uint64_t)strtoull(boot_text, NULL, 10);
    unsigned i;
    if (strlen(hash_hex) != 64U || boot_id == 0U) return 3;
    for (i = 0U; i < 32U; ++i) {
        unsigned value;
        if (sscanf(&hash_hex[i * 2U], "%2x", &value) != 1) return 3;
        hash[i] = (uint8_t)value;
    }
    uart.Instance = USART6; uart.ErrorCode = HAL_UART_ERROR_NONE;
    if (!communication_runtime_prepare(&uart)
        || !control_safety_runtime_start(hash, true, boot_id)
        || !communication_runtime_arm_rx()) return 4;
    puts("READY"); fflush(stdout);
    while (fgets(line, sizeof(line), stdin) != NULL) {
        unsigned long tick;
        char *hex, *end;
        uint8_t bytes[MECANUM_UART_V1_COBS_BUFFER_MINIMUM];
        size_t count = 0U, before_tx = transmit_calls;
        control_safety_snapshot_t snapshot;
        if (sscanf(line, "%lu", &tick) != 1) return 5;
        hex = strchr(line, ' ');
        if (hex == NULL) return 5;
        ++hex;
        end = strpbrk(hex, "\r\n"); if (end != NULL) *end = '\0';
        if ((strlen(hex) % 2U) != 0U || strlen(hex) > sizeof(bytes) * 2U) return 5;
        while (hex[count * 2U] != '\0') {
            unsigned value;
            if (sscanf(&hex[count * 2U], "%2x", &value) != 1) return 5;
            bytes[count++] = (uint8_t)value;
        }
        if (count == 0U) return 5;
        fake_tick = (uint32_t)tick;
        receive_chunk(bytes, (uint16_t)count, fake_tick);
        in_task = true; service_task(); in_task = false;
        service_control_task();
        in_task = true; service_task(); in_task = false;
        if (!control_safety_runtime_copy_snapshot(&snapshot)) return 6;
        printf("RESULT boot=%" PRIu64 " epoch=%" PRIu32 " accepted=%" PRIu32
               " state=%u faults=%" PRIu32 " configured=%u telemetry=%u tx=",
               snapshot.mcu_boot_id, snapshot.reset_epoch,
               snapshot.last_accepted_command_sequence, (unsigned)snapshot.state,
               snapshot.mcu_fault_bits, snapshot.configured ? 1U : 0U,
               snapshot.telemetry_allowed ? 1U : 0U);
        if (transmit_calls == before_tx) puts("-");
        else {
            for (i = 0U; i < transmitted_size[before_tx]; ++i)
                printf("%02x", transmitted[before_tx][i]);
            putchar('\n');
        }
        fflush(stdout);
    }
    return 0;
}

static int run_fault_case(const char *name)
{
    uint8_t byte = 0x55U;
    uint8_t wire[MECANUM_UART_V1_COBS_BUFFER_MINIMUM];
    communication_candidate_t candidate;
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
    } else if (strcmp(name, "fault-after-tx-dequeue") == 0) {
        assert(communication_runtime_enqueue_config_status(&status));
        inject_fault_after_dequeue = INJECT_TX_RECEIVE;
        in_task = true; service_task(); in_task = false;
        assert(!communication_runtime_is_usable());
        assert(transmit_calls == 0U);
        in_task = true; service_task(); in_task = false;
        assert(abort_calls == 1U && transmit_calls == 0U);
    } else if (strcmp(name, "fault-after-candidate-dequeue") == 0) {
        size_t frame_size = make_config_frame(wire);
        candidate.type = COMMUNICATION_CANDIDATE_COMMAND;
        receive_chunk(wire, (uint16_t)frame_size, 7U);
        in_task = true; service_task(); in_task = false;
        inject_fault_after_dequeue = INJECT_CANDIDATE_RECEIVE;
        assert(!communication_runtime_take_candidate(&candidate));
        assert(candidate.type == COMMUNICATION_CANDIDATE_COMMAND);
        assert(!communication_runtime_is_usable());
        in_task = true; service_task(); in_task = false;
        assert(abort_calls == 1U);
    } else if (strcmp(name, "fault-during-tx") == 0) {
        assert(communication_runtime_enqueue_config_status(&status));
        assert(communication_runtime_enqueue_telemetry(&(mecanum_uart_v1_telemetry_t){0}));
        inject_fault_during_transmit = true;
        in_task = true; service_task(); in_task = false;
        assert(transmit_calls == 1U && !communication_runtime_is_usable());
        in_task = true; service_task(); in_task = false;
        assert(abort_calls == 1U && transmit_calls == 1U);
    } else if (strcmp(name, "fault-after-status-enqueue") == 0) {
        inject_fault_after_send = INJECT_STATUS_SEND;
        assert(!communication_runtime_enqueue_config_status(&status));
        assert(!communication_runtime_is_usable());
        in_task = true; service_task(); in_task = false;
        assert(abort_calls == 1U && transmit_calls == 0U);
    } else if (strcmp(name, "fault-after-telemetry-enqueue") == 0) {
        inject_fault_after_send = INJECT_TELEMETRY_SEND;
        assert(!communication_runtime_enqueue_telemetry(&(mecanum_uart_v1_telemetry_t){0}));
        assert(!communication_runtime_is_usable());
        in_task = true; service_task(); in_task = false;
        assert(abort_calls == 1U && transmit_calls == 0U);
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
    if ((argc == 4) && (strcmp(argv[1], "--interop") == 0))
        return run_interop_peer(argv[2], argv[3]);
    if ((argc == 2) && (strcmp(argv[1], "u4-session-runtime") == 0))
        return run_control_safety_case();
    if ((argc == 2) && (strcmp(argv[1], "isr-public-apis") == 0)) {
        in_isr = true;
        assert(!communication_runtime_start(&uart));
        in_isr = false;
        assert(queue_create_calls == 0U && task_create_calls == 0U);
    }
    assert(!communication_runtime_start(&foreign));
    assert(!communication_runtime_is_usable());
    assert(communication_runtime_start(&uart));
    assert(receive_calls == 1U && active_rx_capacity == 128U && transmit_calls == 0U);
    if ((argc == 2) && (strcmp(argv[1], "isr-public-apis") == 0)) {
        communication_candidate_t out = {0};
        mecanum_uart_v1_config_status_t out_status = {0};
        mecanum_uart_v1_telemetry_t out_telemetry = {0};
        unsigned critical_before = critical_api_calls, queue_before = queue_api_calls;
        unsigned task_before = task_api_calls, create_before = queue_create_calls;
        current_task = created_task; /* Same owner handle remains visible in interrupt context. */
        in_isr = true;
        assert(!communication_runtime_start(&uart));
        assert(!communication_runtime_is_usable());
        assert(!communication_runtime_take_candidate(&out));
        assert(!communication_runtime_enqueue_config_status(&out_status));
        assert(!communication_runtime_enqueue_telemetry(&out_telemetry));
        communication_runtime_service_once();
        in_isr = false;
        assert(critical_api_calls == critical_before && queue_api_calls == queue_before);
        assert(task_api_calls == task_before && queue_create_calls == create_before);
        assert(transmit_calls == 0U && communication_runtime_is_usable());
        wire_size = make_config_frame(wire);
        receive_chunk(wire, (uint16_t)wire_size, 21U);
        service_task();
        assert(communication_runtime_take_candidate(&candidate));
        return 0;
    }
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
