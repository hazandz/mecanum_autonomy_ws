#ifndef MECANUM_TELEMETRY_H
#define MECANUM_TELEMETRY_H

#include <stdbool.h>

bool telemetry_runtime_start(void);
/* Chỉ TelemetryTask mới được gọi trong production task context. */
bool telemetry_runtime_service_once(void);

#endif
