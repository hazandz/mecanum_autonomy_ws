from setuptools import find_packages, setup


package_name = "mecanum_nav_rl"


setup(
    name=package_name,
    version="0.1.0",

    packages=find_packages(
        exclude=[
            "test",
            "test.*",
        ]
    ),

    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/" + package_name],
        ),
        (
            "share/" + package_name,
            ["package.xml"],
        ),
    ],

    install_requires=[
        "setuptools",
    ],

    zip_safe=True,

    maintainer="Ha Van Vu",
    maintainer_email="havan.vu1302@gmail.com",

    description=(
        "ROS 2 package for Mecanum navigation using deep reinforcement "
        "learning, simulation, evaluation, deployment, and runtime safety."
    ),

    license="Apache-2.0",

    tests_require=[
        "pytest",
    ],

    entry_points={
        "console_scripts": [],
    },
)
