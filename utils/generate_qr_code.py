import uuid
import random
from datetime import datetime, timedelta
from geoalchemy2 import WKTElement
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import QRCode, Encounter  # Assuming your models are imported here

# Define possible scan types
SCAN_TYPES = ["item_drop", "encounter", "transportation"]
PUZZLE_TYPES = ["decryption", "pattern", "hacking"]

# Define possible item types
ITEM_TYPES = ["intel_file", "spy_gadget", "digital_currency", "weapon_upgrade", "hacking_tool"]

# Define item properties
ITEM_DATA = {
    "intel_file": {
        "rarity": "common",
        "description": "A classified document containing sensitive information.",
        "value": 10
    },
    "spy_gadget": {
        "rarity": "uncommon",
        "description": "A high-tech gadget used by elite spies.",
        "value": 50
    },
    "digital_currency": {
        "rarity": "rare",
        "description": "Encrypted credits used in underground markets.",
        "value": 100
    },
    "weapon_upgrade": {
        "rarity": "epic",
        "description": "Enhances your existing weapon capabilities.",
        "value": 150
    },
    "hacking_tool": {
        "rarity": "legendary",
        "description": "A powerful tool that can bypass the most secure systems.",
        "value": 200
    }
}

# Define cooldown ranges (in seconds)
COOLDOWN_RANGES = {
    "item_drop": (3600, 86400),  # 1 hour to 24 hours
    "encounter": (1800, 43200),  # 30 minutes to 12 hours
    "transportation": (0, 0)  # No cooldown needed
}

# Define max scan limits per player
SCAN_LIMITS = {
    "item_drop": 1,  # One-time items
    "encounter": 3,  # Can retry puzzles up to 3 times
    "transportation": None  # Unlimited usage
}

# Define probabilities for encounters vs. items vs. transportation
QR_TYPE_PROBABILITIES = {
    "item_drop": 0.6,  # 60% chance to be an item
    "encounter": 0.3,  # 30% chance for an encounter
    "transportation": 0.1  # 10% chance for transportation
}

async def generate_qr_code(scan_code: str, db: AsyncSession, latitude: float = None, longitude: float = None) -> QRCode:
    """
    Generates a new QR code entry in the database with randomized properties.
    """
    # Check if QR code already exists
    existing_qr_code = await db.execute(select(QRCode).where(QRCode.code == scan_code))
    existing_qr_code = existing_qr_code.scalars().first()
    
    if existing_qr_code:
        return existing_qr_code
    
    scan_type = random.choices(list(QR_TYPE_PROBABILITIES.keys()), weights=QR_TYPE_PROBABILITIES.values())[0]
    
    # Determine cooldown and scan limits based on type
    cooldown_seconds = random.randint(*COOLDOWN_RANGES[scan_type])
    max_scans_per_player = SCAN_LIMITS[scan_type]

    # Determine repeatability
    is_repeatable = scan_type != "item_drop"  # Only encounters & transportation are repeatable

    # Set an expiration date (optional, for seasonal events)
    expiration_date = datetime.utcnow() + timedelta(days=random.randint(30, 365)) if random.random() < 0.2 else None

    # Generate QR code entry
    qr_code = QRCode(
        id=uuid.uuid4(),
        code=scan_code,
        description=f"Generated QR Code {scan_code}",
        scan_type=scan_type,
        requires_location=(random.random() < 0.5),  # 50% chance location is required
        location=WKTElement(f"POINT({longitude} {latitude})", srid=4326) if latitude and longitude else None,
        scan_cooldown_seconds=cooldown_seconds,
        max_scans_per_player=max_scans_per_player,
        is_repeatable=is_repeatable,
        expiration_date=expiration_date,
        reward_data={},  # Empty for now, can be extended later
    )

    db.add(qr_code)
    await db.flush()

    # If an encounter, generate associated encounter entry
    if scan_type == "encounter":
        encounter = Encounter(
            id=uuid.uuid4(),
            qr_code_id=qr_code.id,
            puzzle_type=random.choice(PUZZLE_TYPES),
            difficulty_level=random.randint(1, 5),
            data={},  # Placeholder for future puzzle generation
            repeatable=is_repeatable,
            expires_at=expiration_date,
        )
        db.add(encounter)
        await db.flush()

        qr_code.encounter_id = encounter.id  # Link the QR code to the encounter
        
        # Add encounter details to reward_data
        qr_code.reward_data = {
            "type": "encounter",
            "puzzle_type": encounter.puzzle_type,
            "difficulty_level": encounter.difficulty_level,
            "repeatable": encounter.repeatable,
            "expires_at": encounter.expires_at.isoformat() if encounter.expires_at else None
        }

    # If transportation, generate transportation details
    elif scan_type == "transportation":
        destination_name = f"Secret Location {uuid.uuid4().hex[:6]}"  # Generate a name
        qr_code.reward_data = {
            "type": "transportation",
            "destination": destination_name,
            "coordinates": {
                "latitude": latitude,
                "longitude": longitude
            } if latitude and longitude else None
        }

        # If item drop, assign a random item
    elif scan_type == "item_drop":
        selected_item = random.choice(ITEM_TYPES)
        item_details = ITEM_DATA[selected_item]

        qr_code.reward_data = {
            "type": "item_drop",
            "item_name": selected_item.replace("_", " ").title(),
            "rarity": item_details["rarity"],
            "description": item_details["description"],
            "value": item_details["value"]
        }
    db.add(qr_code)
    await db.flush()
    
    return qr_code
