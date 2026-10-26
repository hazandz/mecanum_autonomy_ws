#ifndef MECANUM_BOOT_ID_H
#define MECANUM_BOOT_ID_H

#include <stdbool.h>
#include <stdint.h>

#define BOOT_ID_JOURNAL_CELL_COUNT UINT32_C(32768)
#define BOOT_ID_JOURNAL_ERASED UINT32_C(0xFFFFFFFF)
#define BOOT_ID_JOURNAL_COMMITTED UINT32_C(0x00000000)

typedef bool (*boot_id_read_cell_fn)(void *context, uint32_t index, uint32_t *value);
typedef bool (*boot_id_program_cell_fn)(void *context, uint32_t index, uint32_t value);
typedef struct {
    void *context;
    boot_id_read_cell_fn read_cell;
    boot_id_program_cell_fn program_cell;
} boot_id_storage_t;

bool boot_id_allocate(const boot_id_storage_t *storage, uint64_t *boot_id);
bool boot_id_allocate_hal(uint64_t *boot_id);

#endif
