from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="bluerpc_client",
    packages=find_packages(),
    version="0.0.0",
    author="drosocode",
    license="MIT",
    description="Python BlueRPC Client",
    url="https://github.com/BlueRPC/BlueRPC",
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "async_timeout",
        "bleak>=0.20",
        "cryptography>=41.0",
        "grpcio>=1.52",
        "protobuf>=4.23",
        "zeroconf",
    ],
    python_requires=">=3.8",
    project_urls={
        "Documentation": "https://bluerpc.github.io/",
        "Source": "https://github.com/BlueRPC/BlueRPC/tree/main/client",
    },
)
