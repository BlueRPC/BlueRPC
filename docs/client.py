from lazydocs import generate_docs
import sys
import os

sys.path.append(os.path.join(os.getcwd(), "client"))
generate_docs(
    ["bluerpc_client"],
    output_path="./docs/docs/reference/client",
    ignored_modules=["bluerpc_client.rpc"],
    src_base_url="https://github.com/BlueRPC/BlueRPC/blob/main/client/",
    src_root_path="client/",
    remove_package_prefix=True
)
