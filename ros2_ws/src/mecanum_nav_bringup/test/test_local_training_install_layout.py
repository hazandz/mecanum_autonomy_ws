"""Static exact data-file inventory and external install layout checks."""
import ast
import os
from pathlib import Path


def _literal(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name) and node.id == 'package_name':
        return 'mecanum_nav_bringup'
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _literal(node.left) + _literal(node.right)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == 'join'
    ):
        return os.path.join(*(_literal(value) for value in node.args))
    if isinstance(node, ast.ListComp):
        return []
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_literal(value) for value in node.elts]
    raise AssertionError(
        f'setup.py data-files expression is not literal: {ast.dump(node)}'
    )


def test_bringup_setup_declares_b2_runtime_assets_explicitly():
    """Check the explicit package inventory and installed copies."""
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / 'setup.py').read_text(encoding='utf-8'))
    setup_call = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, 'id', None) == 'setup'
    )
    kwargs = {item.arg: item.value for item in setup_call.keywords}
    data_files = _literal(kwargs['data_files'])
    entry_points = ast.literal_eval(kwargs['entry_points'])
    sources = [source for _, values in data_files for source in values]
    assert sources.count('launch/sim_train_local_training.launch.py') == 1
    assert sources.count('config/bridge/local_training.runtime.yaml') == 1
    assert sources.count('config/gui/local_training.config') == 1
    assert (
        'local_training_supervisor = '
        'mecanum_nav_bringup.local_training_process_supervisor:main'
        in entry_points['console_scripts']
    )
    assert all((root / source).is_file() for source in sources)

    raw_base = os.environ.get('MECANUM_NAV_BRINGUP_INSTALL_BASE')
    assert raw_base, 'MECANUM_NAV_BRINGUP_INSTALL_BASE_REQUIRED'
    from ament_index_python.packages import (
        get_package_prefix, get_package_share_directory,
    )
    base = Path(raw_base).resolve(strict=True)
    prefix = Path(
        get_package_prefix('mecanum_nav_bringup'),
    ).resolve(strict=True)
    share = Path(
        get_package_share_directory('mecanum_nav_bringup'),
    ).resolve(strict=True)
    assert prefix.is_relative_to(base) and share.is_relative_to(base)
    for source, installed in (
        (
            'launch/sim_train_local_training.launch.py',
            'launch/sim_train_local_training.launch.py',
        ),
        (
            'config/bridge/local_training.runtime.yaml',
            'config/bridge/local_training.runtime.yaml',
        ),
        (
            'config/gui/local_training.config',
            'config/gui/local_training.config',
        ),
    ):
        assert (share / installed).read_bytes() == (root / source).read_bytes()
    executable = prefix / 'lib/mecanum_nav_bringup/local_training_supervisor'
    assert executable.is_file()
