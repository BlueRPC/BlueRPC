from bluerpc.utils import get_net_ips, get_net_mac, get_version
from zeroconf import IPVersion
from zeroconf.asyncio import AsyncServiceInfo, AsyncZeroconf


async def start_discovery(
    bind_addr: str = "[::]:50052",
    name: str = "unknown",
    adapter_mac: str = "00:00:00:00:00:00",
) -> None:
    """
    Start the mDNS task for auto-discovery

    Args:
        bind_addr: the bind address passed to the worker
        name: the name of the worker
        encrypted: if the worker is running with encryption
        adapter_mac: mac address of the bluetooth adapter
    """
    aiozc = AsyncZeroconf(ip_version=IPVersion.All)
    await aiozc.async_register_service(
        AsyncServiceInfo(
            "_bluerpc._tcp.local.",
            f"{name}._bluerpc._tcp.local.",
            addresses=get_net_ips(),
            port=int(bind_addr[bind_addr.rfind(":") + 1:]),
            properties={
                "name": name,
                "version": get_version(),
                "uid": (adapter_mac == "00:00:00:00:00:00" or get_net_mac()).replace(
                    ":", ""
                ),
            },
        )
    )
