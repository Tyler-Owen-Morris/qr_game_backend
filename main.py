import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from routes import qr, player, websocket, auth, hunts
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(title="QR Code Game Service")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(qr.router, prefix="/qr", tags=["qr"])
app.include_router(player.router, prefix="/player", tags=["player"])
app.include_router(websocket.router, tags=["websocket"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(hunts.router, prefix="/hunts", tags=["hunts"])

@app.on_event("startup")
async def startup_event():
    await init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
