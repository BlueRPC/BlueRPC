from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="bluerpc",
    packages=find_packages(),
    version="0.0.0",
    author="drosocode",
    license="MIT",
    description="Python BlueRPC Worker",
    url="https://github.com/BlueRPC/BlueRPC",
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "bleak",
        "bluetooth-adapters",
        "cryptography",
        "grpcio",
        "grpc-interceptor",
        "protobuf",
        "netifaces",
        "zeroconf",
    ],
    python_requires=">=3.10",
    project_urls={
        "Documentation": "https://bluerpc.github.io/",
        "Source": "https://github.com/BlueRPC/BlueRPC/tree/main/python",
    },
    entry_points={"console_scripts": ["bluerpc=bluerpc.cli:run"]},
)
