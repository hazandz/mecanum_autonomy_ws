import pytest

from mecanum_base_bridge.cobs_codec import CobsDecodeError, cobs_decode, cobs_encode


@pytest.mark.parametrize('payload', (b'normal payload', b'zero\x00inside\x00payload', b''))
def test_cobs_round_trip(payload: bytes) -> None:
    assert cobs_decode(cobs_encode(payload)) == payload


def test_cobs_empty_payload_has_standard_encoding() -> None:
    assert cobs_encode(b'') == b'\x01'


@pytest.mark.parametrize('encoded', (b'', b'\x00', b'\x02'))
def test_malformed_cobs_is_rejected_safely(encoded: bytes) -> None:
    with pytest.raises(CobsDecodeError):
        cobs_decode(encoded)
