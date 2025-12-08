# Simple FastAPI Server

A minimal FastAPI server with basic routing.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
python -m uvicorn app.main:app --reload
```

Or use the start script:
```bash
start_server.bat
```

## Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /users/{user_id}` - Get user by ID
- `GET /items/{item_id}` - Get item by ID