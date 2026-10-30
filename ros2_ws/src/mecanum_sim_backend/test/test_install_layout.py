"""External install checks for the backend package."""
from __future__ import annotations

import os
from pathlib import Path


def test_backend_share_and_plugin_are_inside_fresh_install() -> None:
    """Resolve the backend library and share within the fresh install."""
    base_value = os.environ.get('MECANUM_SIM_BACKEND_INSTALL_BASE')
    assert base_value, 'MECANUM_SIM_BACKEND_INSTALL_BASE_REQUIRED'
    base = Path(base_value).resolve()
    assert base.is_absolute() and base.is_dir()
    from ament_index_python.packages import (
        get_package_prefix, get_package_share_directory,
    )
    prefix = Path(get_package_prefix('mecanum_sim_backend')).resolve()
    share = Path(get_package_share_directory('mecanum_sim_backend')).resolve()
    assert prefix.is_relative_to(base)
    assert share.is_relative_to(base)
    assert (prefix / 'lib/libmecanum_sim_backend_system.so').is_file()
    assert (share / 'environment/mecanum_sim_backend.dsv').is_file()
