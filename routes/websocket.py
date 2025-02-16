from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json
import asyncio
import asyncpg
import os
import logging
import uuid

router = APIRouter()
logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Store player connections
        self.active_player_connections: Dict[str, Set[WebSocket]] = {}
        # Store login session connections
        self.login_session_connections: Dict[str, WebSocket] = {}

    async def connect_player(self, websocket: WebSocket, player_id: str):
        await websocket.accept()
        if player_id not in self.active_player_connections:
            self.active_player_connections[player_id] = set()
        self.active_player_connections[player_id].add(websocket)

    async def connect_login_session(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.login_session_connections[session_id] = websocket

    def disconnect_player(self, websocket: WebSocket, player_id: str):
        self.active_player_connections[player_id].remove(websocket)
        if not self.active_player_connections[player_id]:
            del self.active_player_connections[player_id]

    def disconnect_login_session(self, session_id: str):
        if session_id in self.login_session_connections:
            del self.login_session_connections[session_id]

    async def broadcast_to_player(self, player_id: str, message: str):
        if player_id in self.active_player_connections:
            for connection in self.active_player_connections[player_id]:
                await connection.send_text(message)

    async def send_login_success(self, session_id: str, token: str):
        if session_id in self.login_session_connections:
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
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    await conn.add_listener('qr_scan', handle_notification)
    await conn.add_listener('player_interaction', handle_notification)

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
async def player_websocket_endpoint(websocket: WebSocket, player_id: str):
    await manager.connect_player(websocket, player_id)
    try:
        while True:
            await websocket.receive_text()
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