#include "communication_runtime.h"

#include "FreeRTOS.h"
#include "queue.h"
#include "task.h"

#include <string.h>

typedef struct {
    uint16_t size;
    uint32_t tick;
    uint8_t bytes[COMMUNICATION_RUNTIME_RX_CHUNK_BYTES];
} rx_chunk_t;

typedef enum { TX_CONFIG_STATUS = 1, TX_TELEMETRY = 2 } tx_type_t;
typedef struct {
    tx_type_t type;
    union {
        mecanum_uart_v1_config_status_t config_status;
        mecanum_uart_v1_telemetry_t telemetry;
    } value;
} tx_item_t;

static UART_HandleTypeDef *bound_uart;
static uint8_t hal_rx_buffer[COMMUNICATION_RUNTIME_RX_CHUNK_BYTES];
static StaticQueue_t rx_queue_control, candidate_queue_control, tx_queue_control;
static uint8_t rx_queue_storage[COMMUNICATION_RUNTIME_RX_PENDING_CHUNKS * sizeof(rx_chunk_t)];
static uint8_t candidate_queue_storage[COMMUNICATION_RUNTIME_CANDIDATE_QUEUE_LENGTH * sizeof(communication_candidate_t)];
static uint8_t tx_queue_storage[COMMUNICATION_RUNTIME_TX_QUEUE_LENGTH * sizeof(tx_item_t)];
static QueueHandle_t rx_queue, candidate_queue, tx_queue;
static StaticTask_t task_control;
static StackType_t task_stack[COMMUNICATION_RUNTIME_TASK_STACK_WORDS];
static TaskHandle_t communication_task;
static bool started;
static bool rx_armed;
static bool transport_fault;
static bool fault_cleanup_done;
static bool recovery_requested;
static bool recovery_attempted;
static uint32_t recovery_last_attempt;
static uint32_t fault_generation;
static uint8_t frame_accumulator[MECANUM_UART_V1_COBS_BUFFER_MINIMUM];
static size_t frame_length;
static bool discard_until_delimiter;

static void communication_task_entry(void *argument);

static bool fault_is_latched(void)
{
    bool value;
    taskENTER_CRITICAL();
    value = transport_fault;
    taskEXIT_CRITICAL();
    return value;
}

static void latch_fault_task(void)
{
    taskENTER_CRITICAL();
    transport_fault = true;
    ++fault_generation;
    taskEXIT_CRITICAL();
}

static void latch_fault_isr(BaseType_t *higher_priority_task_woken)
{
    UBaseType_t mask = taskENTER_CRITICAL_FROM_ISR();
    transport_fault = true;
    ++fault_generation;
    taskEXIT_CRITICAL_FROM_ISR(mask);
    if (communication_task != NULL) {
        vTaskNotifyGiveFromISR(communication_task, higher_priority_task_woken);
    }
}

static bool fault_is_latched_isr(void)
{
    bool value;
    UBaseType_t mask = taskENTER_CRITICAL_FROM_ISR();
    value = transport_fault;
    taskEXIT_CRITICAL_FROM_ISR(mask);
    return value;
}

bool communication_runtime_is_usable(void)
{
    bool armed;
    if (__get_IPSR() != 0U) return false;
    taskENTER_CRITICAL();
    armed = rx_armed;
    taskEXIT_CRITICAL();
    return started && armed && !fault_is_latched();
}

bool communication_runtime_prepare(UART_HandleTypeDef *uart)
{
    if (__get_IPSR() != 0U) return false;
    if ((uart == NULL) || (uart->Instance != USART6) || started) {
        return false;
    }
    rx_queue = xQueueCreateStatic(COMMUNICATION_RUNTIME_RX_PENDING_CHUNKS, sizeof(rx_chunk_t),
                                  rx_queue_storage, &rx_queue_control);
    candidate_queue = xQueueCreateStatic(COMMUNICATION_RUNTIME_CANDIDATE_QUEUE_LENGTH,
                                         sizeof(communication_candidate_t), candidate_queue_storage,
                                         &candidate_queue_control);
    tx_queue = xQueueCreateStatic(COMMUNICATION_RUNTIME_TX_QUEUE_LENGTH, sizeof(tx_item_t),
                                  tx_queue_storage, &tx_queue_control);
    if ((rx_queue == NULL) || (candidate_queue == NULL) || (tx_queue == NULL)) {
        return false;
    }
    bound_uart = uart;
    started = true;
    communication_task = xTaskCreateStatic(communication_task_entry, "UARTComm",
                                            COMMUNICATION_RUNTIME_TASK_STACK_WORDS, NULL,
                                            COMMUNICATION_RUNTIME_TASK_PRIORITY, task_stack,
                                            &task_control);
    if (communication_task == NULL) {
        started = false;
        return false;
    }
    return true;
}

bool communication_runtime_arm_rx(void)
{
    if ((__get_IPSR() != 0U) || !started || rx_armed || fault_is_latched()) return false;
    if (HAL_UARTEx_ReceiveToIdle_IT(bound_uart, hal_rx_buffer,
                                    COMMUNICATION_RUNTIME_RX_CHUNK_BYTES) != HAL_OK) {
        latch_fault_task();
        return false;
    }
    taskENTER_CRITICAL();
    rx_armed = true;
    taskEXIT_CRITICAL();
    return true;
}

bool communication_runtime_start(UART_HandleTypeDef *uart)
{
    return communication_runtime_prepare(uart) && communication_runtime_arm_rx();
}

bool communication_runtime_request_recovery(void)
{
    if ((__get_IPSR() != 0U) || !started) return false;
    taskENTER_CRITICAL();
    recovery_requested = true;
    taskEXIT_CRITICAL();
    return true;
}

bool communication_runtime_recovery_complete(void)
{
    bool armed;
    if (__get_IPSR() != 0U) return false;
    taskENTER_CRITICAL();
    armed = rx_armed;
    taskEXIT_CRITICAL();
    return started && armed && !fault_is_latched();
}

bool communication_runtime_is_started(void)
{
    if (__get_IPSR() != 0U) return false;
    return started;
}

bool communication_runtime_is_faulted(void)
{
    if (__get_IPSR() != 0U) return false;
    return fault_is_latched();
}

bool communication_runtime_take_candidate(communication_candidate_t *candidate)
{
    communication_candidate_t pending;
    if ((__get_IPSR() != 0U) || (candidate == NULL) || !communication_runtime_is_usable()) return false;
    if (xQueueReceive(candidate_queue, &pending, 0U) != pdPASS) return false;
    if (!communication_runtime_is_usable()) return false;
    *candidate = pending;
    return true;
}

bool communication_runtime_enqueue_config_status(const mecanum_uart_v1_config_status_t *status)
{
    tx_item_t item;
    if (__get_IPSR() != 0U) return false;
    if ((status == NULL) || !communication_runtime_is_usable()) return false;
    item.type = TX_CONFIG_STATUS;
    item.value.config_status = *status;
    if (xQueueSend(tx_queue, &item, 0U) != pdPASS) { latch_fault_task(); return false; }
    if (!communication_runtime_is_usable()) return false;
    return true;
}

bool communication_runtime_enqueue_telemetry(const mecanum_uart_v1_telemetry_t *telemetry)
{
    tx_item_t item;
    if (__get_IPSR() != 0U) return false;
    if ((telemetry == NULL) || !communication_runtime_is_usable()) return false;
    item.type = TX_TELEMETRY;
    item.value.telemetry = *telemetry;
    if (xQueueSend(tx_queue, &item, 0U) != pdPASS) { latch_fault_task(); return false; }
    if (!communication_runtime_is_usable()) return false;
    return true;
}

static void process_frame(uint32_t tick)
{
    mecanum_uart_v1_frame_t decoded;
    communication_candidate_t candidate;
    frame_accumulator[frame_length] = MECANUM_UART_V1_WIRE_DELIMITER;
    if (mecanum_uart_v1_decode_wire_frame(frame_accumulator, frame_length + 1U, &decoded) != MECANUM_UART_V1_OK) return;
    candidate.rx_tick = tick;
    if ((decoded.message_type == MECANUM_UART_V1_MESSAGE_CONFIG)
        && (decoded.payload_length == MECANUM_UART_V1_CONFIG_REQUEST_PAYLOAD_LENGTH)) {
        candidate.type = COMMUNICATION_CANDIDATE_CONFIG_REQUEST;
        if (mecanum_uart_v1_parse_config_request(decoded.payload, decoded.payload_length,
                                                 &candidate.value.config_request) != MECANUM_UART_V1_OK) return;
    } else if ((decoded.message_type == MECANUM_UART_V1_MESSAGE_COMMAND)
               && (decoded.payload_length == MECANUM_UART_V1_COMMAND_PAYLOAD_LENGTH)) {
        candidate.type = COMMUNICATION_CANDIDATE_COMMAND;
        if (mecanum_uart_v1_parse_command(decoded.payload, decoded.payload_length,
                                         &candidate.value.command) != MECANUM_UART_V1_OK) return;
    } else {
        return;
    }
    if (xQueueSend(candidate_queue, &candidate, 0U) != pdPASS) latch_fault_task();
}

static void process_chunk(const rx_chunk_t *chunk)
{
    uint16_t i;
    for (i = 0U; i < chunk->size && !fault_is_latched(); ++i) {
        uint8_t byte = chunk->bytes[i];
        if (byte == MECANUM_UART_V1_WIRE_DELIMITER) {
            if (!discard_until_delimiter && frame_length != 0U) process_frame(chunk->tick);
            frame_length = 0U;
            discard_until_delimiter = false;
        } else if (!discard_until_delimiter) {
            if (frame_length >= (MECANUM_UART_V1_COBS_BUFFER_MINIMUM - 1U)) {
                frame_length = 0U;
                discard_until_delimiter = true;
            } else {
                frame_accumulator[frame_length++] = byte;
            }
        }
    }
}

static bool transmit_one(void)
{
    tx_item_t item;
    uint8_t payload[MECANUM_UART_V1_MAX_PAYLOAD_LENGTH];
    uint8_t wire[MECANUM_UART_V1_COBS_BUFFER_MINIMUM];
    size_t payload_length, wire_length;
    uint8_t type;
    if (fault_is_latched() || xQueueReceive(tx_queue, &item, 0U) != pdPASS) return false;
    /* Chốt lỗi sau dequeue trước khi serialize hoặc quyết định dispatch. */
    if (fault_is_latched()) return true;
    if (item.type == TX_CONFIG_STATUS) {
        type = MECANUM_UART_V1_MESSAGE_CONFIG;
        payload_length = MECANUM_UART_V1_CONFIG_STATUS_PAYLOAD_LENGTH;
        if (mecanum_uart_v1_serialize_config_status(&item.value.config_status, payload, sizeof(payload)) != MECANUM_UART_V1_OK) {
            latch_fault_task(); return true;
        }
    } else if (item.type == TX_TELEMETRY) {
        type = MECANUM_UART_V1_MESSAGE_TELEMETRY;
        payload_length = MECANUM_UART_V1_TELEMETRY_PAYLOAD_LENGTH;
        if (mecanum_uart_v1_serialize_telemetry(&item.value.telemetry, payload, sizeof(payload)) != MECANUM_UART_V1_OK) {
            latch_fault_task(); return true;
        }
    } else { latch_fault_task(); return true; }
    if (mecanum_uart_v1_build_wire_frame(type, payload, payload_length, wire, sizeof(wire), &wire_length) != MECANUM_UART_V1_OK) {
        latch_fault_task(); return true;
    }
    /* ISR có thể latch lỗi trong lúc serialize; không dispatch frame mới sau latch. */
    if (fault_is_latched()) return true;
    if ((HAL_UART_Transmit(bound_uart, wire, (uint16_t)wire_length, COMMUNICATION_RUNTIME_TX_TIMEOUT_MS) != HAL_OK)
        || fault_is_latched()) latch_fault_task();
    return true;
}

void communication_runtime_service_once(void)
{
    rx_chunk_t chunk;
    uint8_t budget = COMMUNICATION_RUNTIME_RX_PENDING_CHUNKS;
    if (__get_IPSR() != 0U) return;
    if (!started || (xTaskGetCurrentTaskHandle() != communication_task)) return;
    if (fault_is_latched()) {
        bool requested;
        bool cleanup_attempted_now = false;
        uint32_t now = HAL_GetTick();
        bool due;
        taskENTER_CRITICAL();
        requested = recovery_requested;
        taskEXIT_CRITICAL();
        due = !recovery_attempted
            || ((uint32_t)(now - recovery_last_attempt) >= UINT32_C(1000));
        if (!fault_cleanup_done) {
            HAL_StatusTypeDef abort_status;
            if (requested && !due) return;
            abort_status = HAL_UART_AbortReceive(bound_uart);
            cleanup_attempted_now = requested;
            if (abort_status != HAL_OK) {
                recovery_attempted = true;
                recovery_last_attempt = now;
            }
            if (abort_status != HAL_OK) return;
            taskENTER_CRITICAL();
            rx_armed = false;
            taskEXIT_CRITICAL();
            (void)xQueueReset(rx_queue);
            (void)xQueueReset(candidate_queue);
            (void)xQueueReset(tx_queue);
            frame_length = 0U;
            discard_until_delimiter = true;
            fault_cleanup_done = true;
        }
        if (requested && (cleanup_attempted_now || due)) {
                uint32_t generation;
                HAL_StatusTypeDef status;
                (void)xQueueReset(rx_queue);
                (void)xQueueReset(candidate_queue);
                (void)xQueueReset(tx_queue);
                frame_length = 0U;
                discard_until_delimiter = false;
                taskENTER_CRITICAL();
                generation = fault_generation;
                taskEXIT_CRITICAL();
                status = HAL_UARTEx_ReceiveToIdle_IT(bound_uart, hal_rx_buffer,
                    COMMUNICATION_RUNTIME_RX_CHUNK_BYTES);
                recovery_attempted = true;
                recovery_last_attempt = now;
                taskENTER_CRITICAL();
                if ((status == HAL_OK) && (fault_generation == generation)) {
                    transport_fault = false;
                    fault_cleanup_done = false;
                    recovery_requested = false;
                    rx_armed = true;
                } else {
                    transport_fault = true;
                    rx_armed = false;
                }
                taskEXIT_CRITICAL();
        }
        return;
    }
    while ((budget-- > 0U) && (xQueueReceive(rx_queue, &chunk, 0U) == pdPASS)) process_chunk(&chunk);
    if (!fault_is_latched()) (void)transmit_one();
}

static void communication_task_entry(void *argument)
{
    (void)argument;
    for (;;) {
        communication_runtime_service_once();
        (void)ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(COMMUNICATION_RUNTIME_IDLE_WAIT_MS));
    }
}

void HAL_UARTEx_RxEventCallback(UART_HandleTypeDef *uart, uint16_t size)
{
    BaseType_t higher_priority_task_woken = pdFALSE;
    rx_chunk_t chunk;
    if ((uart == NULL) || (uart != bound_uart)) return;
    if ((uart->ErrorCode != HAL_UART_ERROR_NONE) || (size == 0U)
        || (size > COMMUNICATION_RUNTIME_RX_CHUNK_BYTES) || fault_is_latched_isr()) {
        latch_fault_isr(&higher_priority_task_woken);
        portYIELD_FROM_ISR(higher_priority_task_woken);
        return;
    }
    chunk.size = size;
    chunk.tick = HAL_GetTick();
    (void)memcpy(chunk.bytes, hal_rx_buffer, size);
    if (xQueueSendFromISR(rx_queue, &chunk, &higher_priority_task_woken) != pdPASS) {
        latch_fault_isr(&higher_priority_task_woken);
        portYIELD_FROM_ISR(higher_priority_task_woken);
        return;
    }
    if (HAL_UARTEx_ReceiveToIdle_IT(bound_uart, hal_rx_buffer,
                                    COMMUNICATION_RUNTIME_RX_CHUNK_BYTES) != HAL_OK) {
        latch_fault_isr(&higher_priority_task_woken);
    }
    if (communication_task != NULL) vTaskNotifyGiveFromISR(communication_task, &higher_priority_task_woken);
    portYIELD_FROM_ISR(higher_priority_task_woken);
}

void HAL_UART_ErrorCallback(UART_HandleTypeDef *uart)
{
    BaseType_t higher_priority_task_woken = pdFALSE;
    volatile uint32_t captured_error;
    if ((uart == NULL) || (uart != bound_uart)) return;
    captured_error = uart->ErrorCode;
    (void)captured_error;
    latch_fault_isr(&higher_priority_task_woken);
    portYIELD_FROM_ISR(higher_priority_task_woken);
}
