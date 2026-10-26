#include "boot_id.h"

bool boot_id_allocate(const boot_id_storage_t *storage, uint64_t *boot_id)
{
    uint32_t i;
    uint32_t allocation_index = 0U;
    uint32_t value;
    bool found_erased = false;
    if ((storage == 0) || (storage->read_cell == 0) || (storage->program_cell == 0)
        || (boot_id == 0)) return false;
    for (i = 0U; i < BOOT_ID_JOURNAL_CELL_COUNT; ++i) {
        if (!storage->read_cell(storage->context, i, &value)) return false;
        if (value == BOOT_ID_JOURNAL_ERASED) {
            found_erased = true;
            allocation_index = i;
            break;
        }
    }
    if (found_erased) {
        for (i = allocation_index + 1U; i < BOOT_ID_JOURNAL_CELL_COUNT; ++i) {
            if (!storage->read_cell(storage->context, i, &value)
                || (value != BOOT_ID_JOURNAL_ERASED)) return false;
        }
        if (!storage->program_cell(storage->context, allocation_index,
                                   BOOT_ID_JOURNAL_COMMITTED)) return false;
        if (!storage->read_cell(storage->context, allocation_index, &value)
            || (value != BOOT_ID_JOURNAL_COMMITTED)) return false;
        *boot_id = (uint64_t)allocation_index + UINT64_C(1);
        return true;
    }
    return false;
}
