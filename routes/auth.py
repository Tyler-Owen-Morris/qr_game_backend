from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import Player
from database import get_db
from auth.utils import verify_password, get_password_hash, create_access_token, get_current_user
from datetime import timedelta
from schemas import PlayerCreate, Token, QRLoginRequest, QRLoginResponse
import uuid
from routes.websocket import manager
from datetime import datetime

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# Store temporary QR login sessions with expiration
qr_login_sessions = {}

@router.post("/register", response_model=PlayerCreate)
async def register(
    player: PlayerCreate,
    db: AsyncSession = Depends(get_db)
):
    # Check if username already exists
    query = select(Player).where(Player.username == player.username)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    # Create new player with hashed password
    new_player = Player(
        id=uuid.uuid4(),
        username=player.username,
        password_hash=get_password_hash(player.password)
    )
    db.add(new_player)
    await db.commit()
    await db.refresh(new_player)

    return PlayerCreate(username=new_player.username, password=player.password)

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    # Find user
    query = select(Player).where(Player.username == form_data.username)
    result = await db.execute(query)
    player = result.scalar_one_or_none()

    if not player or not verify_password(form_data.password, player.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token = create_access_token(
        data={"sub": str(player.id)},
        expires_delta=timedelta(minutes=30)
    )

    return Token(access_token=access_token, token_type="bearer")

@router.post("/qr-login-init")
async def initialize_qr_login():
    """Generate a new QR login session"""
    # Clean up expired sessions
    current_time = datetime.utcnow()
    expired_sessions = [
        session_id for session_id, session in qr_login_sessions.items()
        if (current_time - session["created_at"]).total_seconds() > 300  # 5 minutes expiration
        or session["used"]
    ]
    for session_id in expired_sessions:
        del qr_login_sessions[session_id]

    session_id = str(uuid.uuid4())
    qr_login_sessions[session_id] = {
        "created_at": current_time,
        "used": False,
        "attempts": 0  # Track invalid attempts
    }
    return {"session_id": session_id}

@router.post("/qr-login-complete")
async def complete_qr_login(
    login_request: QRLoginRequest,
    current_user: Player = Depends(get_current_user)
):
    """Complete QR login from mobile device"""
    print("login request from qr:",login_request)
    session = qr_login_sessions.get(login_request.session_id)
    print(session)
    if not session:
        raise HTTPException(status_code=400, detail="Invalid session")

    if session["used"]:
        raise HTTPException(status_code=400, detail="Session already used")

    # Check expiration
    if (datetime.utcnow() - session["created_at"]).total_seconds() > 300:
        del qr_login_sessions[login_request.session_id]
        raise HTTPException(status_code=400, detail="Session expired")

    # Track attempts to prevent brute force
    session["attempts"] += 1
    if session["attempts"] > 3:
        del qr_login_sessions[login_request.session_id]
        raise HTTPException(status_code=400, detail="Too many invalid attempts")

    # Mark session as used
    session["used"] = True

    # Create a new token for the web session
    access_token = create_access_token(
        data={"sub": str(current_user.id)},
        expires_delta=timedelta(minutes=30)
    )

    # Notify the waiting browser through WebSocket
    await manager.send_login_success(
        login_request.session_id,
        access_token
    )

    return {"status": "success"}

@router.get("/me")
async def read_users_me(
    current_user: Player = Depends(get_current_user)
):
    return current_user