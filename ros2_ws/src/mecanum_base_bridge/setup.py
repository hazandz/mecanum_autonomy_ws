from setuptools import find_packages, setup


package_name = 'mecanum_base_bridge'


setup(
    name=package_name,
    version='0.3.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml', 'README.md']),
        ('share/' + package_name + '/config', [
            'config/sim_eval_wheel_imu_ingress.static.yaml',
            'config/sim_eval_wheel_imu_runtime_source.yaml',
            'config/uart_bridge.yaml',
        ]),
        ('share/' + package_name + '/config/bridge', [
            'config/bridge/sim_eval_wheel_imu_ingress.runtime.yaml',
        ]),
        ('share/' + package_name + '/launch', [
            'launch/sim_eval_wheel_imu_ingress.launch.py',
        ]),
    ],
    install_requires=['setuptools', 'pyserial==3.5', 'PyYAML>=6,<7', 'rfc8785==0.1.4'],
    extras_require={'hardware-config': ['PyYAML>=6,<7', 'rfc8785==0.1.4']},
    zip_safe=True,
    maintainer='Hazan',
    maintainer_email='hazard@example.com',
    description='Mecanum base transport components and offline-only sim_eval wheel/IMU ingress source.',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'sim_eval_wheel_imu_ingress = mecanum_base_bridge.sim_eval_wheel_imu_ingress_node:main',
            'mecanum_uart_bridge = mecanum_base_bridge.bridge_node:main',
        ],
    },
)
