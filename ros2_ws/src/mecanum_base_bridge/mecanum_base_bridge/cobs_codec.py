"""COBS codec for bounded Python byte strings."""


class CobsDecodeError(ValueError):
    """Raised when a COBS byte sequence is malformed."""


def cobs_encode(data: bytes) -> bytes:
    """Encode data with COBS, excluding the trailing delimiter."""
    output = bytearray()
    code_index = 0
    output.append(0)
    code = 1
    for value in data:
        if value == 0:
            output[code_index] = code
            code_index = len(output)
            output.append(0)
            code = 1
        else:
            output.append(value)
            code += 1
            if code == 0xFF:
                output[code_index] = code
                code_index = len(output)
                output.append(0)
                code = 1
    output[code_index] = code
    return bytes(output)


def cobs_decode(encoded: bytes) -> bytes:
    """Decode a COBS payload without its trailing wire delimiter."""
    if not encoded:
        raise CobsDecodeError('COBS payload is empty')
    output = bytearray()
    index = 0
    while index < len(encoded):
        code = encoded[index]
        if code == 0:
            raise CobsDecodeError('zero byte inside COBS payload')
        index += 1
        copy_length = code - 1
        if index + copy_length > len(encoded):
            raise CobsDecodeError('COBS code exceeds available input')
        output.extend(encoded[index:index + copy_length])
        index += copy_length
        if code != 0xFF and index < len(encoded):
            output.append(0)
    return bytes(output)
