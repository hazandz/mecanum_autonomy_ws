#include "telemetry.h"
#include "communication_runtime.h"
#include "control_safety_runtime.h"
#include "encoder.h"
#include "safety_io.h"
#include "task.h"
#include <assert.h>
#include <string.h>

static bool estop_valid;
static bool estop_value;
static bool session_configured;
static unsigned sent;
static mecanum_uart_v1_telemetry_t last;
static TaskHandle_t current_task;
uint32_t __get_IPSR(void) { return 0U; }
TaskHandle_t xTaskCreateStatic(void (*entry)(void *),const char *name,uint32_t depth,
 void *arg,UBaseType_t priority,StackType_t *stack,StaticTask_t *control)
{ assert(entry && name && depth==384U && arg==NULL && priority==8U && stack && control); current_task=control; return control; }
TaskHandle_t xTaskGetCurrentTaskHandle(void) { return current_task; }
TickType_t xTaskGetTickCount(void) { return 0U; }
void vTaskDelayUntil(TickType_t *last,TickType_t n) {(void)last;(void)n;}
bool control_safety_runtime_copy_snapshot(control_safety_snapshot_t *s)
{ memset(s,0,sizeof(*s)); s->configured=session_configured; s->telemetry_allowed=session_configured; s->mcu_boot_id=44U; return true; }
bool encoder_snapshot(encoder_snapshot_t *s)
{ memset(s,0,sizeof(*s)); s->valid=true; s->ticks_fl=7; s->monotonic_time_us=1000U; return true; }
bool safety_io_read_estop_aux(bool *active) { if (!estop_valid) return false; *active=estop_value; return true; }
bool control_safety_runtime_enqueue_telemetry_if_current(
 const control_safety_snapshot_t *snapshot,const mecanum_uart_v1_telemetry_t *p)
{ assert(snapshot && snapshot->configured && snapshot->telemetry_allowed); last=*p; ++sent; return true; }

int main(void)
{
    assert(telemetry_runtime_start());
    assert(!telemetry_runtime_service_once() && sent==0U); /* Trước CONFIG. */
    session_configured=true;
    assert(!telemetry_runtime_service_once() && sent==0U); /* E-stop mapping absent. */
    estop_valid=true; estop_value=true;
    assert(telemetry_runtime_service_once() && sent==1U);
    assert(last.telemetry_sequence==0U && last.ticks_fl==7);
    assert(last.estop_aux_active==1U && (last.mcu_fault_bits & MECANUM_FAULT_ESTOP_ACTIVE));
    return 0;
}
