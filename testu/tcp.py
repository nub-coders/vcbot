#  Pyrogram - Telegram MTProto API Client Library for Python
#  Copyright (C) 2017-present Dan <https://github.com/delivrance>
#
#  This file is part of Pyrogram.
#
#  Pyrogram is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Lesser General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Pyrogram is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with Pyrogram.  If not, see <http://www.gnu.org/licenses/>.

# ... (Pyrogram's existing copyright and license header)

import asyncio
import ipaddress
import logging
import socket
from concurrent.futures import ThreadPoolExecutor
from typing import Tuple, Dict, TypedDict, Optional

import socks

log = logging.getLogger(__name__)

proxy_type_by_scheme: Dict[str, int] = {
    "SOCKS4": socks.SOCKS4,
    "SOCKS5": socks.SOCKS5,
    "HTTP": socks.HTTP,
}


class Proxy(TypedDict):
    scheme: str
    hostname: str
    port: int
    username: Optional[str]
    password: Optional[str]


class TCP:
    TIMEOUT = 15  # Increased timeout for connection attempts
    CONNECT_RETRIES = 3  # Number of connection retries
    RETRY_DELAY = 1  # Delay between retries in seconds

    def __init__(self, ipv6: bool, proxy: Proxy) -> None:
        self.ipv6 = ipv6
        self.proxy = proxy

        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self._address: Optional[Tuple[str, int]] = None  # Store the destination address

        self.lock = asyncio.Lock()
        self.loop = asyncio.get_event_loop()

    async def _resolve_proxy_hostname(self, hostname: str, port: int, family: int) -> Tuple[str, int]:
        """Resolve proxy hostname asynchronously."""
        try:
            infos = await self.loop.getaddrinfo(
                hostname, port,
                family=family,
                type=socket.SOCK_STREAM
            )
            _, _, _, _, sockaddr = infos[0]
            return sockaddr[0], sockaddr[1]
        except socket.gaierror as e:
            raise OSError(f"DNS resolution failed for proxy hostname {hostname}: {e}")

    async def _connect_via_proxy(self, destination: Tuple[str, int]) -> None:
        scheme = self.proxy.get("scheme", "").upper()
        proxy_type = proxy_type_by_scheme.get(scheme)
        if proxy_type is None:
            raise ValueError(f"Unsupported proxy scheme: {scheme}")

        proxy_host = self.proxy["hostname"]
        proxy_port = self.proxy["port"]
        username = self.proxy.get("username")
        password = self.proxy.get("password")

        # Determine proxy family based on resolved address
        try:
            ipaddress.ip_address(proxy_host)
            proxy_family = socket.AF_INET6 if ":" in proxy_host else socket.AF_INET
        except ValueError:
            # Hostname needs resolution
            proxy_family = socket.AF_INET6 if self.ipv6 else socket.AF_INET
            proxy_host, proxy_port = await self._resolve_proxy_hostname(proxy_host, proxy_port, proxy_family)

        sock = socks.socksocket(proxy_family)
        sock.set_proxy(
            proxy_type=proxy_type,
            addr=proxy_host,
            port=proxy_port,
            username=username,
            password=password
        )
        sock.settimeout(TCP.TIMEOUT)
        # Enable TCP keep-alive
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        # Platform-specific keep-alive settings (Linux)
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
        except AttributeError:
            pass  # Unsupported on this platform

        # Connect to destination via proxy
        with ThreadPoolExecutor() as executor:
            await self.loop.run_in_executor(executor, sock.connect, destination)

        sock.setblocking(False)
        self.reader, self.writer = await asyncio.open_connection(sock=sock)

    async def _connect_via_direct(self, destination: Tuple[str, int]) -> None:
        host, port = destination
        family = socket.AF_INET6 if self.ipv6 else socket.AF_INET
        self.reader, self.writer = await asyncio.open_connection(
            host=host,
            port=port,
            family=family
        )
        # Enable TCP keep-alive on direct connection
        sock = self.writer.transport.get_extra_info('socket')
        if sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            try:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
            except AttributeError:
                pass

    async def _connect(self, destination: Tuple[str, int]) -> None:
        if self.proxy:
            await self._connect_via_proxy(destination)
        else:
            await self._connect_via_direct(destination)

    async def connect(self, address: Tuple[str, int]) -> None:
        self._address = address
        for attempt in range(1, TCP.CONNECT_RETRIES + 1):
            try:
                await asyncio.wait_for(self._connect(address), TCP.TIMEOUT)
                log.info("Connected successfully on attempt %d", attempt)
                return
            except (TimeoutError, OSError, socks.ProxyError) as e:
                log.warning("Connection attempt %d/%d failed: %s", attempt, TCP.CONNECT_RETRIES, e)
                if attempt == TCP.CONNECT_RETRIES:
                    raise  # Re-raise the last error
                await asyncio.sleep(TCP.RETRY_DELAY)

    async def close(self) -> None:
        if not self.writer:
            return
        try:
            self.writer.close()
            await asyncio.wait_for(self.writer.wait_closed(), TCP.TIMEOUT)
        except Exception as e:
            log.info("Close exception: %s", e, exc_info=True)
        finally:
            self.reader = None
            self.writer = None

    async def send(self, data: bytes) -> None:
        if not self.writer or self.writer.is_closing():
            if not self._address:
                raise OSError("Cannot send data: not connected and no address available")
            log.info("Reconnecting to %s", self._address)
            await self.connect(self._address)

        async with self.lock:
            try:
                self.writer.write(data)
                await self.writer.drain()
            except (ConnectionResetError, BrokenPipeError) as e:
                log.info("Connection error: %s, reconnecting...", e)
                await self.close()
                await self.connect(self._address)
                await self.send(data)  # Retry sending after reconnection
            except Exception as e:
                log.error("Unexpected error during send: %s", e, exc_info=True)
                await self.close()
                raise OSError(e)

    async def recv(self, length: int = 0) -> Optional[bytes]:
        data = b""
        while len(data) < length:
            try:
                chunk = await asyncio.wait_for(
                    self.reader.read(length - len(data)),
                    TCP.TIMEOUT
                )
                if not chunk:
                    log.info("Connection closed by peer")
                    await self.close()
                    return None
                data += chunk
            except (asyncio.TimeoutError, ConnectionResetError, BrokenPipeError) as e:
                log.info("Receive error: %s, reconnecting...", e)
                await self.close()
                await self.connect(self._address)
                return await self.recv(length)  # Retry recv after reconnection
            except Exception as e:
                log.error("Unexpected error during recv: %s", e, exc_info=True)
                await self.close()
                raise
        return data
