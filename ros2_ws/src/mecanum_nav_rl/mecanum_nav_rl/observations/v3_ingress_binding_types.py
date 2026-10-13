"""Dependency-injected message bindings for nonexecuting OIC V3 adapters."""

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class IngressMessageBinding:
    """Upstream-verified binding metadata; it is not a runtime source pin."""

    expected_message_class: type
    expected_topic: str | None
    expected_type: str
    expected_frame_id: str
    converter: Callable[[object], object] | None
    expected_child_frame_id: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.expected_message_class, type):
            raise TypeError("expected_message_class must be a class")
        if self.expected_topic is not None and (
            type(self.expected_topic) is not str or not self.expected_topic
        ):
            raise TypeError("expected_topic must be None or a non-empty exact str")
        if type(self.expected_type) is not str or not self.expected_type:
            raise TypeError("expected_type must be a non-empty exact str")
        if type(self.expected_frame_id) is not str or not self.expected_frame_id:
            raise TypeError("expected_frame_id must be a non-empty exact str")
        if self.expected_child_frame_id is not None and (
            type(self.expected_child_frame_id) is not str
            or not self.expected_child_frame_id
        ):
            raise TypeError(
                "expected_child_frame_id must be None or a non-empty exact str"
            )
        if self.converter is not None and not callable(self.converter):
            raise TypeError("converter must be callable or None")
