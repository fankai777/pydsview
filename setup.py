from setuptools import setup, find_packages

setup(
    name="pydsview",
    version="0.1.0",
    packages=find_packages(),
    package_data={
        "pydsview": ["*.so", "*.so.*", "*.dll"],
    },
)
