from abc import ABC, abstractmethod
from typing import Optional, List



class GameHandler(ABC):
    def __init__(self, player_ids: List[str]):
        self.player_ids = player_ids
        self.state = {}

    @abstractmethod
    async def process_move(self, player_id: str, move: dict) -> bool:
        pass  # True if game continues, False if ended

    @abstractmethod
    async def check_winner(self) -> Optional[str]:
        pass  # Returns winner player_id or None for tie/in-progress