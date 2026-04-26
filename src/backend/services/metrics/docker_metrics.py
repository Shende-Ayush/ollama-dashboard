import asyncio
import os

import httpx
import psutil


class DockerMetricsService:
    def __init__(self) -> None:
        self.container_name = os.getenv("OLLAMA_CONTAINER_NAME", "ollama")

    async def get_container_stats(self) -> dict:
        docker_stats_url = os.getenv("DOCKER_STATS_URL", "")
        if docker_stats_url:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(f"{docker_stats_url}/containers/{self.container_name}/stats?stream=false")
                    if resp.status_code == 200:
                        data = resp.json()
                        return {
                            "cpu_percent": data.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0),
                            "memory_usage": data.get("memory_stats", {}).get("usage", 0),
                            "memory_limit": data.get("memory_stats", {}).get("limit", 0),
                        }
            except Exception:
                pass

        try:
            cpu_percent = await asyncio.to_thread(psutil.cpu_percent, 0.2)
            mem = await asyncio.to_thread(psutil.virtual_memory)
            return {
                "cpu_percent": float(cpu_percent),
                "memory_usage": int(mem.used),
                "memory_limit": int(mem.total),
            }
        except Exception:
            return {"cpu_percent": None, "memory_usage": None, "memory_limit": None}
