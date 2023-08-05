FILES = rpc/common.proto rpc/services.proto rpc/gatt.proto
PYTHON = python3
PIP = pip3

all: clean lint proto build certs
lint: proto-lint python-lint client-lint
proto: proto-lint python-proto test-proto client-proto android-proto
build: python-build docs-build android-build client-build
docs: docs-clean docs-gen docs-build
deps: deps-debian deps-python deps-finish
clean: python-clean test-clean docs-clean client-clean

FORCE:

# Dependencies installation

deps-debian:
	apt-get update
	apt-get install -y python3 python3-pip python3-venv clang-format curl protobuf-compiler
	curl -sSL "https://github.com/bufbuild/buf/releases/download/v1.12.0/buf-$(shell uname -s)-$(shell uname -m)" -o /usr/local/bin/buf
	chmod +x /usr/local/bin/buf
	curl -sSL "https://github.com/pseudomuto/protoc-gen-doc/releases/download/v1.5.1/protoc-gen-doc_1.5.1_linux_amd64.tar.gz" | tar -xz -C /usr/local/bin

deps-python:
	$(PIP) install -r python/requirements.txt
	$(PIP) install -r test/requirements.txt
	$(PIP) install -r docs/requirements.txt
	$(PIP) install black isort flake8 build twine

deps-finish:
	@echo deps installation finished
	@echo you might need to add /usr/local/bin and ~/.local/bin to your PATH

# Protobuf

proto-lint: proto/*
	buf lint proto --config=proto/buf.yaml

proto-docs: proto/*
	mkdir -p docs/docs/reference/proto
	protoc --proto_path=proto --doc_out=docs/docs/reference/proto --doc_opt=markdown,rpc.md $(FILES)

# Python Worker

python-proto: proto/*
	$(PYTHON) -m grpc_tools.protoc --python_out=python/bluerpc --grpc_python_out=python/bluerpc --proto_path=proto $(FILES)
	touch python/bluerpc/rpc/__init__.py
	find python/bluerpc/rpc -type f | xargs sed -i 's/from rpc import/from bluerpc.rpc import/g'

python-lint: python/*
	isort python/ --check --profile=black --skip=rpc
	black --check python/ --exclude=rpc
	flake8 python/ --ignore=E501,W503 --exclude=rpc

python-build: python-lint python-proto
	cd python && python3 -m build

python-docs: python/*
	mkdir -p docs/docs/reference/python
	$(PYTHON) docs/worker.py

python-clean: python/*
	rm -rf python/bluerpc/rpc

# Android Worker

android-proto: proto/*
	mkdir -p android/app/src/main/proto
	cp -R proto/* android/app/src/main/proto
	find android/app/src/main/proto -type f ! -name "*.proto" -exec rm {} \;

android-build: android-proto android/*
	cd android && ./gradlew build

android-docs:
	cd android && ./gradlew dokkaGfm
	cp -R android/app/build/dokka/gfm docs/docs/reference/android

# Client

client-proto: proto/*
	$(PYTHON) -m grpc_tools.protoc --python_out=client/bluerpc_client --grpc_python_out=client/bluerpc_client --proto_path=proto $(FILES)
	find client/bluerpc_client/rpc -type f | xargs sed -i 's/from rpc import/from . import/g'

client-lint: client/*
	isort client/bluerpc_client/ --check --profile=black --skip=rpc
	black --check client/bluerpc_client/ --exclude=rpc
	flake8 client/bluerpc_client/ --ignore=E501,W503 --exclude=rpc,__init__.py

client-build: client-lint client-proto
	cd client && python3 -m build

client-docs: client/*
	mkdir -p docs/docs/reference/client
	$(PYTHON) docs/client.py

client-clean: client/*
	rm -rf client/bluerpc_client/rpc

# Tests

test-proto: proto/*
	$(PYTHON) -m grpc_tools.protoc --python_out=test --grpc_python_out=test --proto_path=proto $(FILES)

test-clean: test/*
	rm -rf test/rpc

# Docs

docs-gen: proto-docs python-docs android-docs client-docs

docs-serve:
	cd docs && mkdocs serve --strict

docs-build: docs-clean docs-gen
	cd docs && mkdocs build --strict

docs-clean: docs/*
	rm -rf docs/docs/reference
	rm -rf docs/site

# Testing certificates for secure gRPC connections (mTLS)

certs: cert-clean cert-ca cert-worker cert-client

cert-ca:
	cd certs && openssl req -x509 -newkey rsa:4096 -days 10000 -subj "/O=BlueRPC/OU=BlueRPC/CN=*" -nodes -keyout ca-key.pem -out ca-cert.pem

cert-worker:
	openssl req -newkey rsa:4096 -nodes -keyout certs/worker-key.pem -out certs/worker-req.pem -subj "/O=BlueRPC/OU=BlueRPC/CN=localhost"
	openssl x509 -req -in certs/worker-req.pem -days 10000 -CA certs/ca-cert.pem -CAkey certs/ca-key.pem -CAcreateserial -out certs/worker-cert.pem -extfile certs/worker-san.conf
	openssl pkcs12 -export -nodes -inkey certs/worker-key.pem -in certs/worker-cert.pem -caname ca -certfile certs/ca-cert.pem -passout pass: -out certs/worker.pfx
	rm certs/worker-*.pem

cert-client:
	openssl req -newkey rsa:4096 -nodes -keyout certs/client-key.pem -out certs/client-req.pem -subj "/O=BlueRPC/OU=BlueRPC/CN=*"
	openssl x509 -req -in certs/client-req.pem -days 10000 -CA certs/ca-cert.pem -CAkey certs/ca-key.pem -CAcreateserial -out certs/client-cert.pem
	openssl pkcs12 -export -nodes -inkey certs/client-key.pem -in certs/client-cert.pem -caname ca -certfile certs/ca-cert.pem -passout pass: -out certs/client.pfx
	rm certs/client-*.pem

cert-worker-clean:
	rm certs/worker*

cert-worker-new: cert-worker-clean cert-worker

cert-clean: FORCE
	rm -rf certs/*.pem certs/*.srl certs/*.pfx
