from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Dict, Set, List, Tuple
import json
import asyncio
import asyncpg
import os
import logging
import uuid
import random
#from auth.utils import get_current_user_from_token
from utils.minigames.rps_handler import RPSHandler
from utils.minigames.GameHandler import GameHandler
from urllib.parse import urlparse, urlunparse
from dotenv import load_dotenv
load_dotenv()

router = APIRouter()
logger = logging.getLogger(__name__)
game_registry = {
    "rps": RPSHandler
}

class ConnectionManager:
    def __init__(self):
        # Store player connections
        self.active_player_connections: Dict[str, List[Tuple[WebSocket, str]]] = {}
        # Store login session connections
        self.login_session_connections: Dict[str, WebSocket] = {}
        # Store Game Sessions
        self.games: Dict[str, GameHandler] = {}  # channel_id -> GameHandler instance

    async def connect_player(self, websocket: WebSocket, player_id: str, connecting_player_id: str):
        if player_id not in self.active_player_connections:
            self.active_player_connections[player_id] = []
        if len(self.active_player_connections[player_id]) >= 2:
            await websocket.send_text(json.dumps({"event": "rejected", "reason": "game_full"}))
            await websocket.close()
            return False
        self.active_player_connections[player_id].append((websocket, connecting_player_id))
        await websocket.accept()
        return True

    async def connect_login_session(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.login_session_connections[session_id] = websocket

    def disconnect_player(self, websocket: WebSocket, player_id: str):
        print("Disconnecting",player_id)
        if player_id in self.active_player_connections:
            self.active_player_connections[player_id] = [(ws, pid) for ws, pid in self.active_player_connections[player_id] if ws != websocket]
            if not self.active_player_connections[player_id]:
                del self.active_player_connections[player_id]

    def disconnect_login_session(self, session_id: str):
        if session_id in self.login_session_connections:
            del self.login_session_connections[session_id]

    async def broadcast_to_player(self, player_id: str, message: str):
        if player_id in self.active_player_connections:
            for connection in self.active_player_connections[player_id]:
                print(connection[0].application_state)
                await connection[0].send_text(message)
    
    async def broadcast_game_message(self, player_id: str, message: str):
        if player_id not in self.active_player_connections:
            return  # No players - nothing to broadcast
        
        # Ensure all WebSockets are accepted
        for websocket, _ in self.active_player_connections[player_id]:
            # No need to re-accept - already done in connect_player
            await websocket.send_text(message)
        
        # Start game if two players and no game exists
        if len(self.active_player_connections[player_id]) == 2 and player_id not in self.games:
            player_ids = [pid for _, pid in self.active_player_connections[player_id]]
            game_type = "rps"  # Hardcode for now
            self.games[player_id] = game_registry[game_type](player_ids)
            start_message = json.dumps({
                "event": "start_game",
                "game_type": game_type,
                "players": player_ids
            })
            # Broadcast start game to all players
            for websocket, _ in self.active_player_connections[player_id]:
                await websocket.send_text(start_message)

    async def send_login_success(self, session_id: str, token: str):
        if session_id in self.login_session_connections:
            print(session_id,token)
            await self.login_session_connections[session_id].send_text(
                json.dumps({
                    "event": "login_success",
                    "token": token
                })
            )
            # Clean up the login session after successful login
            self.disconnect_login_session(session_id)

manager = ConnectionManager()

async def database_listener():
    raw_url = os.getenv("DATABASE_URL")
    parsed = urlparse(raw_url)
    clean_url = urlunparse(("postgresql", parsed.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    conn = await asyncpg.connect(clean_url)
    await conn.add_listener('qr_scan', handle_notification)
    await conn.add_listener('player_interaction', handle_notification)
    while True:
        await asyncio.sleep(1)

async def handle_notification(conn, pid, channel, payload):
    data = json.loads(payload)
    event_type = data.get('event_type')

    if event_type == 'qr_scan':
        player_id = data['player_id']
        await manager.broadcast_to_player(
            player_id,
            json.dumps({
                "event": "qr_scan",
                "player_id": player_id,
                "qr_code": data['qr_code']
            })
        )
    elif event_type == 'player_interaction':
        # Handle player-to-player interaction notifications
        for player_id in [data['player1_id'], data['player2_id']]:
            await manager.broadcast_to_player(
                player_id,
                json.dumps({
                    "event": "player_interaction",
                    "interaction_type": data['interaction_type'],
                    "success": data['success'],
                    "message": data.get('message')
                })
            )

@router.websocket("/ws/player/{player_id}")
async def player_websocket_endpoint(websocket: WebSocket, player_id: str, player2_id: str = Query(None)):
    # Assume connecting_player_id is passed via auth or query param - mock for now
    connecting_player_id = player2_id if player2_id else player_id
    
    # Connect the player and check if accepted (enforces two-player limit)
    is_accepted = await manager.connect_player(websocket, player_id, connecting_player_id)
    if not is_accepted:
        return  # Exit early if rejected (e.g., third player)
    
    # Start game when two players are connected
    print("active games before deciding to start or not:", manager.games, flush=True)
    if len(manager.active_player_connections[player_id]) == 2 and player_id not in manager.games:
        player_ids = [pid for _, pid in manager.active_player_connections[player_id]]
        game_type = 'rps'
        manager.games[player_id] = game_registry[game_type](player_ids)
        print("making new game",flush=True)
        await manager.broadcast_to_player(player_id, json.dumps({
            "event": "start_game",
            "game_type": game_type,
            "players": player_ids
        }))
    
    # Handle messages (moves and game logic)
    try:
        while True:
            data = await websocket.receive_text()
            data_dict = json.loads(data)
            if data_dict.get("event") == "move":
                print("move detected", data_dict,flush=True)
                game = manager.games.get(player_id)
                if game and data_dict["player_id"] in game.player_ids:
                    game_continues = await game.process_move(data_dict["player_id"], data_dict["data"])
                    if not game_continues:
                        winner = await game.check_winner()
                        if not winner:
                            winner = "tie"
                        await manager.broadcast_to_player(player_id, json.dumps({
                            "event": "result",
                            "winner": winner
                        }))
                        # for ws, _ in manager.active_player_connections[player_id]:
                        #     await ws.close()
                        del manager.games[player_id]  # Clear game state after result
            elif data_dict.get("event") == "request_game_state":
                print("Received request_game_state from:", data_dict["player_id"])
                game = manager.games.get(player_id)
                if game:
                    # Resend existing game state
                    await manager.broadcast_to_player(player_id, json.dumps({
                        "event": "start_game",
                        "game_type": "rps",
                        "players": game.player_ids
                    }))
                elif len(manager.active_player_connections[player_id]) == 2:
                    # Create new game if 2 players are connected
                    player_ids = [pid for _, pid in manager.active_player_connections[player_id]]
                    game_type = "rps"
                    manager.games[player_id] = game_registry[game_type](player_ids)
                    await manager.broadcast_to_player(player_id, json.dumps({
                        "event": "start_game",
                        "game_type": game_type,
                        "players": player_ids
                    }))
    except WebSocketDisconnect:
        manager.disconnect_player(websocket, player_id)

@router.websocket("/ws/login/{session_id}")
async def login_websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect_login_session(websocket, session_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_login_session(session_id)

@router.on_event("startup")
async def startup_event():
    asyncio.create_task(database_listener())