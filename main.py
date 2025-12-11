import os
import sys
import uvicorn
import asyncio
from fastapi import FastAPI
from app.routers import router
from app.config.cors import cors_origins
from fastapi.middleware.cors import CORSMiddleware
from app.config.event_loop import setup_event_loop

setup_event_loop()

# Set up logging first
from app.config.logging_config import setup_logging
setup_logging()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

NODE_PATH = os.path.join(BASE_DIR, "nodejs")
FFMPEG_PATH = os.path.join(BASE_DIR,"..","ffmpeg", "bin")

# Đưa portable NodeJS + FFmpeg vào PATH
os.environ["PATH"] = (
    NODE_PATH + os.pathsep +
    FFMPEG_PATH + os.pathsep +
    os.environ["PATH"]
)




# Initialize FastAPI application
app = FastAPI(
    title="Kino Server",
    description="Kino Server API",
    version="1.0.0",
    docs_url="/docs",        # Default, but you can change it
    redoc_url="/redoc",      # Default, but you can change it
    openapi_url="/openapi.json"  # Default OpenAPI schema
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
app.include_router(router, prefix="/api")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["."]
    )