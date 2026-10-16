from setuptools import find_packages, setup


package_name = "mecanum_nav_bringup"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test", "test.*"]),
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/" + package_name],
        ),
        ("share/" + package_name, ["package.xml"]),
        (
            "share/" + package_name + "/config",
            [
                "config/navigation_v1_source_lock.template.yaml",
                "config/navigation_v1_static_bringup.template.yaml",
            ],
        ),
        (
            "share/" + package_name + "/config/bridge",
            ["config/bridge/sim_eval_lidar_scan_bridge.static.yaml"],
        ),
        (
            "share/" + package_name + "/config/profiles",
            ["config/profiles/sim_eval_nav2_baseline.static.yaml"],
        ),
        (
            "share/" + package_name + "/config/localization",
            [
                "config/localization/navigation_v1_amcl_omni.static.template.yaml",
                "config/localization/amcl_omni.yaml",
            ],
        ),
        (
            "share/" + package_name + "/config/state_estimation",
            [
                "config/state_estimation/navigation_v1_ekf.static.template.yaml",
                "config/state_estimation/ekf_sim.yaml",
            ],
        ),
        (
            "share/" + package_name + "/config/lifecycle",
            [
                "config/lifecycle/navigation_v1_localization_lifecycle.static.template.yaml",
                "config/lifecycle/navigation_v1_startup.yaml",
            ],
        ),
        (
            "share/" + package_name + "/config/navigation",
            ["config/navigation/nav2_baseline.yaml"],
        ),
        (
            "share/" + package_name + "/config/remaps",
            ["config/remaps/navigation_v1.yaml"],
        ),
        (
            "share/" + package_name + "/launch",
            [
                "launch/navigation_v1_static_bringup.launch.py",
                "launch/navigation_v1.launch.py",
                "launch/navigation_v1_lifecycle.launch.py",
            ],
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Ha Van Vu",
    maintainer_email="havan.vu1302@gmail.com",
    description="Static fail-closed source scaffold for Navigation V1.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={"console_scripts": []},
)
