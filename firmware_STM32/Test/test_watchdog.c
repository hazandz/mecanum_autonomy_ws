#include "command_watchdog.h"

#include <assert.h>
#include <stdio.h>

int main(void)
{
    command_watchdog_t watchdog;
    command_watchdog_init(&watchdog, 200U);
    assert(!watchdog.armed);
    assert(!command_watchdog_expired(&watchdog, 100U));
    assert(!command_watchdog_accept(&watchdog, 10U, 210U));
    assert(!watchdog.armed);
    assert(command_watchdog_accept(&watchdog, 10U, 209U));
    assert(!command_watchdog_expired(&watchdog, 209U));
    assert(!command_watchdog_expired(&watchdog, 209U));
    assert(command_watchdog_expired(&watchdog, 210U));
    command_watchdog_init(&watchdog, 200U);
    assert(command_watchdog_accept(&watchdog, UINT32_MAX - 50U, 10U));
    assert(!command_watchdog_expired(&watchdog, 148U));
    assert(command_watchdog_expired(&watchdog, 149U));
    command_watchdog_disarm(&watchdog);
    assert(!command_watchdog_expired(&watchdog, 1000U));
    puts("Command watchdog tests passed: boundaries, stale queue tick, uint32 wrap.");
    return 0;
}
