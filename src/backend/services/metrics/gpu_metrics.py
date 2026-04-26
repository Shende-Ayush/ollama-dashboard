import asyncio
import json


class GpuMetricsService:
    async def get_gpu_stats(self) -> dict:
        query = "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits"
        try:
            proc = await asyncio.create_subprocess_shell(
                query,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _stderr = await proc.communicate()
            if proc.returncode != 0:
                return {"utilization_percent": None, "vram_used_mb": None, "vram_total_mb": None}
            line = stdout.decode().strip().splitlines()[0]
            util, used, total = [int(v.strip()) for v in line.split(",")]
            return {"utilization_percent": util, "vram_used_mb": used, "vram_total_mb": total}
        except Exception:
            return {"utilization_percent": None, "vram_used_mb": None, "vram_total_mb": None}
