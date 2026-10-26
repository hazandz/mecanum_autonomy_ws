#include "encoder.h"
#include "FreeRTOS.h"
#include <assert.h>

TIM_TypeDef fake_tim[5];
static uint32_t tick;
static unsigned starts, stops, critical_enters, critical_exits;
static bool fail_second_start;
uint32_t HAL_GetTick(void) { return tick; }
uint32_t __get_IPSR(void) { return 0U; }
HAL_StatusTypeDef HAL_TIM_Encoder_Start(TIM_HandleTypeDef *timer, uint32_t channel)
{ (void)timer; (void)channel; ++starts; return fail_second_start && starts == 2U ? HAL_ERROR : HAL_OK; }
HAL_StatusTypeDef HAL_TIM_Encoder_Stop(TIM_HandleTypeDef *timer, uint32_t channel)
{ (void)timer; (void)channel; ++stops; return HAL_OK; }
void fake_task_enter_critical(void) { ++critical_enters; }
void fake_task_exit_critical(void) { ++critical_exits; }

int main(int argc, char **argv)
{
    TIM_HandleTypeDef fl={TIM2}, fr={TIM5}, rl={TIM1}, rr={TIM4};
    encoder_snapshot_t s;
    (void)argv;
    if (argc > 1 && argv[1][0] == 'o') {
        assert(encoder_start(&fl,&fr,&rl,&rr));
        assert(encoder_test_set_cumulative(0U, INT64_MAX));
        fake_tim[1].CNT=1U;
        assert(!encoder_sample_raw(1U,0U,0U,0U,1U));
        assert(!encoder_snapshot(&s));
        return 0;
    }
    if (argc > 1) {
        assert(!encoder_sample_raw(0U,0U,0U,0U,0U));
        fail_second_start=true;
        assert(!encoder_start(&fl,&fr,&rl,&rr));
        assert(starts==2U && stops==1U && !encoder_snapshot(&s));
        return 0;
    }
    fake_tim[1].CNT=UINT32_MAX-1U; fake_tim[3].CNT=4U;
    fake_tim[0].CNT=2U; fake_tim[2].CNT=1U; tick=UINT32_MAX-1U;
    assert(encoder_start(&fl,&fr,&rl,&rr));
    assert(encoder_snapshot(&s) && s.valid && s.monotonic_time_us==0U);
    fake_tim[1].CNT=1U; fake_tim[3].CNT=2U; fake_tim[0].CNT=65534U; fake_tim[2].CNT=65535U;
    tick=1U;
    assert(encoder_sample_raw(fake_tim[1].CNT,fake_tim[3].CNT,
                              fake_tim[0].CNT,fake_tim[2].CNT,tick));
    assert(encoder_snapshot(&s));
    assert(critical_enters == critical_exits && critical_enters == 2U);
    assert(s.ticks_fl==3 && s.ticks_fr==-2 && s.ticks_rl==-4 && s.ticks_rr==-2);
    assert(s.monotonic_time_us==UINT64_C(4294967297000));
    assert(!encoder_sample_raw(fake_tim[1].CNT+UINT32_C(0x80000000),
        fake_tim[3].CNT,fake_tim[0].CNT,fake_tim[2].CNT,2U));
    assert(!encoder_snapshot(&s));
    return 0;
}
