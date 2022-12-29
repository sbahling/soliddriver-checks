from setuptools import setup, find_packages
import codecs
import os.path


def read(rel_path):
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, rel_path), 'r') as fp:
        return fp.read()


def get_version(rel_path):
    for line in read(rel_path).splitlines():
        if line.startswith('__VERSION__'):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError("Unable to find version string.")


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()


setup(
    name="soliddriver-checks",
    version=get_version("src/soliddriver_checks/version.py"),
    author="Hui-Zhi Zhao",
    author_email="hui.zhi.zhao@suse.com",
    description=("Check Kernel Module Package and Kernel Module information"),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/SUSE/soliddriver-checks",
    project_urls={
        "Bug Tracker": "https://github.com/SUSE/soliddriver-checks/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
    python_requires=">=3.7",
    install_requires=[
        'bottle>=0.12.23',
        'click>=8.1.3',
        'dominate>=2.7.0',
        'Jinja2>=3.1.2',
        'openpyxl>=3.0.10',
        'pandas>=1.5.2',
        'rich>=12.6.0',
        'setuptools>=65.4.1',
        'requests>=2.28.1'
    ],
    entry_points={
        'console_scripts': [
            'soliddriver-checks=soliddriver_checks.cli.cli:run',
            'soliddriver-checks-service=soliddriver_checks.service.service:run_as_service'
        ]
    },
)
