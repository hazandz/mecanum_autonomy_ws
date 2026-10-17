"""Offline parser for multi-document IMU samples captured from ROS CLI output."""

from collections.abc import Mapping

import yaml


class ImuEvidenceParseError(ValueError):
    """Raised when a raw IMU transcript is not exactly one message mapping."""


def parse_single_imu_message(transcript):
    """Parse exactly one mapping while tolerating YAML document separators.

    ROS CLI output can contain explicit YAML document boundaries and trailing
    empty documents. The parser deliberately uses ``safe_load_all`` and
    rejects zero or multiple non-empty mappings.
    """
    if isinstance(transcript, bytes):
        try:
            transcript = transcript.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ImuEvidenceParseError("transcript is not valid UTF-8") from exc
    if not isinstance(transcript, str):
        raise ImuEvidenceParseError("transcript must be str or bytes")
    try:
        documents = list(yaml.safe_load_all(transcript))
    except yaml.YAMLError as exc:
        raise ImuEvidenceParseError("transcript is malformed YAML") from exc
    mappings = [document for document in documents if isinstance(document, Mapping)]
    if len(mappings) != 1:
        raise ImuEvidenceParseError(
            f"expected exactly one message mapping, found {len(mappings)}"
        )
    if any(document is not None and not isinstance(document, Mapping) for document in documents):
        raise ImuEvidenceParseError("transcript contains a non-mapping document")
    return dict(mappings[0])
