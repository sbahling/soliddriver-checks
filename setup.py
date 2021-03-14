import os
from setuptools import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "solid_driver_checks",
    version = "0.0.4",
    author = "Hui-Zhi Zhao",
    author_email = "hui.zhi.zhao@suse.com",
    description = ("Check RPM(s) and Drivers(s) information"),
    license = "GPL 2.0",
    keywords = "RPM, Driver, check",
    url = "http://packages.python.org/solid-driver-checks",
    packages=['solid_driver_checks', 'tests'],
    long_description=read('README.md'),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
        "License :: OSI Approved :: GPL 2.0 License",
    ],
)
