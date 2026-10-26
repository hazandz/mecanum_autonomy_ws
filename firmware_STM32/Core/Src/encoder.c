#include "encoder.h"
#include "FreeRTOS.h"
#include "task.h"

#include <limits.h>
#include <stddef.h>

static TIM_HandleTypeDef *timers[4];
static uint32_t previous[4];
static int64_t cumulative[4];
static uint32_t previous_tick;
static uint64_t tick_high;
static uint64_t monotonic_us;
static bool initialized;
static bool valid;

static bool extend_counter(uint32_t raw, uint32_t old, unsigned width,
                           int64_t *total, uint32_t *next)
{
    uint64_t modulus = UINT64_C(1) << width;
    uint32_t mask = width == 32U ? UINT32_MAX : ((UINT32_C(1) << width) - 1U);
    uint32_t delta_bits = (raw - old) & mask;
    uint64_t half = modulus >> 1U;
    int64_t delta;
    if ((uint64_t)delta_bits == half) return false;
    if ((uint64_t)delta_bits < half) {
        delta = (int64_t)delta_bits;
    } else {
        delta = -(int64_t)(modulus - (uint64_t)delta_bits);
    }
    if ((delta > 0 && *total > INT64_MAX - delta)
        || (delta < 0 && *total < INT64_MIN - delta)) return false;
    *total += delta;
    *next = raw;
    return true;
}

bool encoder_start(TIM_HandleTypeDef *fl, TIM_HandleTypeDef *fr,
                   TIM_HandleTypeDef *rl, TIM_HandleTypeDef *rr)
{
    if (initialized || fl == NULL || fr == NULL || rl == NULL || rr == NULL) return false;
    timers[0] = fl; timers[1] = fr; timers[2] = rl; timers[3] = rr;
    for (unsigned i = 0; i < 4U; ++i) {
        if (HAL_TIM_Encoder_Start(timers[i], TIM_CHANNEL_ALL) != HAL_OK) {
            for (unsigned j = 0; j < i; ++j) (void)HAL_TIM_Encoder_Stop(timers[j], TIM_CHANNEL_ALL);
            valid = false;
            return false;
        }
        previous[i] = __HAL_TIM_GET_COUNTER(timers[i]);
        cumulative[i] = 0;
    }
    previous_tick = HAL_GetTick();
    tick_high = 0U;
    monotonic_us = 0U;
    valid = true;
    initialized = true;
    return true;
}

static bool sample_raw(uint32_t fl, uint32_t fr, uint32_t rl, uint32_t rr,
                       uint32_t tick_ms)
{
    uint32_t raw[4] = {fl, fr, rl, rr};
    uint32_t next[4];
    const unsigned widths[4] = {32U, 32U, 16U, 16U};
    if (!initialized || !valid) return false;
    for (unsigned i = 0; i < 4U; ++i) {
        if (!extend_counter(raw[i], previous[i], widths[i], &cumulative[i], &next[i])) {
            valid = false;
            return false;
        }
    }
    for (unsigned i = 0; i < 4U; ++i) previous[i] = next[i];
    if (tick_ms < previous_tick) {
        if (tick_high > UINT64_MAX - (UINT64_C(1) << 32U)) {
            valid = false;
            return false;
        }
        tick_high += (UINT64_C(1) << 32U);
    }
    previous_tick = tick_ms;
    if (tick_high > UINT64_MAX - tick_ms
        || tick_high + tick_ms > UINT64_MAX / UINT64_C(1000)) {
        valid = false;
        return false;
    }
    monotonic_us = (tick_high + tick_ms) * UINT64_C(1000);
    return true;
}

#ifdef MECANUM_HOST_TEST
bool encoder_sample_raw(uint32_t fl, uint32_t fr, uint32_t rl, uint32_t rr,
                        uint32_t tick_ms)
{
    return sample_raw(fl, fr, rl, rr, tick_ms);
}
bool encoder_test_set_cumulative(unsigned wheel, int64_t ticks)
{
    if (!initialized || wheel >= 4U) return false;
    cumulative[wheel] = ticks;
    return true;
}
#endif

void encoder_sample_1ms(void)
{
    if (!initialized || !valid) return;
    (void)sample_raw(__HAL_TIM_GET_COUNTER(timers[0]),
        __HAL_TIM_GET_COUNTER(timers[1]), __HAL_TIM_GET_COUNTER(timers[2]),
        __HAL_TIM_GET_COUNTER(timers[3]), HAL_GetTick());
}

bool encoder_snapshot(encoder_snapshot_t *snapshot)
{
    if (snapshot == NULL || !initialized) return false;
    taskENTER_CRITICAL();
    snapshot->ticks_fl = cumulative[0]; snapshot->ticks_fr = cumulative[1];
    snapshot->ticks_rl = cumulative[2]; snapshot->ticks_rr = cumulative[3];
    snapshot->monotonic_time_us = monotonic_us;
    snapshot->valid = valid;
    taskEXIT_CRITICAL();
    return snapshot->valid;
}
