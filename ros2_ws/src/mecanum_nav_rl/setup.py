from setuptools import find_packages, setup


package_name = "mecanum_nav_rl"


_V3_CONFIG_DATA_FILES = [
    (
        "share/mecanum_nav_rl/config/v3",
        [
            "config/v3/base.yaml",
            "config/v3/topics.yaml",
            "config/v3/qos.yaml",
            "config/v3/frames.yaml",
            "config/v3/acceptance.yaml",
            "config/v3/measurements.yaml",
        ],
    ),
    (
        "share/mecanum_nav_rl/config/v3/profiles",
        [
            "config/v3/profiles/sim_train.yaml",
            "config/v3/profiles/sim_eval.yaml",
            "config/v3/profiles/deploy_sim.yaml",
            "config/v3/profiles/deploy_real.yaml",
        ],
    ),
    (
        "share/mecanum_nav_rl/config/v3/modes",
        [
            "config/v3/modes/local_training.yaml",
            "config/v3/modes/mapping.yaml",
            "config/v3/modes/nav2_baseline.yaml",
            "config/v3/modes/hybrid_ai_local.yaml",
        ],
    ),
    (
        "share/mecanum_nav_rl/config/v3/algorithms",
        ["config/v3/algorithms/ppo.yaml"],
    ),
]


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
        *_V3_CONFIG_DATA_FILES,
    ],

    install_requires=[
        "setuptools",
        "pydantic==2.10.6",
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
