from lazydocs import generate_docs
import sys
import os

sys.path.append(os.path.join(os.getcwd(), "python"))
generate_docs(
    ["bluerpc"],
    output_path="./docs/docs/reference/python",
    ignored_modules=["bluerpc.rpc"],
    src_base_url="https://github.com/BlueRPC/BlueRPC/blob/main/python/",
    src_root_path="python/",
    remove_package_prefix=True
)
