"""Setup configuration for socket-load-test package."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="socket-load-test",
    version="0.1.0",
    author="Socket Security",
    description="Distributed load testing for Socket Registry Firewall",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Testing",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "paramiko>=2.11.0",
        "pyyaml>=6.0",
        "jinja2>=3.0.0",
        "kubernetes>=25.0.0",
        "google-cloud-container>=2.17.0",
        "requests>=2.28.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-mock>=3.10.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "pylint>=2.15.0",
            "mypy>=0.990",
        ],
    },
    entry_points={
        "console_scripts": [
            "socket-load-test=socket_load_test.cli:cli",
        ],
    },
    include_package_data=True,
)
