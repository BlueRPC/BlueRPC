import asyncio
from zeroconf import IPVersion, ServiceStateChange, Zeroconf
from zeroconf.asyncio import (
    AsyncServiceBrowser,
    AsyncZeroconf,
)

run = True


def async_on_service_state_change(
    zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange
) -> None:
    assert state_change == ServiceStateChange.Added
    assert service_type == "_bluerpc._tcp.local."
    print(name)
    global run
    run = False


async def test_discovery():
    aiozc = AsyncZeroconf(ip_version=IPVersion.All)
    aiobrowser = AsyncServiceBrowser(
        aiozc.zeroconf,
        ["_bluerpc._tcp.local."],
        handlers=[async_on_service_state_change],
    )
    global run
    while run:
        await asyncio.sleep(1)
