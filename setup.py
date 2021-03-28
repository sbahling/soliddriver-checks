from setuptools import setup, find_packages


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="soliddriver-checks",
    version="0.0.17",
    author="Hui-Zhi Zhao",
    author_email="hui.zhi.zhao@suse.com",
    description=("Check RPM(s) and Drivers information"),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/suse/soliddriver-checks",
    project_urls={
        "Bug Tracker": "https://github.com/suse/soliddriver-checks/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
    # package_data={
    #     '': ['*.conf']
    # },
    # data_files=[
    #     ('config', ['src/soliddriver_checks/config/soliddriver-checks.conf'])
    # ],
    python_requires=">=3.6",
    install_requires=[
        'click',
    ],
    entry_points={
        'console_scripts': [
            'soliddriver-checks=soliddriver_checks:run'
        ]
    },
)
