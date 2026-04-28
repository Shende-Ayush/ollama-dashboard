import asyncio
import os


class GpuMetricsService:
    async def get_gpu_stats(self) -> dict:
        query = os.getenv(
            "GPU_METRICS_COMMAND",
            "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits",
        )
        try:
            proc = await asyncio.create_subprocess_shell(
                query,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                return {
                    "utilization_percent": None,
                    "vram_used_mb": None,
                    "vram_total_mb": None,
                    "available": False,
                    "source": "nvidia-smi",
                    "error": stderr.decode(errors="ignore").strip() or "nvidia-smi unavailable",
                }
            lines = stdout.decode().strip().splitlines()
            if not lines:
                return {
                    "utilization_percent": None,
                    "vram_used_mb": None,
                    "vram_total_mb": None,
                    "available": False,
                    "source": "nvidia-smi",
                    "error": "nvidia-smi returned no GPU rows",
                }
            line = lines[0]
            util, used, total = [int(v.strip()) for v in line.split(",")]
            return {
                "utilization_percent": util,
                "vram_used_mb": used,
                "vram_total_mb": total,
                "available": True,
                "source": "nvidia-smi",
                "error": None,
            }
        except Exception as exc:
            return {
                "utilization_percent": None,
                "vram_used_mb": None,
                "vram_total_mb": None,
                "available": False,
                "source": "nvidia-smi",
                "error": str(exc),
            }
