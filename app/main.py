import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

NODE_PATH = os.path.join(BASE_DIR, "nodejs")
FFMPEG_PATH = os.path.join(BASE_DIR,"..","ffmpeg", "bin")

# Đưa portable NodeJS + FFmpeg vào PATH
os.environ["PATH"] = (
    NODE_PATH + os.pathsep +
    FFMPEG_PATH + os.pathsep +
    os.environ["PATH"]
)

from fastapi import FastAPI
from app.routers import router
from app.config.cors import cors_origins
from fastapi.middleware.cors import CORSMiddleware


# Initialize FastAPI application
app = FastAPI(
    title="Kino Server",
    description="Kino Server API",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the centralized router
app.include_router(router, prefix="/api/v1")
