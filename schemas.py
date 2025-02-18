from pydantic import BaseModel, UUID4
from datetime import datetime
from typing import Optional, List

class PlayerBase(BaseModel):
    username: str

class PlayerCreate(PlayerBase):
    password: str

class Player(PlayerBase):
    id: UUID4

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class QRLoginRequest(BaseModel):
    session_id: str

class QRLoginResponse(BaseModel):
    status: str
    message: Optional[str]

class QRScanRequest(BaseModel):
    qr_code: str
    latitude: Optional[float]
    longitude: Optional[float]

class QRScanResponse(BaseModel):
    status: str
    encounter_type: Optional[str]
    reward_data: Optional[dict]
    message: Optional[str]
    location_valid: Optional[bool]
    ok: Optional[bool]

class QRCodeMetadata(BaseModel):
    code: str
    description: str
    scan_type: str
    requires_location: bool

class ScanHistoryItem(BaseModel):
    qr_code: str
    scan_time: datetime
    success: bool

class PlayerHistory(BaseModel):
    scans: List[ScanHistoryItem]

class WebSocketMessage(BaseModel):
    event: str
    player_id: UUID4
    qr_code: str

class PeerScanRequest(BaseModel):
    peer_qr: str
    latitude: float
    longitude: float

class PeerScanResponse(BaseModel):
    status: str
    message: str = None
    matched_player_id: str = None
    matched_player_username: str = None

class ErrorResponse(BaseModel): # Not currently used
    status: str = "error"
    message: str