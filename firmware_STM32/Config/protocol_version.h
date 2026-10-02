#ifndef MECANUM_PROTOCOL_VERSION_H
#define MECANUM_PROTOCOL_VERSION_H

#include <stdint.h>

/* Pi–STM32 UART v1: docs/Pi_STM32_Interface_Contract.md, section 4. */
#define MECANUM_UART_V1_PROTOCOL_VERSION UINT16_C(0x0001)

#endif /* MECANUM_PROTOCOL_VERSION_H */
