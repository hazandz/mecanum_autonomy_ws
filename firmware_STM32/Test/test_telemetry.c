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
static bool session_telemetry_allowed;
static bool session_motor_enabled;
static bool encoder_valid = true;
static bool mutate_snapshot;
static unsigned snapshot_calls;
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
{ memset(s,0,sizeof(*s)); ++snapshot_calls; s->configured=session_configured; s->telemetry_allowed=session_telemetry_allowed; s->motor_enabled=session_motor_enabled; s->snapshot_revision=mutate_snapshot && snapshot_calls % 2U == 0U ? 8U : 7U; s->mcu_boot_id=44U; return true; }
bool encoder_snapshot(encoder_snapshot_t *s)
{ memset(s,0,sizeof(*s)); s->valid=encoder_valid; s->ticks_fl=7; s->monotonic_time_us=1000U; return encoder_valid; }
bool safety_io_read_estop_aux(bool *active) { if (!estop_valid) return false; *active=estop_value; return true; }
bool control_safety_runtime_enqueue_telemetry_if_current(
 const control_safety_snapshot_t *snapshot,const mecanum_uart_v1_telemetry_t *p)
{ assert(snapshot && snapshot->configured && snapshot->telemetry_allowed); last=*p; ++sent; return true; }

int main(void)
{
    assert(telemetry_runtime_start());
    assert(!telemetry_runtime_service_once() && sent==0U); /* Trước CONFIG. */
    session_configured=true;
    session_telemetry_allowed=true;
    /* Encoder values above are synthetic test-double data, not MCU evidence. */
    assert(telemetry_runtime_service_once() && sent==1U); /* Mapping absent -> UNKNOWN. */
    assert(last.telemetry_sequence==0U && last.ticks_fl==7);
    assert(last.estop_aux_active==MECANUM_UART_V1_ESTOP_AUX_UNKNOWN);
    assert((last.mcu_fault_bits & MECANUM_FAULT_ESTOP_ACTIVE)==0U);
    estop_valid=true; estop_value=true;
    assert(telemetry_runtime_service_once() && sent==2U);
    assert(last.telemetry_sequence==1U && last.estop_aux_active==MECANUM_UART_V1_ESTOP_AUX_ACTIVE);
    assert((last.mcu_fault_bits & MECANUM_FAULT_ESTOP_ACTIVE)!=0U);
    estop_value=false;
    assert(telemetry_runtime_service_once() && sent==3U);
    assert(last.estop_aux_active==MECANUM_UART_V1_ESTOP_AUX_INACTIVE);
    encoder_valid=false;
    assert(!telemetry_runtime_service_once() && sent==3U);
    encoder_valid=true;
    mutate_snapshot=true; snapshot_calls=0U;
    assert(!telemetry_runtime_service_once() && sent==3U);
    mutate_snapshot=false; snapshot_calls=0U;
    session_telemetry_allowed=false;
    assert(!telemetry_runtime_service_once() && sent==3U);
    session_telemetry_allowed=true; session_motor_enabled=true;
    assert(!telemetry_runtime_service_once() && sent==3U);
    return 0;
}
