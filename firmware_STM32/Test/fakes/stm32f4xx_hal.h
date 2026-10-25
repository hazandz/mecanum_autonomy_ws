#ifndef U3_FAKE_HAL_H
#define U3_FAKE_HAL_H
#include <stdint.h>
typedef struct { uint32_t opaque; } USART_TypeDef;
extern USART_TypeDef fake_usart6;
#define USART6 (&fake_usart6)
typedef enum { HAL_OK = 0, HAL_ERROR = 1, HAL_BUSY = 2, HAL_TIMEOUT = 3 } HAL_StatusTypeDef;
typedef struct {
    USART_TypeDef *Instance;
    volatile uint32_t ErrorCode;
} UART_HandleTypeDef;
#define HAL_UART_ERROR_NONE 0U
#define HAL_UART_ERROR_PE 1U
#define HAL_UART_ERROR_NE 2U
#define HAL_UART_ERROR_FE 4U
#define HAL_UART_ERROR_ORE 8U
uint32_t HAL_GetTick(void);
HAL_StatusTypeDef HAL_UARTEx_ReceiveToIdle_IT(UART_HandleTypeDef *uart, uint8_t *data, uint16_t size);
HAL_StatusTypeDef HAL_UART_AbortReceive(UART_HandleTypeDef *uart);
HAL_StatusTypeDef HAL_UART_Transmit(UART_HandleTypeDef *uart, uint8_t *data, uint16_t size, uint32_t timeout);
void HAL_UARTEx_RxEventCallback(UART_HandleTypeDef *uart, uint16_t size);
void HAL_UART_ErrorCallback(UART_HandleTypeDef *uart);
#endif
