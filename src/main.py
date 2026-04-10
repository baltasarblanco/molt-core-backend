import uuid
import redis
import json
from datetime import datetime
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.domain import models, schemas
from src.services.ai_service import parse_order_with_ai
from src.services.order_service import create_order_transaction
from src.services.websocket_manager import manager

# 1. Configuración de Rate Limiting
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Môlt Core API", version="0.1.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Conexión al escudo
# decode_responses=True nos permite manejar strings directamente en vez de bytes
cache = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

def shield_order(order_data):
    """
    Guarda la orden en memoria RAM antes de intentar 
    procesarla en la base de datos pesada.
    """
    try:
        order_id = order_data.get('order_id')
        # Guardamos el JSON de la orden con un tiempo de vida de 12hs
        cache.setex(f"pending_order:{order_id}", 43200, json.dumps(order_data))
        
        # Agregamos a una lista de 'últimos pedidos' para auditoría rápida
        cache.lpush("molt:audit_log", f"{datetime.now()}: {order_id} cached")
        cache.ltrim("molt:audit_log", 0, 99) # Solo guardamos los últimos 100 logs
        
        return True
    except Exception as e:
        print(f"⚠️ Fallo en el blindaje de Redis: {e}")
        return False

@app.post("/api/v1/orders", status_code=201)
@limiter.limit("5/minute")
async def place_order(
    request: Request,
    order_data: schemas.OrderCreate,
    db: Session = Depends(get_db),
):
    # Procesa el pedido con bloqueo pesimista e idempotencia en Redis
    order = create_order_transaction(db, order_data)

    # Broadcast a Live-Ops (Cocina/Barra)
    await manager.broadcast(
        {
            "event": "NEW_ORDER",
            "order_id": str(order.id),
            "customer": order_data.customer_name,
            "total": float(order.total_amount),
            "items": [{"product_id": str(i.product_id), "qty": i.quantity} for i in order.items],
        }
    )

    return {"status": "success", "order_id": order.id, "total": order.total_amount}


@app.post("/api/v1/orders/magic", status_code=201)
@limiter.limit("100/minute")
async def place_magic_order(request: Request, payload: dict, db: Session = Depends(get_db)):
    raw_text = payload.get("text", "")
    if not raw_text:
        raise HTTPException(status_code=400, detail="El campo 'text' es obligatorio")

    # 1. IA extrae los datos estructurados
    ai_data = parse_order_with_ai(raw_text)

    # 2. Mapeo Dinámico de Productos
    order_items = []
    for item in ai_data.get("items", []):
        keyword = item.get("product_keyword", "")
        product = db.query(models.Product).filter(models.Product.name.ilike(f"%{keyword}%")).first()

        if product:
            order_items.append(
                schemas.OrderItemCreate(product_id=product.id, quantity=item.get("qty", 1))
            )

    if not order_items:
        raise HTTPException(status_code=400, detail="No se reconocieron productos")

    # 3. Construcción del Schema validado
    order_data = schemas.OrderCreate(
        phone_number=ai_data.get("phone_number") or "+5400000000",
        customer_name=ai_data.get("customer_name") or "Cliente IA",
        items=order_items,
        idempotency_key=f"ai-{uuid.uuid4()}",
    )

    return await place_order(request, order_data, db)


@app.websocket("/ws/live-ops")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/health")
async def health_check():
    return {"status": "ok", "engine": "Bifrost", "version": "0.1.0"}
