from setuptools import find_packages, setup


package_name = 'mecanum_base_bridge'


setup(
    name=package_name,
    version='0.2.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml', 'README.md']),
        ('share/' + package_name + '/config', [
            'config/sim_eval_wheel_imu_ingress.static.yaml',
            'config/sim_eval_wheel_imu_runtime_source.yaml',
        ]),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Hazan',
    maintainer_email='hazard@example.com',
    description='UART codec utilities and bounded sim_eval wheel/IMU ingress.',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'sim_eval_wheel_imu_ingress = mecanum_base_bridge.sim_eval_wheel_imu_ingress_node:main',
        ],
    },
)
