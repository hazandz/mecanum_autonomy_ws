from setuptools import setup
import os
from glob import glob

package_name = 'ROBOT_URDF_final_description'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # Copy các file cần thiết sang install
        (os.path.join('share', package_name, 'launch'), [entry for entry in glob('launch/*') if os.path.isfile(entry)]),
        (os.path.join('share', package_name, 'urdf'), [
            'urdf/ROBOT_URDF_final.xacro', 'urdf/ROBOT_URDF_final.gazebo',
            'urdf/ROBOT_URDF_final.ros2control', 'urdf/materials.xacro',
            'urdf/mecanum_b2_static.urdf',
        ]),
        (os.path.join('share', package_name, 'meshes'), glob('meshes/*')),
        (os.path.join('share', package_name, 'models', 'ROBOT_URDF_final'), glob('models/ROBOT_URDF_final/*')),
        (
            os.path.join('share', package_name, 'worlds'),
            ['worlds/b2_training_arena.sdf'],
        ),
        (os.path.join('share', package_name, 'models', 'mecanum_b2'), [
            'models/mecanum_b2/model.config', 'models/mecanum_b2/model.sdf']),
        (os.path.join('share', package_name, 'models', 'b2_contact_probe'), [
            'models/b2_contact_probe/model.config',
            'models/b2_contact_probe/model.sdf',
        ]),
        (os.path.join('share', package_name, 'manifests', 'b2'), [
            '../../../artifacts/simulation/roadmap_b_b2/asset_manifest.json']),
        (os.path.join('share', package_name, 'config'), glob('config/*')),
        (os.path.join('share', package_name, 'maps'), glob('maps/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='author',
    maintainer_email='todo@todo.com',
    description='The ' + package_name + ' package',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
        ],
    },
)
