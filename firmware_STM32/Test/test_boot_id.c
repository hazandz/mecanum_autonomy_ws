#include "boot_id.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

typedef struct { uint32_t cells[BOOT_ID_JOURNAL_CELL_COUNT]; bool fail_program; bool corrupt_readback; } fake_flash_t;
static bool read_cell(void *p, uint32_t i, uint32_t *v)
{
    fake_flash_t *f = p;
    *v = f->cells[i];
    if (f->corrupt_readback && f->cells[i] == 0U) { *v = 1U; f->corrupt_readback = false; }
    return true;
}
static bool program_cell(void *p, uint32_t i, uint32_t v)
{
    fake_flash_t *f = p;
    if (f->fail_program) return false;
    f->cells[i] &= v;
    return true;
}
static boot_id_storage_t storage(fake_flash_t *f)
{ boot_id_storage_t s = {f, read_cell, program_cell}; return s; }

int main(void)
{
    static fake_flash_t flash;
    boot_id_storage_t s;
    uint64_t id = 99U;
    memset(&flash, 0xff, sizeof(flash));
    flash.fail_program = false; flash.corrupt_readback = false;
    s = storage(&flash);
    assert(boot_id_allocate(&s, &id) && id == 1U);
    assert(boot_id_allocate(&s, &id) && id == 2U);
    flash.cells[2] = UINT32_C(0xFFFFFF00); /* torn/non-erased cell is consumed */
    assert(boot_id_allocate(&s, &id) && id == 4U);
    flash.cells[5] = 0U; /* non-erased after erased suffix is a hole */
    assert(!boot_id_allocate(&s, &id));
    memset(&flash, 0, sizeof(flash));
    assert(!boot_id_allocate(&s, &id)); /* full journal */
    memset(&flash, 0xff, sizeof(flash));
    flash.fail_program = false; flash.corrupt_readback = false;
    flash.fail_program = true;
    assert(!boot_id_allocate(&s, &id));
    flash.fail_program = false;
    flash.corrupt_readback = true;
    assert(!boot_id_allocate(&s, &id));
    assert(boot_id_allocate(&s, &id) && id == 2U); /* dirty consumed cell skipped */
    puts("Boot ID tests passed: scan, torn cell, hole/full, program/readback failure.");
    return 0;
}
