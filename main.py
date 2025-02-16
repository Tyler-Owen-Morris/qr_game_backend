import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import player_router, qr_code_router, puzzle_router, auth_router, admin_router
from database import init_db

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="QR Hunter API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/auth", tags=["authentication"])
app.include_router(player_router, prefix="/player", tags=["player"])
app.include_router(qr_code_router, prefix="/qr", tags=["qr-code"])
app.include_router(puzzle_router, prefix="/puzzle", tags=["puzzle"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])

@app.on_event("startup")
async def startup_event():
    await init_db()

@app.get("/")
async def root():
    return {"message": "Welcome to QR Hunter API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)