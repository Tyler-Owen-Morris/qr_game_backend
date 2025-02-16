from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class Player(Base):
    __tablename__ = "players"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    score = Column(Integer, default=0)
    level = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    scans = relationship("ScanHistory", back_populates="player")

class QRCode(Base):
    __tablename__ = "qr_codes"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)
    type = Column(String)  # puzzle, reward, transport
    data = Column(JSON)  # Stores type-specific data
    location_lat = Column(Float, nullable=True)
    location_lng = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ScanHistory(Base):
    __tablename__ = "scan_history"
    
    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"))
    qr_code_id = Column(Integer, ForeignKey("qr_codes.id"))
    outcome = Column(JSON)
    scanned_at = Column(DateTime(timezone=True), server_default=func.now())
    
    player = relationship("Player", back_populates="scans")
    qr_code = relationship("QRCode")
