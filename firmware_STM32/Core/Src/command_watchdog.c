#include "command_watchdog.h"

#include <stddef.h>
#include <string.h>

void command_watchdog_init(command_watchdog_t *watchdog, uint32_t timeout_ms)
{
    if (watchdog == NULL) return;
    memset(watchdog, 0, sizeof(*watchdog));
    watchdog->timeout_ms = timeout_ms;
}

void command_watchdog_disarm(command_watchdog_t *watchdog)
{
    if (watchdog != NULL) watchdog->armed = false;
}

bool command_watchdog_accept(command_watchdog_t *watchdog, uint32_t candidate_tick,
                             uint32_t now_tick)
{
    if ((watchdog == NULL) || (watchdog->timeout_ms == 0U)
        || ((uint32_t)(now_tick - candidate_tick) >= watchdog->timeout_ms)) {
        return false;
    }
    watchdog->last_accepted_tick = candidate_tick;
    watchdog->armed = true;
    return true;
}

bool command_watchdog_expired(const command_watchdog_t *watchdog, uint32_t now_tick)
{
    return (watchdog != NULL) && watchdog->armed
        && ((uint32_t)(now_tick - watchdog->last_accepted_tick) >= watchdog->timeout_ms);
}
