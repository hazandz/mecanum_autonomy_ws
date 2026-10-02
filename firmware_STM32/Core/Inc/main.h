/* USER CODE BEGIN Header */
/* USER CODE END Header */

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __MAIN_H
#define __MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "stm32f4xx_hal.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
/* USER CODE END Includes */

/* Exported types ------------------------------------------------------------*/
/* USER CODE BEGIN ET */
/* USER CODE END ET */

/* Exported constants --------------------------------------------------------*/
/* USER CODE BEGIN EC */
/* USER CODE END EC */

/* Exported macro ------------------------------------------------------------*/
/* USER CODE BEGIN EM */
/* USER CODE END EM */

void HAL_TIM_MspPostInit(TIM_HandleTypeDef *htim);

/* Exported functions prototypes ---------------------------------------------*/
void Error_Handler(void);

/* USER CODE BEGIN EFP */
/* USER CODE END EFP */

/* Private defines -----------------------------------------------------------*/
#define ENC_FR_A_Pin GPIO_PIN_0
#define ENC_FR_A_GPIO_Port GPIOA
#define ENC_FR_B_Pin GPIO_PIN_1
#define ENC_FR_B_GPIO_Port GPIOA
#define MOTOR_FR_IN2_Pin GPIO_PIN_2
#define MOTOR_FR_IN2_GPIO_Port GPIOA
#define MOTOR_FR_IN1_Pin GPIO_PIN_3
#define MOTOR_FR_IN1_GPIO_Port GPIOA
#define MOTOR_FL_IN1_Pin GPIO_PIN_4
#define MOTOR_FL_IN1_GPIO_Port GPIOA
#define MOTOR_FL_IN2_Pin GPIO_PIN_5
#define MOTOR_FL_IN2_GPIO_Port GPIOA
#define MOTOR_FR_PWM_Pin GPIO_PIN_0
#define MOTOR_FR_PWM_GPIO_Port GPIOB
#define MOTOR_FL_PWM_Pin GPIO_PIN_1
#define MOTOR_FL_PWM_GPIO_Port GPIOB
#define MCU_MOTOR_ENABLE_Pin GPIO_PIN_10
#define MCU_MOTOR_ENABLE_GPIO_Port GPIOB
#define MOTOR_RL_IN2_Pin GPIO_PIN_12
#define MOTOR_RL_IN2_GPIO_Port GPIOB
#define MOTOR_RL_IN1_Pin GPIO_PIN_13
#define MOTOR_RL_IN1_GPIO_Port GPIOB
#define MOTOR_RR_IN1_Pin GPIO_PIN_14
#define MOTOR_RR_IN1_GPIO_Port GPIOB
#define MOTOR_RR_IN2_Pin GPIO_PIN_15
#define MOTOR_RR_IN2_GPIO_Port GPIOB
#define ENC_RL_A_Pin GPIO_PIN_8
#define ENC_RL_A_GPIO_Port GPIOA
#define ENC_RL_B_Pin GPIO_PIN_9
#define ENC_RL_B_GPIO_Port GPIOA
#define ENC_FL_A_Pin GPIO_PIN_15
#define ENC_FL_A_GPIO_Port GPIOA
#define ENC_FL_B_Pin GPIO_PIN_3
#define ENC_FL_B_GPIO_Port GPIOB
#define MOTOR_RL_PWM_Pin GPIO_PIN_4
#define MOTOR_RL_PWM_GPIO_Port GPIOB
#define MOTOR_RR_PWM_Pin GPIO_PIN_5
#define MOTOR_RR_PWM_GPIO_Port GPIOB
#define ENC_RR_A_Pin GPIO_PIN_6
#define ENC_RR_A_GPIO_Port GPIOB
#define ENC_RR_B_Pin GPIO_PIN_7
#define ENC_RR_B_GPIO_Port GPIOB

/* USER CODE BEGIN Private defines */
/* USER CODE END Private defines */

#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */
