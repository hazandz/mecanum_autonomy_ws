#ifndef U3_FAKE_TASK_H
#define U3_FAKE_TASK_H
#include "FreeRTOS.h"
typedef void *TaskHandle_t;
TaskHandle_t xTaskCreateStatic(void (*entry)(void *), const char *name, uint32_t depth,
                               void *arg, UBaseType_t priority, StackType_t *stack,
                               StaticTask_t *control);
void vTaskNotifyGiveFromISR(TaskHandle_t task, BaseType_t *woken);
uint32_t ulTaskNotifyTake(BaseType_t clear, TickType_t ticks);
TaskHandle_t xTaskGetCurrentTaskHandle(void);
TickType_t xTaskGetTickCount(void);
void vTaskDelayUntil(TickType_t *last_wake, TickType_t increment);
#endif
