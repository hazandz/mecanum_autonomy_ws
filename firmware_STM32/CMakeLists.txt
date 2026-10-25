cmake_minimum_required(VERSION 3.20)
if(STM32_ARM_BUILD)
  set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)
endif()
project(mecanum_stm32_uart_runtime C ASM)

option(STM32_ARM_BUILD "Build the firmware with the STM32 ARM GNU toolchain" OFF)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}")

if(NOT STM32_ARM_BUILD)
  enable_testing()
  add_compile_options(-Wall -Wextra -Wpedantic -Werror -UNDEBUG)
  include(CheckCSourceCompiles)
  set(CMAKE_REQUIRED_FLAGS "-fsanitize=address,undefined")
  set(CMAKE_REQUIRED_LINK_OPTIONS "-fsanitize=address,undefined")
  check_c_source_compiles("int main(void) { return 0; }" U3_HAS_SANITIZERS)
  unset(CMAKE_REQUIRED_FLAGS)
  unset(CMAKE_REQUIRED_LINK_OPTIONS)
  if(U3_HAS_SANITIZERS)
    add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)
    add_link_options(-fsanitize=address,undefined)
  endif()
  include_directories(Core/Inc Test/fakes)
  add_executable(test_communication_codec Test/test_communication_codec.c Core/Src/communication.c)
  add_test(NAME communication_codec COMMAND test_communication_codec)
  add_executable(test_control_safety_session Test/test_control_safety_session.c
    Core/Src/control_safety_session.c Core/Src/communication.c)
  add_test(NAME control_safety_session COMMAND test_control_safety_session)
  add_executable(test_communication_runtime Test/test_communication_runtime.c
    Core/Src/communication_runtime.c Core/Src/communication.c)
  target_compile_options(test_communication_runtime PRIVATE -Wno-missing-field-initializers)
  add_test(NAME communication_runtime COMMAND test_communication_runtime)
  foreach(case rearm-busy rearm-error invalid-size rx-error-pe rx-error-fe rx-error-ne rx-error-ore tx-timeout tx-error tx-full rx-full candidate-full fault-after-tx-dequeue fault-after-candidate-dequeue fault-during-tx fault-after-status-enqueue fault-after-telemetry-enqueue isr-public-apis)
    add_test(NAME communication_runtime_${case} COMMAND test_communication_runtime ${case})
  endforeach()
  return()
endif()

if(NOT CMAKE_C_COMPILER MATCHES "arm-none-eabi-gcc")
  message(FATAL_ERROR "STM32_ARM_BUILD requires arm-none-eabi-gcc as CMAKE_C_COMPILER")
endif()
set(FW ${CMAKE_CURRENT_SOURCE_DIR})
set(HAL ${FW}/Drivers/STM32F4xx_HAL_Driver)
set(CMSIS ${FW}/Drivers/CMSIS)
set(FREERTOS ${FW}/Middlewares/Third_Party/FreeRTOS/Source)
add_executable(stm32_uart_runtime
  ${FW}/Core/Src/main.c
  ${FW}/Core/Src/freertos.c
  ${FW}/Core/Src/stm32f4xx_hal_msp.c
  ${FW}/Core/Src/stm32f4xx_hal_timebase_tim.c
  ${FW}/Core/Src/stm32f4xx_it.c
  ${FW}/Core/Src/system_stm32f4xx.c
  ${FW}/Core/Src/safety_io.c
  ${FW}/Core/Src/communication.c
  ${FW}/Core/Src/communication_runtime.c
  ${FW}/Core/Src/syscalls.c
  ${FW}/Core/Src/sysmem.c
  ${FW}/Core/Startup/startup_stm32f411ceux.s
  ${HAL}/Src/stm32f4xx_hal.c
  ${HAL}/Src/stm32f4xx_hal_cortex.c
  ${HAL}/Src/stm32f4xx_hal_dma.c
  ${HAL}/Src/stm32f4xx_hal_exti.c
  ${HAL}/Src/stm32f4xx_hal_flash.c
  ${HAL}/Src/stm32f4xx_hal_flash_ex.c
  ${HAL}/Src/stm32f4xx_hal_gpio.c
  ${HAL}/Src/stm32f4xx_hal_pwr.c
  ${HAL}/Src/stm32f4xx_hal_pwr_ex.c
  ${HAL}/Src/stm32f4xx_hal_rcc.c
  ${HAL}/Src/stm32f4xx_hal_rcc_ex.c
  ${HAL}/Src/stm32f4xx_hal_tim.c
  ${HAL}/Src/stm32f4xx_hal_tim_ex.c
  ${HAL}/Src/stm32f4xx_hal_uart.c
  ${FREERTOS}/CMSIS_RTOS_V2/cmsis_os2.c
  ${FREERTOS}/list.c ${FREERTOS}/queue.c ${FREERTOS}/tasks.c ${FREERTOS}/timers.c
  ${FREERTOS}/portable/GCC/ARM_CM4F/port.c
  ${FREERTOS}/portable/MemMang/heap_4.c)
target_include_directories(stm32_uart_runtime PRIVATE
  ${FW}/Core/Inc ${FW}/Drivers/STM32F4xx_HAL_Driver/Inc
  ${CMSIS}/Device/ST/STM32F4xx/Include ${CMSIS}/Include
  ${FREERTOS}/include ${FREERTOS}/CMSIS_RTOS_V2
  ${FREERTOS}/portable/GCC/ARM_CM4F)
target_compile_definitions(stm32_uart_runtime PRIVATE STM32F411xE USE_HAL_DRIVER)
target_compile_options(stm32_uart_runtime PRIVATE
  -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard
  -ffunction-sections -fdata-sections -Wall -Wextra -Wno-unused-parameter)
target_link_options(stm32_uart_runtime PRIVATE
  -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard
  --specs=nano.specs --specs=nosys.specs -T${FW}/STM32F411CEUX_FLASH.ld
  -Wl,--gc-sections -Wl,-Map=${CMAKE_CURRENT_BINARY_DIR}/stm32_uart_runtime.map)
set_target_properties(stm32_uart_runtime PROPERTIES
  SUFFIX ".elf"
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}")
