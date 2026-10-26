cmake_minimum_required(VERSION 3.20)
if(STM32_ARM_BUILD)
  set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)
endif()
project(mecanum_stm32_uart_runtime C ASM)

option(STM32_ARM_BUILD "Build the firmware with the STM32 ARM GNU toolchain" OFF)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}")
set(FW ${CMAKE_CURRENT_SOURCE_DIR})

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
  add_executable(test_watchdog Test/test_watchdog.c Core/Src/command_watchdog.c)
  add_test(NAME watchdog COMMAND test_watchdog)
  add_executable(test_boot_id Test/test_boot_id.c Core/Src/boot_id.c)
  add_test(NAME boot_id COMMAND test_boot_id)
  add_executable(test_encoder Test/test_encoder.c Core/Src/encoder.c)
  target_compile_definitions(test_encoder PRIVATE MECANUM_HOST_TEST=1)
  add_test(NAME encoder COMMAND test_encoder)
  add_test(NAME encoder_start_failure COMMAND test_encoder start-failure)
  add_test(NAME encoder_int64_overflow COMMAND test_encoder overflow)
  add_executable(test_telemetry Test/test_telemetry.c Core/Src/telemetry.c)
  add_test(NAME telemetry COMMAND test_telemetry)
  add_executable(test_communication_runtime Test/test_communication_runtime.c
    Core/Src/communication_runtime.c Core/Src/communication.c
    Core/Src/control_safety_session.c Core/Src/control_safety_runtime.c
    Core/Src/command_watchdog.c Core/Src/boot_id.c)
  target_compile_options(test_communication_runtime PRIVATE -Wno-missing-field-initializers)
  add_test(NAME communication_runtime COMMAND test_communication_runtime)
  add_test(NAME control_safety_runtime COMMAND test_communication_runtime u4-session-runtime)
  foreach(case rearm-busy rearm-error invalid-size rx-error-pe rx-error-fe rx-error-ne rx-error-ore tx-timeout tx-error tx-full rx-full candidate-full fault-after-tx-dequeue fault-after-candidate-dequeue fault-during-tx fault-after-status-enqueue fault-after-telemetry-enqueue isr-public-apis)
    add_test(NAME communication_runtime_${case} COMMAND test_communication_runtime ${case})
  endforeach()
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  add_test(NAME uart_session_interop COMMAND ${Python3_EXECUTABLE}
    ${FW}/Test/test_uart_session_interop.py)
  set_tests_properties(uart_session_interop PROPERTIES
    ENVIRONMENT "PYTHONPATH=${FW}/../ros2_ws/src/mecanum_base_bridge;WP07_U4_INTEROP_PEER=$<TARGET_FILE:test_communication_runtime>")
  return()
endif()

if(NOT CMAKE_C_COMPILER MATCHES "arm-none-eabi-gcc")
  message(FATAL_ERROR "STM32_ARM_BUILD requires arm-none-eabi-gcc as CMAKE_C_COMPILER")
endif()
find_package(Python3 REQUIRED COMPONENTS Interpreter)
set(MECANUM_HARDWARE_MANIFEST "" CACHE FILEPATH "Explicit hardware_manifest.yaml input for U4")
if(NOT MECANUM_HARDWARE_MANIFEST OR NOT EXISTS "${MECANUM_HARDWARE_MANIFEST}")
  message(FATAL_ERROR "STM32_ARM_BUILD requires -DMECANUM_HARDWARE_MANIFEST=<hardware_manifest.yaml>")
endif()
set(FW ${CMAKE_CURRENT_SOURCE_DIR})
set(GENERATED_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated")
set(GENERATED_CONFIG_HEADER "${GENERATED_DIR}/generated_hardware_config.h")
set(GENERATED_CONFIG_JSON "${GENERATED_DIR}/hardware_config.json")
set(BRIDGE_PYTHON_SOURCE "${FW}/../ros2_ws/src/mecanum_base_bridge")
add_custom_command(OUTPUT "${GENERATED_CONFIG_HEADER}" "${GENERATED_CONFIG_JSON}"
  COMMAND ${CMAKE_COMMAND} -E env "PYTHONPATH=${BRIDGE_PYTHON_SOURCE}"
    ${Python3_EXECUTABLE} -m mecanum_base_bridge.hardware_config
    "${MECANUM_HARDWARE_MANIFEST}" --header "${GENERATED_CONFIG_HEADER}" --json "${GENERATED_CONFIG_JSON}"
  DEPENDS "${MECANUM_HARDWARE_MANIFEST}"
    "${BRIDGE_PYTHON_SOURCE}/mecanum_base_bridge/hardware_config.py"
  WORKING_DIRECTORY "${BRIDGE_PYTHON_SOURCE}"
  COMMENT "Generating strict RFC8785 hardware configuration outputs")
add_custom_target(generate_hardware_config DEPENDS "${GENERATED_CONFIG_HEADER}" "${GENERATED_CONFIG_JSON}")
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
  ${FW}/Core/Src/encoder.c
  ${FW}/Core/Src/telemetry.c
  ${FW}/Core/Src/communication.c
  ${FW}/Core/Src/communication_runtime.c
  ${FW}/Core/Src/control_safety_session.c
  ${FW}/Core/Src/control_safety_runtime.c
  ${FW}/Core/Src/command_watchdog.c
  ${FW}/Core/Src/boot_id.c
  ${FW}/Core/Src/boot_id_hal.c
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
  ${FW}/Core/Inc "${GENERATED_DIR}" ${FW}/Drivers/STM32F4xx_HAL_Driver/Inc
  ${CMSIS}/Device/ST/STM32F4xx/Include ${CMSIS}/Include
  ${FREERTOS}/include ${FREERTOS}/CMSIS_RTOS_V2
  ${FREERTOS}/portable/GCC/ARM_CM4F)
target_compile_definitions(stm32_uart_runtime PRIVATE STM32F411xE USE_HAL_DRIVER)
add_dependencies(stm32_uart_runtime generate_hardware_config)
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
