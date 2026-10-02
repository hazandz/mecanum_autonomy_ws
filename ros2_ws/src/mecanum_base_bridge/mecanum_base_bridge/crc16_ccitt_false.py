"""CRC-16/CCITT-FALSE used by the UART v1 raw frame."""


def crc16_ccitt_false(data: bytes) -> int:
    """Return CRC-16/CCITT-FALSE for data."""
    crc = 0xFFFF
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc
