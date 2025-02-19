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
    expiration_date = Column(DateTime, nullable=True)  # Optional expiration (e.g., seasonal event)
    scan_cooldown_seconds = Column(Integer, nullable=True)  # Cooldown before re-scanning allowed
    max_scans_per_player = Column(Integer, nullable=True)  # Limits how many times a player can scan this
    is_repeatable = Column(Boolean, default=False)  # Determines if the QR code can be re-scanned after cooldown
    reward_data = Column(JSONB, nullable=True)  # JSON-encoded reward structure (future extensibility)
    encounter_id = Column(UUID(as_uuid=True), ForeignKey('encounters.id'), nullable=True)  # Links to an encounter if applicable


class Encounter(Base):
    __tablename__ = "encounters"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    qr_code_id = Column(UUID(as_uuid=True), ForeignKey('qr_codes.id'), nullable=True)  # Can be null if this is a shared encounter
    puzzle_type = Column(String)  # decryption, pattern, hacking
    difficulty_level = Column(Integer)
    data = Column(JSONB)
    repeatable = Column(Boolean, default=False)  # Determines if the event resets later
    expires_at = Column(DateTime, nullable=True)  # Optional expiration for seasonal encounters

class PlayerScan(Base):
    __tablename__ = "player_scans"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id = Column(UUID(as_uuid=True), ForeignKey('players.id'))
    qr_code_id = Column(UUID(as_uuid=True), ForeignKey('qr_codes.id'))
    scan_time = Column(DateTime(timezone=True), server_default=func.now())
    scan_type = Column(String, nullable=False, server_default="standard")
    proximity_status = Column(String) # Tracks status of geofenced validation
    success = Column(Boolean, default=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    attempt_number = Column(Integer, default=1)  # Tracks number of times player scanned this code
    next_scan_available_at = Column(DateTime, nullable=True)  # When player can scan it again (null if one-time use)
