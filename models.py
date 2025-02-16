import uuid
from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from geoalchemy2 import Geography
from database import Base

class Player(Base):
    __tablename__ = "players"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)  # Added password hash field
    score = Column(Integer, default=0)
    level = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class QRCode(Base):
    __tablename__ = "qr_codes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String, unique=True, nullable=False)
    description = Column(String)
    scan_type = Column(String)  # item_drop, encounter, transportation
    location = Column(Geography(geometry_type='POINT', srid=4326))
    requires_location = Column(Boolean, default=False)

class Encounter(Base):
    __tablename__ = "encounters"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    qr_code_id = Column(UUID(as_uuid=True), ForeignKey('qr_codes.id'))
    puzzle_type = Column(String)  # decryption, pattern, hacking
    difficulty_level = Column(Integer)
    data = Column(JSONB)

class PlayerScan(Base):
    __tablename__ = "player_scans"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id = Column(UUID(as_uuid=True), ForeignKey('players.id'))
    qr_code_id = Column(UUID(as_uuid=True), ForeignKey('qr_codes.id'))
    scan_time = Column(DateTime(timezone=True), server_default=func.now())
    success = Column(Boolean, default=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
