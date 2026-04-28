# --- KEY IMPROVEMENTS APPLIED ---
# - Dynamic model discovery
# - Batch DB operations
# - Safe streaming
# - GPU clearing verification
# - Proper error handling
# - Retry logic
# --------------------------------

import json
import logging
import os
import asyncio
import re
import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from backend.common.db.session import SessionLocal, get_db_session
from backend.features.llm.providers.ollama_provider import OllamaProvider
from backend.features.metrics.models import SystemMetric
from backend.features.models.models import ModelDownloadJob, ModelRegistryCache
from backend.features.models.schemas import PullModelRequest, StopModelRequest
from backend.schemas.pagination import paginate
from backend.services.metrics.docker_metrics import DockerMetricsService
from backend.services.metrics.gpu_metrics import GpuMetricsService
from backend.services.ollama_client import OllamaClient
from typing import Optional

from backend.utils.ollama_scraper.client import OllamaScraper
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(tags=["models"])

provider = OllamaProvider()
docker_metrics = DockerMetricsService()
gpu_metrics = GpuMetricsService()
_pull_tasks: dict[str, asyncio.Task] = {}
_MODEL_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._/-]*(?::[a-zA-Z0-9][a-zA-Z0-9._-]*)?$")
TERMINAL_DOWNLOAD_STATES = {"success", "error", "cancelled"}

DEFAULT_POPULAR_MODELS = [
    {
        "id": "llama3.2:3b",
        "model_name": "llama3.2:3b",
        "family": "llama",
        "description": "Small general chat model that runs well on local machines.",
        "tags": ["chat", "tools", "fast", "small"],
        "recommended": True,
        "installed": False,
        "params": "3b",
        "size_gb": 2.0,
    },
    {
        "id": "mistral:7b",
        "model_name": "mistral:7b",
        "family": "mistral",
        "description": "Mistral 7B general-purpose model",
        "tags": ["chat", "fast"],
        "recommended": True,
        "installed": False,
        "params": "7b",
        "size_gb": 4.2,
    },
    {
        "id": "qwen2.5:7b",
        "model_name": "qwen2.5:7b",
        "family": "qwen",
        "description": "Qwen 7B model with strong reasoning",
        "tags": ["chat", "reasoning", "multilingual"],
        "recommended": True,
        "installed": False,
        "params": "7b",
        "size_gb": 4.2,
    },
    {
        "id": "deepseek-r1:7b",
        "model_name": "deepseek-r1:7b",
        "family": "deepseek",
        "description": "Reasoning-focused model for step-by-step problem solving.",
        "tags": ["chat", "reasoning"],
        "recommended": True,
        "installed": False,
        "params": "7b",
        "size_gb": 4.7,
    },
    {
        "id": "nomic-embed-text",
        "model_name": "nomic-embed-text",
        "family": "embedding",
        "description": "Embedding model for search, RAG, and document retrieval.",
        "tags": ["embedding", "rag", "small"],
        "recommended": True,
        "installed": False,
        "params": "137m",
        "size_gb": 0.3,
    },
]


# -------------------------------
# Utility: Retry wrapper
# -------------------------------
async def retry(operation, *args, retries=3, delay=1, **kwargs):
    for i in range(retries):
        try:
            return await operation(*args, **kwargs)
        except Exception:
            if i == retries - 1:
                raise
            await asyncio.sleep(delay)


def normalize_model_name(model_name: str) -> str:
    normalized = model_name.strip()
    if not normalized:
        raise HTTPException(400, "Model name required")
    if len(normalized) > 255 or not _MODEL_NAME_RE.match(normalized):
        raise HTTPException(400, "Model name is not a valid Ollama model identifier")
    return normalized


def model_library_path(model_name: str) -> str:
    return model_name.split(":", 1)[0]


async def validate_pullable_model(model_name: str, client: OllamaClient | None = None) -> None:
    client = client or OllamaClient()
    try:
        if await client.model_exists(model_name):
            return
    except Exception as exc:
        logger.warning("Could not check installed model list before pull: %s", exc)

    url = f"https://ollama.com/library/{model_library_path(model_name)}"
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as http:
            response = await http.get(url)
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Could not verify model against the Ollama registry") from exc

    if response.status_code == 404:
        raise HTTPException(404, f"Model '{model_name}' was not found in the Ollama registry")
    if response.status_code >= 400:
        raise HTTPException(502, f"Ollama registry validation failed with status {response.status_code}")


async def download_job_payload(job: ModelDownloadJob) -> dict:
    size_gb = round(job.total_bytes / (1024 ** 3), 2) if job.total_bytes else None
    return {
        "request_id": job.request_id,
        "model": job.model_name,
        "model_name": job.model_name,
        "status": job.status,
        "completed": job.completed_bytes,
        "total": job.total_bytes,
        "percent": job.percent,
        "speed_mbps": job.speed_mbps,
        "eta_seconds": None,
        "size_gb": size_gb,
        "stop_requested": job.stop_requested,
        "error": job.error,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


async def persist_download_event(request_id: str, item: dict, started: float) -> None:
    now = datetime.now(timezone.utc)
    completed = int(item.get("completed") or 0)
    total = int(item.get("total") or 0)
    percent = round((completed / total * 100), 1) if total else (100.0 if item.get("status") == "success" else 0.0)
    elapsed = max(time.time() - started, 0.001)
    async with SessionLocal() as session:
        job = await session.get(ModelDownloadJob, request_id)
        if not job:
            return
        job.status = item.get("status") or job.status
        job.completed_bytes = completed or job.completed_bytes
        job.total_bytes = total or job.total_bytes
        job.percent = max(job.percent or 0, percent)
        job.speed_mbps = round((job.completed_bytes / 1024 / 1024) / elapsed, 2) if job.completed_bytes else 0
        job.updated_at = now
        if job.status == "success":
            job.percent = 100
            job.completed_at = now
        await session.commit()


async def run_pull_job(request_id: str, model_name: str) -> None:
    client = OllamaClient()
    started = time.time()
    try:
        async for item in client.pull_model(model_name):
            async with SessionLocal() as session:
                job = await session.get(ModelDownloadJob, request_id)
                if job and job.stop_requested:
                    job.status = "cancelled"
                    job.completed_at = datetime.now(timezone.utc)
                    job.updated_at = job.completed_at
                    await session.commit()
                    return
            await persist_download_event(request_id, item, started)

        async with SessionLocal() as session:
            now = datetime.now(timezone.utc)
            job = await session.get(ModelDownloadJob, request_id)
            if job:
                job.status = "success"
                job.percent = 100
                job.updated_at = now
                job.completed_at = now
            cache = await session.get(ModelRegistryCache, model_name)
            if not cache:
                cache = ModelRegistryCache(model_name=model_name)
                session.add(cache)
            cache.downloaded = True
            cache.pulled_at = now
            await session.commit()
    except asyncio.CancelledError:
        async with SessionLocal() as session:
            job = await session.get(ModelDownloadJob, request_id)
            if job:
                now = datetime.now(timezone.utc)
                job.status = "cancelled"
                job.stop_requested = True
                job.updated_at = now
                job.completed_at = now
                await session.commit()
        raise
    except Exception as exc:
        logger.exception("Model pull failed for %s", model_name)
        async with SessionLocal() as session:
            job = await session.get(ModelDownloadJob, request_id)
            if job:
                now = datetime.now(timezone.utc)
                job.status = "error"
                job.error = str(exc)
                job.updated_at = now
                job.completed_at = now
                await session.commit()
    finally:
        _pull_tasks.pop(request_id, None)


# -------------------------------
# GET MODELS (Optimized)
# -------------------------------
@router.get("/models")
async def get_models(
    pg_no: int = Query(default=1, ge=1),
    pg_size: int = Query(default=50, ge=1, le=100),
    search: str | None = None,
    session: AsyncSession = Depends(get_db_session),
):
    try:
        models = await retry(provider.list_models)
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch models: {str(e)}")

    if search:
        models = [m for m in models if search.lower() in m.get("name", "").lower()]

    normalized = []
    for m in models:
        normalized.append({
            "name": m.get("name", ""),
            "size": m.get("size"),
            "size_gb": round((m.get("size") or 0) / (1024 ** 3), 2),
            "quantization": m.get("details", {}).get("quantization_level"),
            "family": m.get("details", {}).get("family"),
            "parameter_size": m.get("details", {}).get("parameter_size"),
            "modified_at": m.get("modified_at"),
        })

    installed_names = {m["name"] for m in normalized if m["name"]}
    cache_result = await session.execute(select(ModelRegistryCache))
    cache_by_name = {row.model_name: row for row in cache_result.scalars().all()}
    now = datetime.now(timezone.utc)
    for item in normalized:
        cache = cache_by_name.get(item["name"])
        if not cache:
            cache = ModelRegistryCache(model_name=item["name"])
            session.add(cache)
            cache_by_name[item["name"]] = cache
        cache.size_gb = item["size_gb"]
        cache.quantization = item["quantization"]
        cache.downloaded = True
        cache.pulled_at = cache.pulled_at or now
    for cache in cache_by_name.values():
        if cache.model_name not in installed_names and cache.downloaded:
            cache.downloaded = False
    if cache_by_name:
        await session.commit()

    active_result = await session.execute(
        select(ModelDownloadJob).where(ModelDownloadJob.status.notin_(list(TERMINAL_DOWNLOAD_STATES)))
    )
    active_by_name = {job.model_name: await download_job_payload(job) for job in active_result.scalars().all()}
    for item in normalized:
        cache = cache_by_name.get(item["name"])
        item["model_id"] = item["name"]
        item["downloaded"] = True
        item["pulled_at"] = cache.pulled_at.isoformat() if cache and cache.pulled_at else None
        item["download"] = active_by_name.get(item["name"])

    return paginate(normalized, pg_no=pg_no, pg_size=pg_size).model_dump()


def infer_family(name: str) -> str:
    name = name.lower()

    if "deepseek" in name:
        return "deepseek"
    if "llama" in name:
        return "llama"
    if "mistral" in name:
        return "mistral"
    if "qwen" in name:
        return "qwen"
    if "gemma" in name:
        return "gemma"
    if "phi" in name:
        return "phi"
    if "codellama" in name:
        return "code"
    if any(token in name for token in ("embed", "nomic", "bge", "mxbai")):
        return "embedding"

    return "other"


def derive_tags(name: str, description: str, tags: list[str]) -> list[str]:
    text = f"{name} {description}".lower()
    derived = set(tags)
    if any(token in text for token in ("embed", "nomic", "bge", "mxbai")):
        derived.add("embedding")
    else:
        derived.add("chat")
    if any(token in text for token in ("code", "coder", "codellama")):
        derived.add("code")
    if any(token in text for token in ("reason", "thinking", "r1")):
        derived.add("reasoning")
    if any(token in text for token in ("vision", "llava", "bakllava")):
        derived.add("vision")
    if any(token in text for token in ("1b", "3b", "tiny", "small", "mini")):
        derived.add("small")
        derived.add("fast")
    if any(token in text for token in ("70b", "405b", "large")):
        derived.add("large")
    if any(token in text for token in ("qwen", "glm", "aya", "multilingual")):
        derived.add("multilingual")
    return sorted(derived)


def estimate_model_size_gb(sizes: list[str]) -> float | None:
    if not sizes:
        return None
    first = sizes[0].lower().strip()
    number = "".join(ch for ch in first if ch.isdigit() or ch == ".")
    if not number:
        return None
    params_b = float(number) / 1000 if first.endswith("m") else float(number)
    return round(max(params_b * 0.6, 0.1), 1)


@router.get("/models/popular")
async def get_popular_models(
    family: Optional[str] = None,
    search: Optional[str] = None,
    tag: Optional[str] = None,
    recommended_only: bool = False,
    pg_no: int = Query(default=1, ge=1),
    pg_size: int = Query(default=24, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        installed = await provider.list_models()
        installed_names = {
            m.get("name", "").lower() for m in installed if m.get("name")
        }
    except Exception as exc:
        logger.warning("Unable to fetch installed Ollama models: %s", exc)
        installed_names = set()

    scraped_models = []
    try:
        scraper = OllamaScraper(max_pages=3)

        scraped_models = await scraper.scrape(
            query=search,
            categories=None,
            order="newest",
        )
    except Exception as exc:
        logger.warning("Model scraper failed: %s", exc)
        scraped_models = []

    external_results = []
    seen_external_ids: set[str] = set()
    for m in scraped_models:
        if not m.name:
            continue

        name = m.name.lower()
        if name in seen_external_ids:
            continue
        seen_external_ids.add(name)

        external_results.append(
            {
                "id": name,
                "model_name": name,
                "family": infer_family(name),
                "description": m.description or "",
                "tags": derive_tags(name, m.description or "", m.tags or []),
                "params": m.sizes[0] if m.sizes else "unknown",
                "size_gb": estimate_model_size_gb(m.sizes),
                "recommended": True,
                "installed": name in installed_names,
            }
        )

    curated_results = [item.copy() for item in DEFAULT_POPULAR_MODELS]
    for item in curated_results:
        item["installed"] = item["id"].lower() in installed_names

    existing_ids = {m["id"] for m in external_results}

    installed_only = [
        {
            "id": name,
            "model_name": name,
            "family": infer_family(name),
            "description": "Installed model",
            "tags": [],
            "params": "installed",
            "size_gb": None,
            "recommended": True,
            "installed": True,
        }
        for name in installed_names
        if name not in existing_ids
    ]

    result_by_id = {item["id"]: item for item in curated_results}
    for item in external_results + installed_only:
        existing = result_by_id.get(item["id"])
        if existing:
            existing.update({key: value for key, value in item.items() if value not in (None, "", [], "unknown")})
            existing["tags"] = sorted(set(existing.get("tags", [])) | set(item.get("tags", [])))
        else:
            result_by_id[item["id"]] = item

    results = list(result_by_id.values())

    if not results:
        logger.info("No popular models found from Ollama; returning default fallback set")
        results = DEFAULT_POPULAR_MODELS.copy()

    if family:
        family = family.lower()
        results = [r for r in results if r["family"] == family]

    if search:
        search = search.lower()
        results = [
            r for r in results
            if search in r["id"] or search in (r.get("description") or "").lower()
        ]

    if tag:
        tag = tag.lower()
        if tag == "recommended":
            results = [r for r in results if r["recommended"]]
        else:
            results = [r for r in results if tag in [t.lower() for t in r.get("tags", [])]]

    if recommended_only:
        results = [r for r in results if r["recommended"]]

    results.sort(
        key=lambda x: (
            not x["installed"],  # installed first
            x["id"],
        )
    )

    page = paginate(results, pg_no=pg_no, pg_size=pg_size).model_dump()
    return {
        "items": page["items"],
        "page": page["page"],
        "families": sorted(list({r["family"] for r in results})),
        "tags": sorted(list({tag for r in results for tag in r.get("tags", [])})),
        "total": len(results),
    }


@router.get("/models/pull-info")
async def pull_info(model: str = Query(...), session: AsyncSession = Depends(get_db_session)):
    model_name = normalize_model_name(model)
    client = OllamaClient()
    await validate_pullable_model(model_name, client)
    cache = await session.get(ModelRegistryCache, model_name)
    try:
        downloaded = await client.model_exists(model_name)
    except Exception:
        downloaded = bool(cache and cache.downloaded)

    active = await session.execute(
        select(ModelDownloadJob)
        .where(ModelDownloadJob.model_name == model_name, ModelDownloadJob.status.notin_(list(TERMINAL_DOWNLOAD_STATES)))
        .order_by(ModelDownloadJob.started_at.desc())
        .limit(1)
    )
    job = active.scalar_one_or_none()
    disk_used = await session.execute(select(func.sum(ModelRegistryCache.size_gb)).where(ModelRegistryCache.downloaded == True))  # noqa: E712
    current_disk = round(float(disk_used.scalar() or 0), 2)
    return {
        "model_name": model_name,
        "download_size_gb": cache.size_gb if cache else None,
        "estimated_disk_after_pull_gb": current_disk + float(cache.size_gb or 0) if cache and cache.size_gb else current_disk,
        "downloaded": downloaded,
        "pulled_at": cache.pulled_at.isoformat() if cache and cache.pulled_at else None,
        "download": await download_job_payload(job) if job else None,
    }


@router.get("/models/downloads")
async def list_downloads(
    active_only: bool = False,
    pg_no: int = Query(default=1, ge=1),
    pg_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    stmt = select(ModelDownloadJob).order_by(ModelDownloadJob.started_at.desc())
    if active_only:
        stmt = stmt.where(ModelDownloadJob.status.notin_(list(TERMINAL_DOWNLOAD_STATES)))
    result = await session.execute(stmt)
    items = [await download_job_payload(job) for job in result.scalars().all()]
    return paginate(items, pg_no=pg_no, pg_size=pg_size).model_dump()


@router.post("/models/pull/{request_id}/stop")
async def stop_pull(request_id: str, session: AsyncSession = Depends(get_db_session)):
    job = await session.get(ModelDownloadJob, request_id)
    if not job:
        raise HTTPException(404, "Download job not found")
    model_name = job.model_name
    job.stop_requested = True
    job.status = "cancelled" if job.status in {"queued", "connecting"} else job.status
    job.updated_at = datetime.now(timezone.utc)
    await session.commit()
    task = _pull_tasks.get(request_id)
    if task and not task.done():
        task.cancel()
    return {"request_id": request_id, "status": "cancel_requested", "model": model_name}
# -------------------------------
# STOP MODEL
# -------------------------------
@router.post("/models/stop")
async def stop_model(payload: StopModelRequest):
    try:
        await provider.stop_model(payload.model)
    except Exception as e:
        raise HTTPException(500, f"Failed to stop model: {str(e)}")

    return {"status": "stopped", "model": payload.model}


# -------------------------------
# CLEAR GPU (Improved)
# -------------------------------
@router.post("/models/clear-gpu")
async def clear_gpu():
    client = OllamaClient()

    try:
        running = await client.list_running()
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch running models: {str(e)}")

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

    # 🔥 Verify GPU cleared
    await asyncio.sleep(2)
    gpu = await gpu_metrics.get_gpu_stats()

    return {
        "status": "cleared",
        "stopped_models": stopped,
        "gpu_after": gpu
    }


# -------------------------------
# PULL MODEL (SAFE STREAM)
# -------------------------------
@router.post("/models/pull")
async def pull_model(
    payload: PullModelRequest,
    session: AsyncSession = Depends(get_db_session),
):
    model_name = normalize_model_name(payload.model)
    await validate_pullable_model(model_name)

    active_result = await session.execute(
        select(ModelDownloadJob)
        .where(ModelDownloadJob.model_name == model_name, ModelDownloadJob.status.notin_(list(TERMINAL_DOWNLOAD_STATES)))
        .order_by(ModelDownloadJob.started_at.desc())
        .limit(1)
    )
    job = active_result.scalar_one_or_none()
    if not job:
        request_id = uuid4().hex
        job = ModelDownloadJob(request_id=request_id, model_name=model_name, status="queued")
        session.add(job)
        await session.commit()
        task = asyncio.create_task(run_pull_job(request_id, model_name))
        _pull_tasks[request_id] = task
    else:
        request_id = job.request_id

    async def event_gen():
        last_status = None
        while True:
            async with SessionLocal() as read_session:
                current = await read_session.get(ModelDownloadJob, request_id)
                if not current:
                    yield f"data: {json.dumps({'request_id': request_id, 'model': model_name, 'status': 'error', 'percent': 0, 'completed': 0, 'total': 0, 'speed_mbps': 0, 'eta_seconds': None, 'size_gb': None, 'error': 'Download job disappeared'})}\n\n"
                    return
                payload_dict = await download_job_payload(current)
            if payload_dict != last_status:
                yield f"data: {json.dumps(payload_dict)}\n\n"
                last_status = payload_dict
            if payload_dict["status"] in TERMINAL_DOWNLOAD_STATES:
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


# -------------------------------
# RUNTIME METRICS (Stable)
# -------------------------------
@router.get("/models/runtime")
async def runtime_metrics(session: AsyncSession = Depends(get_db_session)):
    client = OllamaClient()

    running = await client.list_running()
    docker_stats = await docker_metrics.get_container_stats()
    gpu_stats = await gpu_metrics.get_gpu_stats()

    try:
        session.add(SystemMetric(
            cpu_percent=docker_stats.get("cpu_percent"),
            ram_used_mb=int((docker_stats.get("memory_usage") or 0) / 1024 / 1024),
            ram_total_mb=int((docker_stats.get("memory_limit") or 0) / 1024 / 1024),
            gpu_utilization=gpu_stats.get("utilization_percent"),
            vram_used_mb=gpu_stats.get("vram_used_mb"),
            vram_total_mb=gpu_stats.get("vram_total_mb"),
            container_name="ollama",
        ))
        await session.commit()
    except Exception:
        pass

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "container": docker_stats,
        "gpu": gpu_stats,
        "models": running,
    }


@router.delete("/models/{model_name:path}")
async def delete_model(model_name: str, session: AsyncSession = Depends(get_db_session)):
    client = OllamaClient()

    try:
        await client.delete_model(model_name)
    except ValueError:
        raise HTTPException(404, "Model not found")
    except Exception as e:
        raise HTTPException(500, str(e))

    # DB cleanup
    cache = await session.get(ModelRegistryCache, model_name)
    if cache:
        cache.downloaded = False
        cache.last_used_at = None
        await session.commit()

    return {"status": "deleted", "model": model_name}
