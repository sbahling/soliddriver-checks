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
    description=("Check RPMs and Drivers information"),
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
    #     '': ['*.conf', '*.sh']
    # },
    # data_files=[
    #     ('config', ['src/soliddriver_checks/config/soliddriver-checks.conf'])
    # ],
    python_requires=">=3.6",
    install_requires=[
        'click',
        'paramiko',
        'pdfkit',
        'dominate',
        'rich',
        'jinja2',
        'scp'
    ],
    entry_points={
        'console_scripts': [
            'soliddriver-checks=soliddriver_checks.cli:run'
        ]
    },
)
