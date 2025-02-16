from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime

class PlayerBase(BaseModel):
    username: str
    email: EmailStr

class PlayerCreate(PlayerBase):
    password: str

class PlayerResponse(PlayerBase):
    id: int
    score: int
    level: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class QRCodeBase(BaseModel):
    code: str
    type: str
    data: Dict[str, Any]
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None

class QRCodeCreate(QRCodeBase):
    pass

class QRCodeResponse(QRCodeBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class ScanHistoryBase(BaseModel):
    qr_code_id: int
    outcome: Dict[str, Any]

class ScanHistoryCreate(ScanHistoryBase):
    player_id: int

class ScanHistoryResponse(ScanHistoryBase):
    id: int
    scanned_at: datetime
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
