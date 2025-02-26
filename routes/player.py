from pydantic import BaseModel
from cryptography.fernet import InvalidToken
import math  # For distance calculation
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, or_, func
from sqlalchemy.orm import joinedload
from database import get_db
from models import Player, PlayerScan, QRCode
from schemas import PlayerHistory, ScanHistoryItem, Player as PlayerSchema, PeerScanRequest, PeerScanResponse, ErrorResponse
from auth.utils import get_current_user
from typing import List
import os
import uuid
import json
import time
import base64
from cryptography.fernet import Fernet, InvalidToken
import math
from datetime import datetime, timedelta
from utils.location import calculate_distance
from .websocket import manager
from time import perf_counter

STRING_ENCODE_SECRET_KEY = os.getenv("STRING_ENCODE_SECRET_KEY", "iNbKium-f8sdpM3yp_g_ZoXz3nin2psxJ7_oPvJN7kU=")
PEER_SCAN_COOLDOWN = os.getenv("PEER_SCAN_COOLDOWN",5 * 60)
cipher = Fernet(STRING_ENCODE_SECRET_KEY)
router = APIRouter()

async def get_pagination_params(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=50, description="Number of records to return")
):
    return {"skip": skip, "limit": limit}

# Get player history
@router.get("/my_history", response_model=PlayerHistory)
async def get_player_history(
    current_user: Player = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    pagination: dict = Depends(get_pagination_params)
):
    skip = pagination["skip"]
    limit = pagination["limit"]

    # Base query for PlayerScan
    base_query = select(PlayerScan).where(PlayerScan.player_id == current_user.id)

    # Count total scans
    total_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(total_query)
    total = total_result.scalar()

    # Fetch paginated scans with explicit column selection
    query = (
        select(
            PlayerScan.scan_time,
            PlayerScan.success,
            PlayerScan.scan_type,
            PlayerScan.proximity_status,
            QRCode.code.label("qr_code"),
            Player.username.label("peer_username")
        )
        .select_from(PlayerScan)
        .outerjoin(QRCode, PlayerScan.qr_code_id == QRCode.id)
        .outerjoin(Player, PlayerScan.peer_player_id == Player.id)
        .where(PlayerScan.player_id == current_user.id)
        .order_by(PlayerScan.scan_time.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    scans = result.fetchall()  # Returns tuples with selected columns

    # Build response
    scan_history = []
    for scan_tuple in scans:
        scan_time, success, scan_type, proximity_status, qr_code, peer_username = scan_tuple
        item = ScanHistoryItem(
            scan_time=scan_time,
            success=success,
            scan_type=scan_type,
            proximity_status=proximity_status,
            qr_code=qr_code,
            peer_username=peer_username
        )
        scan_history.append(item)

    return PlayerHistory(
        total=total,
        skip=skip,
        limit=limit,
        scans=scan_history
    )

# Get current player profile
@router.get("/me", response_model=PlayerSchema)
async def get_current_player(
    current_user: Player = Depends(get_current_user)
):
    return current_user

# Retrieve scan history for a player (Admin/Internal Use)
@router.get("/{player_id}/history", response_model=PlayerHistory)
async def get_player_scan_history(
    player_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Player = Depends(get_current_user)
):
    if str(current_user.id) != str(player_id):
        raise HTTPException(status_code=403, detail="Not authorized to view this player's history")

    query = select(PlayerScan, QRCode).join(
        QRCode,
        PlayerScan.qr_code_id == QRCode.id
    ).where(PlayerScan.player_id == player_id)

    result = await db.execute(query)
    scans = result.all()

    scan_history = [
        ScanHistoryItem(
            qr_code=qr.code,
            scan_time=scan.scan_time,
            success=scan.success
        )
        for scan, qr in scans
    ]

    return PlayerHistory(scans=scan_history)

# Update player progress (e.g., after scanning a QR code)
@router.post("/progress/update")
async def update_progress(
    current_user: Player = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = update(Player).where(Player.id == current_user.id).values(progress=current_user.progress + 1)
    await db.execute(query)
    await db.commit()
    return {"message": "Progress updated successfully"}

# Record a new scan
@router.post("/scan")
async def record_scan(
    qr_code_id: uuid.UUID,
    success: bool,
    current_user: Player = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    qr_code = await db.get(QRCode, qr_code_id)
    if not qr_code:
        raise HTTPException(status_code=404, detail="QR code not found")

    new_scan = PlayerScan(player_id=current_user.id, qr_code_id=qr_code_id, success=success)
    db.add(new_scan)
    await db.commit()
    return {"message": "Scan recorded successfully"}

# Generate my barcode to pair with another player
@router.post("/peer_scan/generate")
async def generate_peer_scan_qr(
    location: dict,  # Expecting JSON object { "latitude": ..., "longitude": ... }
    current_user: Player = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    start = perf_counter()
    print("loc",location, flush=True)
    if "location" not in location or ("latitude" not in location['location'] or "longitude" not in location['location']):
        raise HTTPException(status_code=400, detail="Invalid location data")
    validation_time = perf_counter()
    print(f"Validation took: {validation_time - start:.4f}s", flush=True)
    # Create payload with player ID, location, and timestamp
    payload = {
        "player_id": str(current_user.id),
        "location": location['location'],
        "timestamp": int(time.time())  # Unix timestamp
    }
    payload_time = perf_counter()
    print(f"Payload creation took: {payload_time - validation_time:.4f}s", flush=True)

    # Convert to JSON string
    payload_str = json.dumps(payload)
    json_time = perf_counter()
    print(f"JSON serialization took: {json_time - payload_time:.4f}s", flush=True)

    # Encrypt the string
    encrypted_payload = cipher.encrypt(payload_str.encode())
    encrypt_time = perf_counter()
    print(f"Encryption took: {encrypt_time - json_time:.4f}s", flush=True)

    # Encode in Base64 for easier QR encoding
    encoded_qr_string = base64.urlsafe_b64encode(encrypted_payload).decode()
    encode_time = perf_counter()
    print(f"Base64 encoding took: {encode_time - encrypt_time:.4f}s", flush=True)

    response = {"peer_qr": f"arg://peer.{encoded_qr_string}"}
    end = perf_counter()
    print(f"Total time: {end - start:.4f}s", flush=True)
    return response

@router.post("/peer_scan/validate", response_model=PeerScanResponse)
async def validate_peer_scan(
    body: PeerScanRequest,
    current_user: Player = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Extract QR code
    peer_qr = body.peer_qr
    if not peer_qr.startswith("arg://peer."):
        return ErrorResponse(message="This QR code isn’t valid for peer pairing.")

    # Decrypt QR payload
    try:
        encrypted_data = peer_qr.replace("arg://peer.", "")
        decrypted_bytes = cipher.decrypt(base64.urlsafe_b64decode(encrypted_data))
        payload = json.loads(decrypted_bytes.decode())
    except (InvalidToken, ValueError, json.JSONDecodeError):
        return ErrorResponse(message="This QR code is invalid or has been tampered with.")
    # Extract payload fields
    player_id = payload.get("player_id")
    orig_location = payload.get("location", {})
    timestamp = payload.get("timestamp")

    if not all([player_id, orig_location.get("latitude"), orig_location.get("longitude"), timestamp]):
        return ErrorResponse(message="The QR code data is incomplete or corrupted.")

    # Prevent self-scanning
    if player_id == str(current_user.id):
        raise HTTPException(status_code=400, detail="Cannot scan your own QR code")

    # Check time validity (5 minutes = 300 seconds)
    current_time = int(time.time())
    if current_time - timestamp > 300:
        return ErrorResponse(message="You can’t pair with yourself!")
    
    # Check these players haven't paired recently
    recent_scan_query = select(PlayerScan).where(
        or_(
            (PlayerScan.player_id == current_user.id) & (PlayerScan.qr_code_id == player_id),
            (PlayerScan.player_id == player_id) & (PlayerScan.qr_code_id == current_user.id)
        ),
        PlayerScan.scan_type == "peer",
        PlayerScan.next_scan_available_at > func.now()
    )
    result = await db.execute(recent_scan_query)
    recent_scan = result.scalars().first()

    if recent_scan:
        time_left = (recent_scan.next_scan_available_at - func.now()).total_seconds()
        minutes_left = int(time_left // 60) + 1
        return ErrorResponse(
            message=f"You paired with this player recently. Wait {minutes_left} minute(s) before pairing again."
        )

    # Check Proximity
    distance = calculate_distance(
        orig_location["latitude"],
        orig_location["longitude"],
        body.latitude,
        body.longitude
    )
    proximity_status = "far"
    if distance < 50:  # 50 meters threshold
        proximity_status = "near"

    # Fetch Player 1's info
    matched_player = await db.get(Player, uuid.UUID(player_id))
    if not matched_player:
        return ErrorResponse(message="The matched player no longer exists.")

    ###### SUCCESS ######
    scan_time = datetime.utcnow()
    next_scan_at = scan_time + timedelta(seconds=PEER_SCAN_COOLDOWN)
    # Scanner's record (current_user scans player_id)
    scanner_scan = PlayerScan(
        player_id=current_user.id,
        qr_code_id=None,
        peer_player_id = uuid.UUID(player_id),  # Using player_id as qr_code_id for peer scans
        scan_type="peer",
        proximity_status=proximity_status,
        success=True,
        latitude=body.latitude,
        longitude=body.longitude,
        scan_time=scan_time,
        next_scan_available_at=next_scan_at
    )
    db.add(scanner_scan)

    # Scanned player's record (player_id scanned by current_user)
    scanned_scan = PlayerScan(
        player_id=uuid.UUID(player_id),
        qr_code_id=None,
        peer_player_id=current_user.id,
        scan_type="peer",
        proximity_status=proximity_status,
        success=True,
        latitude=orig_location["latitude"],
        longitude=orig_location["longitude"],
        scan_time=scan_time,
        next_scan_available_at=next_scan_at
    )
    db.add(scanned_scan)

    await db.commit()
    # Prepare success message
    message = (
        f"Paired successfully with {matched_player.username}! "
        f"You’re {distance:.2f}m apart." if proximity_status == "near"
        else f"Paired remotely with {matched_player.username}!"
    )

    # Notify encoding player via Web Socket
    notification = json.dumps({
        "event": "peer_pairing_success",
        "paired_player": {
            "id": str(current_user.id),
            "username": current_user.username
        },
        "proximity_status": proximity_status,
        "message": f"{current_user.username} paired with you ({'Nearby' if proximity_status == 'near' else 'Remotely'})!"
    })
    await manager.broadcast_to_player(player_id, notification)

    # Success response to scanning/decoding client
    return PeerScanResponse(
        status="success",
        message=message,
        matched_player_id=player_id,
        matched_player_username=matched_player.username
    )