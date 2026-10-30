from setuptools import find_packages, setup


package_name = 'mecanum_nav_bringup'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test', 'test.*']),
    data_files=[
        (
            'share/ament_index/resource_index/packages',
            ['resource/' + package_name],
        ),
        ('share/' + package_name, ['package.xml']),
        (
            'share/' + package_name + '/config',
            [
                'config/navigation_v1_source_lock.template.yaml',
                'config/navigation_v1_static_bringup.template.yaml',
            ],
        ),
        (
            'share/' + package_name + '/config/bridge',
            [
                'config/bridge/sim_eval_lidar_scan_bridge.static.yaml',
                'config/bridge/sim_eval_lidar_scan_bridge.runtime.yaml',
                'config/bridge/sim_eval_scan_endpoint_probe.static.yaml',
                'config/bridge/sim_eval_clock.runtime.yaml',
                'config/bridge/sim_eval_cmd_vel.runtime.yaml',
            ],
        ),
        ('share/' + package_name + '/config/bridge',
            ['config/bridge/local_training.runtime.yaml']),
        ('share/' + package_name + '/config/gui',
            ['config/gui/local_training.config']),
        (
            'share/' + package_name + '/config/profiles',
            ['config/profiles/sim_eval_nav2_baseline.static.yaml'],
        ),
        (
            'share/' + package_name + '/config/localization',
            [
                'config/localization/'
                'navigation_v1_amcl_omni.static.template.yaml',
                'config/localization/amcl_omni.yaml',
            ],
        ),
        (
            'share/' + package_name + '/config/state_estimation',
            [
                'config/state_estimation/'
                'navigation_v1_ekf.static.template.yaml',
                'config/state_estimation/ekf_sim.yaml',
            ],
        ),
        (
            'share/' + package_name + '/config/lifecycle',
            [
                'config/lifecycle/'
                'navigation_v1_localization_lifecycle.static.template.yaml',
                'config/lifecycle/navigation_v1_startup.yaml',
                'config/lifecycle/sim_eval_nav2_baseline.runtime.yaml',
            ],
        ),
        (
            'share/' + package_name + '/config/navigation',
            [
                'config/navigation/nav2_baseline.yaml',
                'config/navigation/sim_eval_nav2_baseline.runtime.yaml',
            ],
        ),
        ('share/' + package_name + '/config/recording',
            ['config/recording/step07_research_qos.yaml']),
        (
            'share/' + package_name + '/config/remaps',
            ['config/remaps/navigation_v1.yaml'],
        ),
        (
            'share/' + package_name + '/launch',
            [
                'launch/sim_eval_lidar_scan_bridge.launch.py',
                'launch/navigation_v1_static_bringup.launch.py',
                'launch/navigation_v1.launch.py',
                'launch/navigation_v1_lifecycle.launch.py',
                'launch/sim_eval_tf_ekf_state_estimation.launch.py',
                'launch/sim_eval_nav2_baseline_system.launch.py',
                'launch/sim_train_local_training.launch.py',
            ],
        ),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Ha Van Vu',
    maintainer_email='havan.vu1302@gmail.com',
    description='Static fail-closed source scaffold for Navigation V1.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'sim_eval_scan_endpoint_probe = '
            'mecanum_nav_bringup.sim_eval_scan_endpoint_probe:main',
            'local_training_supervisor = '
            'mecanum_nav_bringup.local_training_process_supervisor:main',
        ]
    },
)
