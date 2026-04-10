from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        # Lista de conexiones activas
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Envía un mensaje JSON a todos los conectados (barra, cocina, etc)"""
        for connection in self.active_connections:
            await connection.send_json(message)


# Instancia única para toda la app (Singleton)
manager = ConnectionManager()
