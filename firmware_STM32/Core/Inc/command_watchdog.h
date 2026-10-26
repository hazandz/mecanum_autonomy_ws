#ifndef MECANUM_COMMAND_WATCHDOG_H
#define MECANUM_COMMAND_WATCHDOG_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint32_t timeout_ms;
    uint32_t last_accepted_tick;
    bool armed;
} command_watchdog_t;

void command_watchdog_init(command_watchdog_t *watchdog, uint32_t timeout_ms);
void command_watchdog_disarm(command_watchdog_t *watchdog);
bool command_watchdog_accept(command_watchdog_t *watchdog, uint32_t candidate_tick,
                             uint32_t now_tick);
bool command_watchdog_expired(const command_watchdog_t *watchdog, uint32_t now_tick);

#endif
