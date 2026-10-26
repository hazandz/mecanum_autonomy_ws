#include "boot_id.h"

#include "stm32f4xx_hal.h"
#include "stm32f4xx_hal_flash.h"

#define BOOT_ID_FLASH_BASE (FLASH_BASE + UINT32_C(0x00060000))

static bool flash_read_cell(void *context, uint32_t index, uint32_t *value)
{
    uint32_t cache_enabled;
    (void)context;
    if ((index >= BOOT_ID_JOURNAL_CELL_COUNT) || (value == 0)) return false;
    cache_enabled = (FLASH->ACR & FLASH_ACR_DCEN);
    if (cache_enabled != 0U) __HAL_FLASH_DATA_CACHE_DISABLE();
    __HAL_FLASH_DATA_CACHE_RESET();
    *value = *(volatile const uint32_t *)(BOOT_ID_FLASH_BASE + index * 4U);
    if (cache_enabled != 0U) __HAL_FLASH_DATA_CACHE_ENABLE();
    return true;
}

static bool flash_program_cell(void *context, uint32_t index, uint32_t value)
{
    uint32_t byte_index;
    bool ok = true;
    uint32_t address;
    (void)context;
    if ((index >= BOOT_ID_JOURNAL_CELL_COUNT) || (value != BOOT_ID_JOURNAL_COMMITTED)) return false;
    address = BOOT_ID_FLASH_BASE + index * 4U;
    if (HAL_FLASH_Unlock() != HAL_OK) {
        (void)HAL_FLASH_Lock();
        return false;
    }
    for (byte_index = 0U; byte_index < 4U; ++byte_index) {
        if (HAL_FLASH_Program(FLASH_TYPEPROGRAM_BYTE, address + byte_index, 0U) != HAL_OK) {
            ok = false;
            break;
        }
    }
    if (HAL_FLASH_Lock() != HAL_OK) ok = false;
    return ok;
}

bool boot_id_allocate_hal(uint64_t *boot_id)
{
    const boot_id_storage_t storage = {0, flash_read_cell, flash_program_cell};
    return boot_id_allocate(&storage, boot_id);
}
