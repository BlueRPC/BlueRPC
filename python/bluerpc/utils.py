import asyncio
import logging
import os
import platform
import re
from importlib.metadata import version
from pathlib import Path

import netifaces
from bluetooth_adapters import (
    ADAPTER_ADDRESS,
    DEFAULT_ADDRESS,
    AdapterDetails,
    get_adapters,
)

_LOGGER = logging.getLogger(__name__)


def validate_mac(addr: str) -> bool:
    """
    Mac address validation regex

    Args:
        addr: the mac address (with colons)
    Returns:
        True if this is a valid mac address
    """
    return bool(
        re.match("^([0-9a-fA-F][0-9a-fA-F]:){5}([0-9a-fA-F][0-9a-fA-F])$", addr)
    )


def validate_uuid(u: str) -> bool:
    """
    UUID validation regex

    Args:
        addr: the uuid
    Returns:
        True if this is a valid UUID
    """
    return bool(
        re.match(
            "[0-9a-f]{8}-[0-9a-f]{4}-[0-5][0-9a-f]{3}-[089ab][0-9a-f]{3}-[0-9a-f]{12}",
            u,
        )
    )


def get_appdata_dir() -> Path:
    """
    Get the path to a bluerpc appdata folder

    Returns:
        a path object to this folder
    """
    if platform.system() == "Windows":
        p = os.getenv("LOCALAPPDATA")
    elif platform.system() == "Darwin":
        p = "~/Library/Application Support"
    else:
        p = os.getenv("XDG_DATA_HOME", "~/.local/share")

    path = Path(p).expanduser().joinpath("bluerpc")
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_version() -> str:
    """
    Helper to get the current version of our package

    Returns:
        the version if found, else 0.0.0
    """
    try:
        return version("bluerpc")
    except Exception:
        return "0.0.0"


def get_kwargs(adapter: str = None) -> dict[str, str]:
    """
    Get kwargs for bleak scanner/client

    Args:
        adapter: adapter identifier
    Returns:
        an array of kwargs
    """
    kwargs = {}
    plt = platform.system()
    if plt == "Darwin":
        # use mac address on mac os
        kwargs["cb"] = {"use_bdaddr": True}
    if adapter:
        if plt == "Linux":
            kwargs["adapter"] = adapter
        else:
            _LOGGER.warning(f"unable to select adapter on this platform: {plt}")
    return kwargs


def list_adapters() -> dict[str, AdapterDetails]:
    """
    List available bluetooth adapters

    Returns:
        a dict of adapters and their details
    """
    adp = get_adapters()
    loop = asyncio.new_event_loop()
    loop.run_until_complete(adp.refresh())
    loop.close()
    return adp.adapters


def find_adapter_by_address(address: str) -> str | None:
    """
    Find an adapter from a mac address

    Args:
        address: the mac address of the adapter
    Returns:
        the adapter identifier
    """
    for adapter, details in list_adapters().items():
        if details[ADAPTER_ADDRESS] == address:
            return adapter
    _LOGGER.warning(f"adapter with address {address} was not found")
    return None


def list_adapters_mac() -> str:
    """
    List adapters identifiables by mac address

    Returns:
        a list of adapter mac address
    """
    adapters = []
    for details in list_adapters().values():
        if details[ADAPTER_ADDRESS] != DEFAULT_ADDRESS:
            adapters.append(details[ADAPTER_ADDRESS])
    return adapters


def get_net_mac() -> str:
    """
    Get mac address of the default network interface (or the first one if no default)

    Returns:
        a mac address
    """
    gws = netifaces.gateways()

    def get_mac(ifname: dict):
        x = netifaces.ifaddresses(ifname)
        if netifaces.AF_LINK in x:
            for i in x[netifaces.AF_LINK]:
                if "addr" in i:
                    return i["addr"]
        return None

    if "default" in gws:
        if x := get_mac(list(gws["default"].values())[0][1]):
            return x

    for k, v in gws.items():
        if k != "default":
            if x := get_mac(v[0][1]):
                return x

    return None


def get_net_ips(v6e=True) -> str:
    """
    Get ip addresses of the network interfaces

    Args:
        v6e: return also IPv6 addresses
    Returns:
        a list of ip addresses (the first is the one of the default interface)
    """
    ips = []
    gws = netifaces.gateways()

    def get_ip(ifname: str):
        v4 = None
        v6 = None
        x = netifaces.ifaddresses(ifname)
        if netifaces.AF_INET in x:
            for i in x[netifaces.AF_INET]:
                if "addr" in i:
                    v4 = i["addr"]
                    break
        if netifaces.AF_INET6 in x:
            for i in x[netifaces.AF_INET]:
                if "addr" in i:
                    v6 = i["addr"]
                    break

        return (v4, v6)

    if "default" in gws:
        v4, v6 = get_ip(list(gws["default"].values())[0][1])
        if v4:
            ips.append(v4)
        if v6e and v6:
            ips.append(v6)

    for k, v in gws.items():
        if k != "default":
            v4, v6 = get_ip(v[0][1])
            if v4:
                ips.append(v4)
            if v6e and v6:
                ips.append(v6)

    return ips
