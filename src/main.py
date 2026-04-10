from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.domain import schemas
from src.services.order_service import create_order_transaction
from src.services.websocket_manager import manager

# Inicialización del limitador por IP
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Môlt Core API", version="0.1.0")

# Conectamos el limitador al estado de la app y registramos el manejador de errores
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.post("/api/v1/orders", status_code=201)
@limiter.limit("5/minute")
async def place_order(
    request: Request,  # Requerido por slowapi para trackear la IP
    order_data: schemas.OrderCreate,
    db: Session = Depends(get_db),
):
    """
    Endpoint transaccional con Rate Limiting.
    Procesa el pedido y notifica en tiempo real a la cocina.
    """
    # 1. Ejecutamos la transacción pesada en la DB (con validación de idempotencia en Redis)
    order = create_order_transaction(db, order_data)

    # 2. Si la DB confirmó, emitimos el evento vía WebSockets
    await manager.broadcast(
        {
            "event": "NEW_ORDER",
            "order_id": str(order.id),
            "customer": order_data.customer_name,
            "total": float(order.total_amount),
            "items": [
                {"product_id": str(i.product_id), "qty": i.quantity} for i in order_data.items
            ],
        }
    )

    return {"status": "success", "order_id": order.id, "total": order.total_amount}


@app.websocket("/ws/live-ops")
async def websocket_endpoint(websocket: WebSocket):
    """Canal de baja latencia para la pantalla de la cocina."""
    await manager.connect(websocket)
    try:
        while True:
            # Espera mensajes o simplemente mantiene el keep-alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/health")
async def health_check():
    return {"status": "ok", "engine": "Bifrost"}
