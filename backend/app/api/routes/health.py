from __future__ import annotations

import shutil

import psutil
from fastapi import APIRouter

from app.core.config import settings
from app.schemas.health import HealthResponse, SystemHealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    return HealthResponse(status="ok", version=settings.app_version)


@router.get("/health/system", response_model=SystemHealthResponse)
async def get_system_health() -> SystemHealthResponse:
    memory = psutil.virtual_memory()
    disk = shutil.disk_usage("/")

    gpu_available = False
    gpu_name = None
    gpu_memory_total_mb = None
    gpu_memory_used_mb = None
    cuda_available = False
    mps_available = False
    torch_device = "cpu"
    torch_version = "unavailable"

    try:
        import torch

        torch_version = torch.__version__
        cuda_available = torch.cuda.is_available()
        try:
            mps_available = torch.backends.mps.is_available()
        except AttributeError:
            mps_available = False

        if cuda_available:
            gpu_available = True
            gpu_name = torch.cuda.get_device_name(0)
            total = torch.cuda.get_device_properties(0).total_memory
            used = torch.cuda.memory_allocated(0)
            gpu_memory_total_mb = total // (1024 * 1024)
            gpu_memory_used_mb = used // (1024 * 1024)
            torch_device = "cuda"
        elif mps_available:
            gpu_available = True
            gpu_name = "Apple Silicon MPS"
            torch_device = "mps"
    except ImportError:
        pass

    return SystemHealthResponse(
        gpu_available=gpu_available,
        gpu_name=gpu_name,
        gpu_memory_total_mb=gpu_memory_total_mb,
        gpu_memory_used_mb=gpu_memory_used_mb,
        cpu_count=psutil.cpu_count(logical=True) or 1,
        ram_total_mb=memory.total // (1024 * 1024),
        ram_used_mb=memory.used // (1024 * 1024),
        disk_free_gb=disk.free / (1024**3),
        model_loaded=False,
        active_run_id=None,
        torch_device=torch_device,
        torch_version=torch_version,
        cuda_available=cuda_available,
        mps_available=mps_available,
    )
