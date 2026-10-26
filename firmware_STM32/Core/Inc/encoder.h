#ifndef MECANUM_ENCODER_H
#define MECANUM_ENCODER_H

#include "stm32f4xx_hal.h"
#include <stdbool.h>
#include <stdint.h>

typedef struct {
    int64_t ticks_fl;
    int64_t ticks_fr;
    int64_t ticks_rl;
    int64_t ticks_rr;
    uint64_t monotonic_time_us;
    bool valid;
} encoder_snapshot_t;

bool encoder_start(TIM_HandleTypeDef *fl, TIM_HandleTypeDef *fr,
                   TIM_HandleTypeDef *rl, TIM_HandleTypeDef *rr);
void encoder_sample_1ms(void);
bool encoder_snapshot(encoder_snapshot_t *snapshot);
/* Seam kiểm thử host dùng chung đường mở rộng modular của callback TIM10. */
#ifdef MECANUM_HOST_TEST
bool encoder_sample_raw(uint32_t fl, uint32_t fr, uint32_t rl, uint32_t rr,
                        uint32_t tick_ms);
bool encoder_test_set_cumulative(unsigned wheel, int64_t ticks);
#endif

#endif
