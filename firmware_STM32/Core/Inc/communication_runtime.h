#ifndef MECANUM_COMMUNICATION_RUNTIME_H
#define MECANUM_COMMUNICATION_RUNTIME_H

#include "communication.h"

#include "stm32f4xx_hal.h"

#include <stdbool.h>
#include <stdint.h>

#define COMMUNICATION_RUNTIME_RX_CHUNK_BYTES 128U
#define COMMUNICATION_RUNTIME_RX_PENDING_CHUNKS 4U
#define COMMUNICATION_RUNTIME_CANDIDATE_QUEUE_LENGTH 8U
#define COMMUNICATION_RUNTIME_TX_QUEUE_LENGTH 8U
#define COMMUNICATION_RUNTIME_TASK_PRIORITY 24U
#define COMMUNICATION_RUNTIME_TASK_STACK_WORDS 512U
#define COMMUNICATION_RUNTIME_TX_TIMEOUT_MS 10U
#define COMMUNICATION_RUNTIME_IDLE_WAIT_MS 5U

typedef enum {
    COMMUNICATION_CANDIDATE_CONFIG_REQUEST = 1,
    COMMUNICATION_CANDIDATE_COMMAND = 2
} communication_candidate_type_t;

typedef struct {
    communication_candidate_type_t type;
    uint32_t rx_tick;
    union {
        mecanum_uart_v1_config_request_t config_request;
        mecanum_uart_v1_command_t command;
    } value;
} communication_candidate_t;

/* API này chỉ gọi trong task context; lời gọi từ ISR bị từ chối. */
bool communication_runtime_start(UART_HandleTypeDef *uart);
bool communication_runtime_prepare(UART_HandleTypeDef *uart);
bool communication_runtime_arm_rx(void);
bool communication_runtime_request_recovery(void);
bool communication_runtime_recovery_complete(void);
bool communication_runtime_is_started(void);
bool communication_runtime_is_faulted(void);
/* Các API công khai bên dưới chỉ dành cho task context, không gọi từ ISR. */
bool communication_runtime_is_usable(void);
bool communication_runtime_take_candidate(communication_candidate_t *candidate);
bool communication_runtime_enqueue_config_status(
    const mecanum_uart_v1_config_status_t *status);
bool communication_runtime_enqueue_telemetry(
    const mecanum_uart_v1_telemetry_t *telemetry);
void communication_runtime_service_once(void);

#endif
