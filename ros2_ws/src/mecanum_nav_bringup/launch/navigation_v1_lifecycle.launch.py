"""Static fail-closed lifecycle manifest for the Navigation V1 baseline."""

MAP_YAML_FILENAME = "__PROFILE_RESOLVED_ARTIFACT_YAML_REQUIRED__"


def generate_launch_description():
    if MAP_YAML_FILENAME == "__PROFILE_RESOLVED_ARTIFACT_YAML_REQUIRED__":
        raise RuntimeError(
            "Navigation V1 map binding is unresolved; runtime graph creation is not authorized."
        )
    raise RuntimeError("Navigation V1 lifecycle runtime graph creation is not authorized.")
