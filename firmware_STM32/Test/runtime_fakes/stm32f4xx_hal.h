#ifndef MANUAL_SLAM_RUNTIME_FAKE_HAL_H
#define MANUAL_SLAM_RUNTIME_FAKE_HAL_H

#include <stdint.h>

typedef struct { uint32_t autoreload; } TIM_TypeDef;
typedef struct { TIM_TypeDef *Instance; } TIM_HandleTypeDef;
typedef struct { uint8_t opaque; } GPIO_TypeDef;
typedef enum { GPIO_PIN_RESET = 0, GPIO_PIN_SET = 1 } GPIO_PinState;
typedef enum { HAL_OK = 0, HAL_ERROR = 1 } HAL_StatusTypeDef;

extern TIM_HandleTypeDef htim1, htim2, htim3, htim4, htim5;
extern GPIO_TypeDef fake_gpio_b;

#define GPIOB (&fake_gpio_b)
#define GPIO_PIN_10 (1U << 10)
#define TIM_CHANNEL_1 1U
#define TIM_CHANNEL_2 2U
#define TIM_CHANNEL_3 3U
#define TIM_CHANNEL_4 4U

HAL_StatusTypeDef HAL_TIM_PWM_Start(TIM_HandleTypeDef *timer, uint32_t channel);
void HAL_GPIO_WritePin(GPIO_TypeDef *port, uint16_t pin, GPIO_PinState state);
void manual_slam_fake_set_compare(TIM_HandleTypeDef *timer, uint32_t channel,
                                  uint32_t compare);
uint32_t manual_slam_fake_get_compare(TIM_HandleTypeDef *timer, uint32_t channel);

#define __HAL_TIM_SET_COMPARE(timer, channel, value) \
    manual_slam_fake_set_compare((timer), (channel), (value))
#define __HAL_TIM_GET_AUTORELOAD(timer) ((timer)->Instance->autoreload)

#endif
