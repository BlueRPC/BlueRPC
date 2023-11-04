FROM alpine:latest

RUN apk update && apk add build-base python3 py3-pip python3-dev libffi-dev openssl-dev rust cargo && pip install bluerpc
CMD ["bluerpc"]
