#ifndef MECANUM_TIMER_IRQ_DISPATCH_H
#define MECANUM_TIMER_IRQ_DISPATCH_H

typedef void (*timer_irq_dispatch_fn)(void *handle);

static inline void timer_irq_dispatch_if_initialized(
    void *handle, const void *instance, timer_irq_dispatch_fn dispatch)
{
    if ((handle != 0) && (instance != 0) && (dispatch != 0)) {
        dispatch(handle);
    }
}

#endif
