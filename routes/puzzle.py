from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database import get_db
from models import Player, QRCode, ScanHistory
from auth import get_current_user
import random

router = APIRouter()

PUZZLE_TYPES = {
    "math": lambda: generate_math_puzzle(),
    "riddle": lambda: generate_riddle_puzzle(),
    "sequence": lambda: generate_sequence_puzzle()
}

@router.get("/generate/{qr_code_id}")
async def generate_puzzle(
    qr_code_id: int,
    current_user: Player = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify QR code exists and is puzzle type
    result = await db.execute(
        select(QRCode).filter(QRCode.id == qr_code_id)
    )
    qr_code = result.scalar_one_or_none()
    
    if not qr_code or qr_code.type != "puzzle":
        raise HTTPException(status_code=404, detail="Puzzle not found")
    
    # Get puzzle type from QR data
    puzzle_type = qr_code.data.get("puzzle_type", "math")
    difficulty = qr_code.data.get("difficulty", "easy")
    
    if puzzle_type not in PUZZLE_TYPES:
        puzzle_type = "math"
    
    puzzle = PUZZLE_TYPES[puzzle_type]()
    puzzle["difficulty"] = difficulty
    
    return puzzle

@router.post("/solve/{qr_code_id}")
async def solve_puzzle(
    qr_code_id: int,
    solution: str,
    current_user: Player = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify QR code exists
    result = await db.execute(
        select(QRCode).filter(QRCode.id == qr_code_id)
    )
    qr_code = result.scalar_one_or_none()
    
    if not qr_code:
        raise HTTPException(status_code=404, detail="Puzzle not found")
    
    # Get last scan for this QR code
    result = await db.execute(
        select(ScanHistory)
        .filter(ScanHistory.player_id == current_user.id)
        .filter(ScanHistory.qr_code_id == qr_code_id)
        .order_by(ScanHistory.scanned_at.desc())
    )
    scan = result.scalar_one_or_none()
    
    if not scan:
        raise HTTPException(status_code=400, detail="Must scan QR code first")
    
    # Verify solution
    if verify_solution(qr_code.data["puzzle_type"], solution, scan.outcome):
        points = calculate_points(qr_code.data["difficulty"])
        current_user.score += points
        db.add(current_user)
        await db.commit()
        
        return {
            "success": True,
            "points": points,
            "message": "Puzzle solved correctly!"
        }
    
    return {
        "success": False,
        "message": "Incorrect solution, try again"
    }

def generate_math_puzzle():
    operations = ["+", "-", "*"]
    op = random.choice(operations)
    a = random.randint(1, 20)
    b = random.randint(1, 20)
    
    if op == "+":
        answer = a + b
    elif op == "-":
        answer = a - b
    else:
        answer = a * b
    
    return {
        "type": "math",
        "question": f"What is {a} {op} {b}?",
        "answer": str(answer)
    }

def generate_riddle_puzzle():
    riddles = [
        {
            "question": "What has keys, but no locks; space, but no room; you can enter, but not go in?",
            "answer": "keyboard"
        },
        {
            "question": "What gets wetter and wetter the more it dries?",
            "answer": "towel"
        }
    ]
    return random.choice(riddles)

def generate_sequence_puzzle():
    start = random.randint(1, 10)
    step = random.randint(2, 5)
    sequence = [start + (step * i) for i in range(4)]
    answer = start + (step * 4)
    
    return {
        "type": "sequence",
        "question": f"What comes next in the sequence: {', '.join(map(str, sequence))}?",
        "answer": str(answer)
    }

def verify_solution(puzzle_type: str, user_solution: str, puzzle_data: dict):
    return user_solution.lower().strip() == puzzle_data["answer"].lower().strip()

def calculate_points(difficulty: str):
    points = {
        "easy": 10,
        "medium": 20,
        "hard": 30
    }
    return points.get(difficulty, 10)
