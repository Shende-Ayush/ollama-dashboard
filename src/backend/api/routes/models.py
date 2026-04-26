"""
Models router — no auth required.
"""
import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.db.session import get_db_session
from backend.common.security.no_auth import require_api_key
from backend.features.llm.providers.ollama_provider import OllamaProvider
from backend.features.metrics.models import SystemMetric
from backend.features.models.models import ModelRegistryCache
from backend.features.models.schemas import PullModelRequest, StopModelRequest
from backend.features.users.models import UserApiClient
from backend.schemas.pagination import paginate
from backend.services.metrics.docker_metrics import DockerMetricsService
from backend.services.metrics.gpu_metrics import GpuMetricsService
from backend.services.ollama_client import OllamaClient

router = APIRouter(tags=["models"])
provider = OllamaProvider()
docker_metrics = DockerMetricsService()
gpu_metrics = GpuMetricsService()

POPULAR_MODELS = [
    {"id":"llama3.2:3b",     "family":"Llama",     "size_gb":2.0,  "params":"3B",    "description":"Fast, capable Meta Llama 3.2 – ideal for daily tasks",          "tags":["fast","general"],          "recommended":True},
    {"id":"llama3.2:1b",     "family":"Llama",     "size_gb":0.8,  "params":"1B",    "description":"Ultra-light Meta Llama 3.2 — runs on CPU",                      "tags":["tiny","cpu-friendly"],     "recommended":False},
    {"id":"llama3.1:8b",     "family":"Llama",     "size_gb":4.7,  "params":"8B",    "description":"Meta Llama 3.1 — strong reasoning and instruction following",    "tags":["reasoning","general"],     "recommended":True},
    {"id":"llama3.1:70b",    "family":"Llama",     "size_gb":40.0, "params":"70B",   "description":"Meta Llama 3.1 70B — near-frontier open model",                  "tags":["large","frontier"],        "recommended":False},
    {"id":"mistral:7b",      "family":"Mistral",   "size_gb":4.1,  "params":"7B",    "description":"Mistral 7B — excellent code and chat quality",                   "tags":["code","chat"],             "recommended":True},
    {"id":"mistral-nemo",    "family":"Mistral",   "size_gb":7.1,  "params":"12B",   "description":"Mistral Nemo — 128k context, great for long docs",               "tags":["long-context","documents"], "recommended":False},
    {"id":"codellama:7b",    "family":"CodeLlama", "size_gb":3.8,  "params":"7B",    "description":"Meta CodeLlama — fine-tuned for code generation",               "tags":["code","programming"],      "recommended":True},
    {"id":"codellama:13b",   "family":"CodeLlama", "size_gb":7.4,  "params":"13B",   "description":"CodeLlama 13B — improved code understanding",                   "tags":["code","large"],            "recommended":False},
    {"id":"deepseek-coder-v2:lite","family":"DeepSeek","size_gb":8.9,"params":"16B", "description":"DeepSeek Coder V2 Lite — top-tier OSS code model",              "tags":["code","top-rated"],        "recommended":True},
    {"id":"qwen2.5:7b",      "family":"Qwen",      "size_gb":4.7,  "params":"7B",    "description":"Alibaba Qwen 2.5 — multilingual, strong at math & code",        "tags":["multilingual","math"],     "recommended":True},
    {"id":"qwen2.5:14b",     "family":"Qwen",      "size_gb":9.0,  "params":"14B",   "description":"Qwen 2.5 14B — near GPT-4 class open model",                    "tags":["large","frontier"],        "recommended":False},
    {"id":"qwen2.5-coder:7b","family":"Qwen",      "size_gb":4.7,  "params":"7B",    "description":"Qwen 2.5 Coder — competitive with Codestral",                   "tags":["code","top-rated"],        "recommended":False},
    {"id":"phi4",            "family":"Phi",       "size_gb":9.1,  "params":"14B",   "description":"Microsoft Phi-4 — exceptional reasoning per parameter",          "tags":["reasoning","efficient"],   "recommended":True},
    {"id":"phi3.5:mini",     "family":"Phi",       "size_gb":2.2,  "params":"3.8B",  "description":"Microsoft Phi-3.5 Mini — tiny but punches above weight",         "tags":["tiny","efficient"],        "recommended":False},
    {"id":"gemma3:4b",       "family":"Gemma",     "size_gb":3.3,  "params":"4B",    "description":"Google Gemma 3 4B — great vision & multilingual support",        "tags":["google","multimodal"],     "recommended":True},
    {"id":"gemma3:12b",      "family":"Gemma",     "size_gb":8.1,  "params":"12B",   "description":"Google Gemma 3 12B — strong across all benchmarks",              "tags":["google","large"],          "recommended":False},
    {"id":"nomic-embed-text","family":"Embedding", "size_gb":0.3,  "params":"137M",  "description":"Nomic Embed Text — best-in-class local embeddings",              "tags":["embedding","tiny"],        "recommended":True},
    {"id":"mxbai-embed-large","family":"Embedding","size_gb":0.7,  "params":"335M",  "description":"MixedBread embed-large — high quality dense retrieval",          "tags":["embedding","rag"],         "recommended":False},
]


@router.get("/models")
async def get_models(
    pg_no: int = Query(default=1, ge=1),
    pg_size: int = Query(default=50, ge=1, le=100),
    search: str | None = None,
    session: AsyncSession = Depends(get_db_session),
):
    try:
        models = await provider.list_models()
    except Exception:
        models = []
    if search:
        models = [m for m in models if search.lower() in m.get("name", "").lower()]
    normalized = [
        {
            "name": m.get("name", ""),
            "size": m.get("size"),
            "size_gb": round((m.get("size") or 0) / (1024 ** 3), 2),
            "quantization": m.get("details", {}).get("quantization_level"),
            "family": m.get("details", {}).get("family"),
            "parameter_size": m.get("details", {}).get("parameter_size"),
            "modified_at": m.get("modified_at"),
        }
        for m in models
    ]
    for model in normalized:
        existing = await session.get(ModelRegistryCache, model["name"])
        if existing is None:
            session.add(ModelRegistryCache(
                model_name=model["name"],
                size_gb=model["size_gb"],
                quantization=model["quantization"],
                downloaded=True,
                pulled_at=datetime.now(timezone.utc),
            ))
    await session.commit()
    return paginate(normalized, pg_no=pg_no, pg_size=pg_size).model_dump()


@router.get("/models/popular")
async def get_popular_models(
    family: str | None = None,
    search: str | None = None,
    recommended_only: bool = False,
    session: AsyncSession = Depends(get_db_session),
):
    installed_names: set[str] = set()
    try:
        installed = await provider.list_models()
        installed_names = {m.get("name", "") for m in installed}
    except Exception:
        pass

    results = POPULAR_MODELS
    if family:
        results = [m for m in results if m["family"].lower() == family.lower()]
    if search:
        q = search.lower()
        results = [m for m in results if q in m["id"].lower() or q in m["description"].lower() or any(q in t for t in m["tags"])]
    if recommended_only:
        results = [m for m in results if m["recommended"]]

    enriched = [{**m, "installed": m["id"] in installed_names} for m in results]
    families = sorted({m["family"] for m in POPULAR_MODELS})
    return {"items": enriched, "families": families, "total": len(enriched)}


@router.get("/models/search")
async def search_models(q: str):
    ql = q.lower()
    results = [m for m in POPULAR_MODELS if ql in m["id"].lower() or ql in m["description"].lower() or ql in m["family"].lower() or any(ql in t for t in m["tags"])]
    return {"items": results, "query": q}


@router.post("/models/stop")
async def stop_model(payload: StopModelRequest):
    await provider.stop_model(payload.model)
    return {"status": "stopped", "model": payload.model}


@router.post("/models/clear-gpu")
async def clear_gpu():
    client = OllamaClient()
    running = await client.list_running()
    stopped = []
    for model in running:
        name = model.get("name")
        if not name:
            continue
        try:
            await provider.stop_model(name)
            stopped.append(name)
        except Exception:
            continue
    return {"status": "cleared", "stopped_models": stopped}


@router.post("/models/pull")
async def pull_model(
    payload: PullModelRequest,
    session: AsyncSession = Depends(get_db_session),
):
    client = OllamaClient()

    async def event_gen():
        import time
        start_time = time.time()
        async for item in client.pull_model(payload.model):
            completed = item.get("completed", 0) or 0
            total     = item.get("total", 0) or 0
            status    = item.get("status", "")
            digest    = item.get("digest", "")
            percent   = round((completed / total * 100), 1) if total > 0 else 0
            elapsed   = time.time() - start_time
            speed_mbps = round((completed / 1024 / 1024) / elapsed, 2) if elapsed > 0 and completed > 0 else 0
            eta_seconds = round((total - completed) / (completed / elapsed)) if elapsed > 0 and completed > 0 else None

            event = {
                "status": status, "completed": completed, "total": total,
                "percent": percent, "digest": digest, "speed_mbps": speed_mbps,
                "eta_seconds": eta_seconds,
                "size_gb": round(total / 1024 / 1024 / 1024, 2) if total else None,
            }
            if completed > 0 and total > 0 and completed >= total:
                try:
                    cache = await session.get(ModelRegistryCache, payload.model)
                    if cache is None:
                        cache = ModelRegistryCache(model_name=payload.model)
                        session.add(cache)
                    cache.downloaded = True
                    cache.size_gb = total / (1024 ** 3)
                    cache.pulled_at = datetime.now(timezone.utc)
                    await session.commit()
                except Exception:
                    pass
            yield f"data: {json.dumps(event)}\n\n"
        yield f"data: {json.dumps({'status': 'success', 'percent': 100, 'completed': True})}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.get("/models/runtime")
async def runtime_metrics(session: AsyncSession = Depends(get_db_session)):
    client = OllamaClient()
    try:
        running = await client.list_running()
    except Exception:
        running = []

    try:
        docker_stats = await docker_metrics.get_container_stats()
    except Exception:
        docker_stats = {"cpu_percent": None, "memory_usage": None, "memory_limit": None}

    try:
        gpu_stats = await gpu_metrics.get_gpu_stats()
    except Exception:
        gpu_stats = {"utilization_percent": None, "vram_used_mb": None, "vram_total_mb": None}

    try:
        session.add(SystemMetric(
            cpu_percent=float(docker_stats["cpu_percent"]) if docker_stats.get("cpu_percent") is not None else None,
            ram_used_mb=int((docker_stats.get("memory_usage") or 0) / 1024 / 1024) if docker_stats.get("memory_usage") else None,
            ram_total_mb=int((docker_stats.get("memory_limit") or 0) / 1024 / 1024) if docker_stats.get("memory_limit") else None,
            gpu_utilization=float(gpu_stats["utilization_percent"]) if gpu_stats.get("utilization_percent") is not None else None,
            vram_used_mb=gpu_stats.get("vram_used_mb"),
            vram_total_mb=gpu_stats.get("vram_total_mb"),
            container_name="ollama",
        ))
        await session.commit()
    except Exception:
        pass
    return {"container": docker_stats, "gpu": gpu_stats, "models": running}


@router.get("/models/pull-info")
async def pull_info(model: str, session: AsyncSession = Depends(get_db_session)):
    cache = await session.get(ModelRegistryCache, model)
    catalog_entry = next((m for m in POPULAR_MODELS if m["id"] == model or model.startswith(m["id"].split(":")[0])), None)
    size_gb = (cache.size_gb if cache and cache.size_gb else None) or (catalog_entry["size_gb"] if catalog_entry else None)
    return {
        "model_name": model,
        "download_size_gb": size_gb,
        "estimated_disk_after_pull_gb": round((size_gb or 0) * 1.05, 2) if size_gb else None,
        "downloaded": bool(cache and cache.downloaded),
        "pulled_at": cache.pulled_at.isoformat() if cache and cache.pulled_at else None,
    }


@router.delete("/models/{model_name:path}")
async def delete_model(model_name: str, session: AsyncSession = Depends(get_db_session)):
    import httpx
    host = os.getenv("OLLAMA_HOST", "localhost")
    port = os.getenv("OLLAMA_PORT", "11434")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.delete(f"http://{host}:{port}/api/delete", json={"name": model_name})
        ok = resp.status_code in (200, 204)
    cache = await session.get(ModelRegistryCache, model_name)
    if cache:
        await session.delete(cache)
        await session.commit()
    return {"status": "deleted" if ok else "error", "model": model_name}
