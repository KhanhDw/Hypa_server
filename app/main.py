from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Domain FE được phép truy cập API
origins = [
    "http://localhost:5173",   # Vite React chạy local
    "https://hypa.app",        # FE production (ví dụ)
]

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Mở cho tất cả các domain (không an toàn cho production)
    # allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import services after app initialization to avoid circular dependencies
from app.services.container import ServiceContainer

# Initialize services using container
service_container = ServiceContainer()
metadata_service = service_container.get_metadata_service()

# -------------------------------------------------------
# Endpoint /metadata (Uses service layer)
# -------------------------------------------------------
@app.get("/metadata")
async def metadata(url: str):
    return await metadata_service.get_metadata(url)


# -------------------------------------------------------
# Homepage
# -------------------------------------------------------
@app.get("/")
def home():
    return {"message": "Simple Server is running!"}