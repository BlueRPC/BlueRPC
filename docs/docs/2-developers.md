# Developers

The main repository for the BlueRPC project is [bluerpc/bluerpc](https://github.com/BlueRPC/bluerpc) which contains:

- The [protocol](reference/proto/rpc.md) definition in `proto/`
- The [python worker](reference/python/bluerpc.cli.md) implementation in `python/`
- The [android worker](reference/android/app/com.bluerpc.worker/index.md) implementation in `android/`
- The project's tests scripts in `test/`
- The documentation in `docs/`

There is also an other repository for the Home-Assistant integration: [bluerpc/hass](https://github.com/BlueRPC/hass)

## Setting up the environment

The first step is to clone the [main repository](https://github.com/BlueRPC/bluerpc).

Then you need to install the dependencies, if you are on a debian-based distribution, you can just run `sudo make deps-debian` which will install all the system dependencies (except for android).
You can also run `make deps-python` to install the python dependencies.

Note that some python dependencies must be available in your path (like isort or black).

Here is a list of the required dependencies for each part of the project:

- Protobuf generation: [buf](https://buf.build/), `proto/requirements.txt`
- Android worker: Java 17, Android SDK
- Python worker: C compiler, `python/requirements.txt`
- Documentation: [protoc](https://grpc.io/docs/protoc-installation/), [protoc-gen-doc](https://github.com/pseudomuto/protoc-gen-doc/), `docs/requirements.txt`

## Development instructions

### Protocol

To validate the protobuf files, run `make proto-lint`

### Python Worker

First, run `make python-proto` to generate the gRPC stubs.

You can then lint the project with `make python-lint` and run it with `python run.py`.

To build a python package, run `make python-build`.

### Android Worker

It is recommanded to use Android Studio for development.

First, copy the proto files to the android project with `make android-proto`

Then you can build the app either from the IDE or with `make android-build`.

### Documentation

To build the documentation, you also need the worker's dependencies.

To build all the docs, run `make docs`, you can also run `make docs-serve` to start a local server.

The android documentation is generated from the javadoc comments with [dokka](https://kotlinlang.org/docs/dokka-introduction.html).

The python documentation is generated from the docstrings in [google format](https://google.github.io/styleguide/pyguide.html) using [lazydocs](https://github.com/ml-tooling/lazydocs).

## Testing

A few testing scripts are available for the project.

These scripts are running real bluetooth commands against bluetooth devices, currently there is a test for the miflora sensor and the switchbot bot. There is also a test for scanning and discovery.

You can run these tests with a command like this `pytest ./test_scan_grpc.py::test_scan --url="127.0.0.1:5052"`.

To test using encryption, use `make certs` to generate certificates and use `--keystore=../certs/client.pfx` for the test script and `certs/worker.pfx` for the worker.

The following parameters are supported:

- url: the ip:port of the worker
- mac: the mac address of the bluetooth device (for test_miflora_grpc and test_switchbot_grpc)
- keystore: path to a keystore for mTLS
