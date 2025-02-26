from utils.minigames.GameHandler import GameHandler
class RPSHandler(GameHandler):
    async def process_move(self, player_id: str, move: dict):
        self.state[player_id] = move["choice"]
        print(self.state, move['choice'])
        return len(self.state) < 2  # Continue if <2 moves

    async def check_winner(self):
        if len(self.state) != 2:
            return None
        p1, p2 = self.player_ids
        c1, c2 = self.state[p1], self.state[p2]
        if c1 == c2:
            return None
        if (c1 == "rock" and c2 == "scissors") or (c1 == "scissors" and c2 == "paper") or (c1 == "paper" and c2 == "rock"):
            return p1
        return p2