from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import QRCode, PlayerScan, Player
from schemas import QRScanRequest, QRScanResponse, QRCodeMetadata
from utils.location import validate_location
from auth.utils import get_current_user
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

    if not qr_code:
        # Create new QR code with default values
        qr_code = QRCode(
            id=uuid.uuid4(),
            code=scan_request.qr_code,
            description=f"Dynamic QR Code {scan_request.qr_code}",
            scan_type="item_drop",  # Default type
            requires_location=False  # Default to not requiring location
        )
        db.add(qr_code)
        await db.flush()

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

    # Record the scan
    new_scan = PlayerScan(
        player_id=current_user.id,
        qr_code_id=qr_code.id,
        latitude=scan_request.latitude,
        longitude=scan_request.longitude,
        success=location_valid
    )
    db.add(new_scan)
    await db.commit()

    return QRScanResponse(
        status="success",
        encounter_type=qr_code.scan_type,
        reward="spy_gadget" if qr_code.scan_type == "item_drop" else None,
        message="Location check failed" if not location_valid else None,
        location_valid=location_valid
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