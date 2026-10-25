#ifndef U3_FAKE_FREERTOS_H
#define U3_FAKE_FREERTOS_H
#include <stddef.h>
#include <stdint.h>
typedef int BaseType_t;
typedef unsigned UBaseType_t;
typedef uint32_t TickType_t;
typedef uint32_t StackType_t;
typedef struct { uintptr_t opaque[16]; } StaticQueue_t;
typedef struct { uintptr_t opaque[32]; } StaticTask_t;
#define pdTRUE 1
#define pdFALSE 0
#define pdPASS 1
#define pdFAIL 0
#define pdMS_TO_TICKS(ms) (ms)
#define taskENTER_CRITICAL() fake_task_enter_critical()
#define taskEXIT_CRITICAL() fake_task_exit_critical()
#define taskENTER_CRITICAL_FROM_ISR() fake_task_enter_critical_from_isr()
#define taskEXIT_CRITICAL_FROM_ISR(mask) fake_task_exit_critical_from_isr(mask)
#define portYIELD_FROM_ISR(woken) fake_yield_from_isr(woken)
void fake_task_enter_critical(void);
void fake_task_exit_critical(void);
UBaseType_t fake_task_enter_critical_from_isr(void);
void fake_task_exit_critical_from_isr(UBaseType_t mask);
void fake_yield_from_isr(BaseType_t woken);
#endif
