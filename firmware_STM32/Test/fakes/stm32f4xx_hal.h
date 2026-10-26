#ifndef U3_FAKE_HAL_H
#define U3_FAKE_HAL_H
#include <stdint.h>
typedef struct { uint32_t opaque; } USART_TypeDef;
typedef struct { volatile uint32_t CNT; } TIM_TypeDef;
extern USART_TypeDef fake_usart6;
extern TIM_TypeDef fake_tim[5];
#define USART6 (&fake_usart6)
#define TIM1 (&fake_tim[0])
#define TIM2 (&fake_tim[1])
#define TIM4 (&fake_tim[2])
#define TIM5 (&fake_tim[3])
#define TIM10 (&fake_tim[4])
#define TIM_CHANNEL_ALL 0xFFFFU
typedef struct { TIM_TypeDef *Instance; } TIM_HandleTypeDef;
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
uint32_t __get_IPSR(void);
HAL_StatusTypeDef HAL_UARTEx_ReceiveToIdle_IT(UART_HandleTypeDef *uart, uint8_t *data, uint16_t size);
HAL_StatusTypeDef HAL_UART_AbortReceive(UART_HandleTypeDef *uart);
HAL_StatusTypeDef HAL_UART_Transmit(UART_HandleTypeDef *uart, uint8_t *data, uint16_t size, uint32_t timeout);
HAL_StatusTypeDef HAL_TIM_Encoder_Start(TIM_HandleTypeDef *timer, uint32_t channel);
HAL_StatusTypeDef HAL_TIM_Encoder_Stop(TIM_HandleTypeDef *timer, uint32_t channel);
#define __HAL_TIM_GET_COUNTER(timer) ((timer)->Instance->CNT)
void HAL_UARTEx_RxEventCallback(UART_HandleTypeDef *uart, uint16_t size);
void HAL_UART_ErrorCallback(UART_HandleTypeDef *uart);
#endif
