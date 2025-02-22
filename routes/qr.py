from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import QRCode, PlayerScan, Player, PlayerHuntProgress
from schemas import QRScanRequest, QRScanResponse, QRCodeMetadata
from utils.location import validate_location
from utils.generate_qr_code import generate_qr_code
from auth.utils import get_current_user
from datetime import timedelta, datetime
import logging
import uuid

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/scan", response_model=QRScanResponse)
async def scan_qr_code(
    scan_request: QRScanRequest,
    current_user: Player = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Validate player
    print("current user:",  current_user)
    # if str(current_user.id) != str(scan_request.player_id):
    #     raise HTTPException(status_code=403, detail="Not authorized to scan for this player")

    # Fetch or create QR code
    qr_code = await db.execute(
        select(QRCode).where(QRCode.code == scan_request.qr_code)
    )
    qr_code = qr_code.scalar_one_or_none()
    scan_type = "standard"
    if not qr_code:
        scan_type = "discovery"
        qr_code = await generate_qr_code(scan_request.qr_code, db, latitude=scan_request.latitude, longitude=scan_request.longitude)

    # Check location if required
    location_valid = True
    if qr_code.requires_location:
        if not scan_request.latitude or not scan_request.longitude:
            location_valid = False
        else:
            location_valid = validate_location(
                scan_request.latitude,
                scan_request.longitude,
                qr_code.location
            )

    # Check how many times the player has scanned this QR code before
    previous_scans = await db.execute(
        select(PlayerScan)
        .where(PlayerScan.player_id == current_user.id)
        .where(PlayerScan.qr_code_id == qr_code.id)
    )
    scan_count = len(previous_scans.scalars().all())  # Get previous scan attempts

    # Determine when the player can scan again
    next_scan_available_at = None
    if qr_code.scan_cooldown_seconds:
        next_scan_available_at = datetime.utcnow() + timedelta(seconds=qr_code.scan_cooldown_seconds)

    # Create new PlayerScan record
    new_scan = PlayerScan(
        player_id=current_user.id,
        qr_code_id=qr_code.id,
        latitude=scan_request.latitude,
        longitude=scan_request.longitude,
        attempt_number=scan_count + 1,  # Increment scan attempt count
        next_scan_available_at=next_scan_available_at , # Set cooldown time if applicable,
        success=location_valid,
        scan_type=scan_type
    )

    db.add(new_scan)
    await db.commit()

    hunt_status = None
    if qr_code and qr_code.scan_type == "transportation" and qr_code.reward_data.get("hunt_id"):
        hunt_id = qr_code.reward_data["hunt_id"]
        progress = await db.scalar(select(PlayerHuntProgress).where(
            PlayerHuntProgress.player_id == current_user.id,
            PlayerHuntProgress.hunt_id == hunt_id
        ))
        if progress:
            if progress.completed_at:
                hunt_status = "completed"
            elif progress.abandoned_at:
                hunt_status = "abandoned"
            else:
                hunt_status = "active"
        else:
            hunt_status = "new"

    print("qr_code:", qr_code.reward_data)
    return QRScanResponse(
        status="success",
        encounter_type=qr_code.scan_type,
        reward_data=qr_code.reward_data if qr_code.reward_data else None,
        message="Location check failed" if not location_valid else None,
        location_valid=location_valid,
        ok=True,
        hunt_status=hunt_status
    )

@router.get("/{code}", response_model=QRCodeMetadata)
async def get_qr_metadata(
    code: str,
    current_user: Player = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    qr_code = await db.execute(
        select(QRCode).where(QRCode.code == code)
    )
    qr_code = qr_code.scalar_one_or_none()
    if not qr_code:
        raise HTTPException(status_code=404, detail="QR code not found")

    return QRCodeMetadata(
        code=qr_code.code,
        description=qr_code.description,
        scan_type=qr_code.scan_type,
        requires_location=qr_code.requires_location
    )