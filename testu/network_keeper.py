# network_keeper.py
import asyncio
import aiohttp
import socket
import psutil
import platform
import subprocess
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

class NetworkKeepAlive:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.session = aiohttp.ClientSession()
        self.ping_targets = [
            "8.8.8.8",  # Google DNS
            "1.1.1.1"   # Cloudflare DNS
        ]
        
    async def keep_connection_alive(self):
        while True:
            try:
                # TCP keep-alive settings
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                
                if platform.system() == 'Linux':
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 5)
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
                
                # Ping check
                for target in self.ping_targets:
                    await self.ping_host(target)
                
            except Exception as e:
                print(f"Network check error: {str(e)}")
                
            await asyncio.sleep(60)

    async def ping_host(self, host: str) -> Optional[float]:
        try:
            if platform.system() == "Linux":
                cmd = f"ping -c 1 -W 2 {host}"
                result = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                await result.communicate()
                return result.returncode == 0
        except:
            return False

    async def cleanup(self):
        await self.session.close()
        self.executor.shutdown()

# Example usage
async def main():
    network_keeper = NetworkKeepAlive()
    try:
        await network_keeper.keep_connection_alive()
    finally:
        await network_keeper.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
