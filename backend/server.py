import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List
import uuid
from datetime import datetime


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
from lib.db import client, db, ensure_indexes


# Startup runs before the yield, shutdown after it. Add your own setup/teardown here.
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.index_task = asyncio.create_task(ensure_indexes())  # background: a big index build must not block boot
    yield
    client.close()


# Create the main app without a prefix
app = FastAPI(lifespan=lifespan)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class StatusCheckCreate(BaseModel):
    client_name: str

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Hello World"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    _ = await db.status_checks.insert_one(status_obj.model_dump())
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**status_check) for status_check in status_checks]

# Feature routers (one module per resource) — every route stays under /api
from fastapi.responses import JSONResponse

from lib.errors import FeatureDisabled, StorageNotConfigured
from routers import projects, renders, system, timeline

api_router.include_router(system.router)
api_router.include_router(projects.router)
api_router.include_router(timeline.router)
api_router.include_router(renders.router)


# Architectural seams that are intentionally not implemented yet answer 501 honestly,
# and a missing storage configuration answers 503 — no fake success anywhere.
@app.exception_handler(FeatureDisabled)
async def feature_disabled_handler(request, exc: FeatureDisabled):
    return JSONResponse(
        status_code=501,
        content={"detail": str(exc), "feature": exc.feature, "stage": exc.stage},
    )


@app.exception_handler(StorageNotConfigured)
async def storage_not_configured_handler(request, exc: StorageNotConfigured):
    # 424 rather than 503: gateway-class statuses get their bodies replaced by the
    # platform ingress, hiding this actionable message from the UI.
    return JSONResponse(
        status_code=424,
        content={"detail": str(exc), "code": "storage_not_configured"},
    )


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
