from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional
from database import get_db
from models import QRCode, ScanHistory, Player
from schemas import QRCodeResponse, ScanHistoryCreate
from utils.qr_validation import validate_qr_code
from auth import get_current_user
import random

router = APIRouter()

@router.post("/scan/{code}")
async def scan_qr_code(
    code: str,
    player_lat: Optional[float] = None,
    player_lng: Optional[float] = None,
    current_user: Player = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Find QR code in database
    result = await db.execute(
        select(QRCode).filter(QRCode.code == code)
    )
    qr_code = result.scalar_one_or_none()
    
    if not qr_code:
        raise HTTPException(status_code=404, detail="QR code not found")
    
    # Validate QR code
    is_valid, message = validate_qr_code(qr_code, player_lat, player_lng)
    if not is_valid:
        raise HTTPException(status_code=400, detail=message)
    
    # Check if already scanned
    result = await db.execute(
        select(ScanHistory)
        .filter(ScanHistory.player_id == current_user.id)
        .filter(ScanHistory.qr_code_id == qr_code.id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="QR code already scanned")
    
    # Generate outcome based on QR code type
    outcome = generate_outcome(qr_code.type, qr_code.data)
    
    # Record scan
    scan_history = ScanHistory(
        player_id=current_user.id,
        qr_code_id=qr_code.id,
        outcome=outcome
    )
    
    # Update player score
    current_user.score += outcome.get("points", 0)
    
    db.add(scan_history)
    db.add(current_user)
    await db.commit()
    
    return {
        "message": "QR code scanned successfully",
        "outcome": outcome
    }

def generate_outcome(qr_type: str, qr_data: dict):
    if qr_type == "puzzle":
        return {
            "type": "puzzle",
            "puzzle_id": qr_data["puzzle_id"],
            "difficulty": qr_data["difficulty"],
            "points": 10
        }
    elif qr_type == "reward":
        reward_chance = random.random()
        if reward_chance < 0.1:  # 10% chance for rare item
            item = qr_data["rare_items"][random.randint(0, len(qr_data["rare_items"]) - 1)]
            points = 50
        else:
            item = qr_data["common_items"][random.randint(0, len(qr_data["common_items"]) - 1)]
            points = 20
        return {
            "type": "reward",
            "item": item,
            "points": points
        }
    elif qr_type == "transport":
        return {
            "type": "transport",
            "destination": qr_data["destination"],
            "points": 5
        }
    
    return {"type": "unknown", "points": 1}

@router.get("/{qr_id}", response_model=QRCodeResponse)
async def get_qr_code_info(
    qr_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(QRCode).filter(QRCode.id == qr_id)
    )
    qr_code = result.scalar_one_or_none()
    
    if not qr_code:
        raise HTTPException(status_code=404, detail="QR code not found")
    
    return qr_code
