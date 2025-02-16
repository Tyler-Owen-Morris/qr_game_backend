from .player import router as player_router
from .qr_code import router as qr_code_router
from .puzzle import router as puzzle_router
from .auth import router as auth_router
from .admin import router as admin_router

__all__ = ["player_router", "qr_code_router", "puzzle_router", "auth_router", "admin_router"]
