import json
import uuid

import redis
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import or_
from sqlalchemy.orm import Session

# Importaciones de tu proyecto
from src.db.session import get_db
from src.domain import models, schemas
from src.services.ai_service import parse_order_with_ai
from src.services.order_service import create_order_transaction
from src.services.websocket_manager import manager

# 1. Configuración de Rate Limiting
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Môlt Core API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 2. Configuración de Redis
cache = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)


def shield_order(order_data_dict):
    """Guarda la orden en memoria RAM para persistencia rápida."""
    try:
        order_id = str(order_data_dict.get("order_id"))
        cache.setex(f"pending_order:{order_id}", 43200, json.dumps(order_data_dict))
        return True
    except Exception as e:
        print(f"⚠️ Fallo en el blindaje de Redis: {e}")
        return False


# 3. Endpoints de Órdenes
@app.post("/api/v1/orders", status_code=201)
@limiter.limit("5/minute")
async def place_order(
    request: Request,
    order_data: schemas.OrderCreate,
    db: Session = Depends(get_db),
):
    order = create_order_transaction(db, order_data)

    items_formatted = []
    for i in order.items:
        product = db.query(models.Product).filter(models.Product.id == i.product_id).first()
        items_formatted.append(
            {
                "name": product.name if product else "Producto",
                "qty": i.quantity,
                "product_id": str(i.product_id),
            }
        )

    broadcast_data = {
        "event": "NEW_ORDER",
        "order_id": str(order.id),
        "customer": order_data.customer_name,
        "total": float(order.total_amount),
        "items": items_formatted,
    }

    shield_order(broadcast_data)
    await manager.broadcast(broadcast_data)

    return {"status": "success", "order_id": order.id, "total": order.total_amount}


@app.post("/api/v1/orders/magic", status_code=201)
@limiter.limit("100/minute")
async def place_magic_order(request: Request, payload: dict, db: Session = Depends(get_db)):
    raw_text = payload.get("text", "")
    if not raw_text:
        raise HTTPException(status_code=400, detail="El campo 'text' es obligatorio")

    ai_data = parse_order_with_ai(raw_text)

    order_items = []
    for item in ai_data.get("items", []):
        keyword = item.get("product_keyword", "").strip()
        if not keyword:
            continue
        keyword_singular = keyword.rstrip("s") if len(keyword) > 3 else keyword

        product = (
            db.query(models.Product)
            .filter(
                or_(
                    models.Product.name.ilike(f"%{keyword}%"),
                    models.Product.name.ilike(f"%{keyword_singular}%"),
                )
            )
            .first()
        )

        if product:
            order_items.append(
                schemas.OrderItemCreate(product_id=product.id, quantity=item.get("qty", 1))
            )

    if not order_items:
        raise HTTPException(status_code=400, detail="No se reconocieron productos")

    order_data = schemas.OrderCreate(
        phone_number=ai_data.get("phone_number") or "+5400000000",
        customer_name=ai_data.get("customer_name") or "Cliente IA",
        items=order_items,
        idempotency_key=f"ai-{uuid.uuid4()}",
    )

    return await place_order(request, order_data, db)


@app.get("/api/v1/orders/active")
async def get_active_orders(db: Session = Depends(get_db)):
    """Recupera órdenes PENDING para el Dashboard."""
    active_orders = db.query(models.Order).filter(models.Order.status == "PENDING").all()

    result = []
    for o in active_orders:
        items_detail = []
        for item in o.items:
            p = db.query(models.Product).filter(models.Product.id == item.product_id).first()
            items_detail.append(
                {
                    "name": p.name if p else "Producto",
                    "qty": item.quantity,
                    "product_id": str(item.product_id),
                }
            )

        result.append(
            {
                "order_id": str(o.id),
                "customer": getattr(o, "customer_name", "Cliente Môlt"),
                "total": float(o.total_amount),
                "items": items_detail,
            }
        )

    return result


@app.patch("/api/v1/orders/{order_id}/status")
async def update_order_status(order_id: str, payload: dict, db: Session = Depends(get_db)):
    new_status = payload.get("status")
    print(f"📡 Intentando cambiar orden {order_id} a estado: {new_status}")

    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    try:
        order.status = new_status
        db.commit()
        cache.delete(f"pending_order:{order_id}")
        print(f"✅ Orden {order_id} actualizada correctamente en DB.")
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        print(f"❌ Error de base de datos: {e}")
        # Fix Ruff B904: Encadenamos el error con 'from e'
        raise HTTPException(status_code=400, detail=str(e)) from e


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
    return {"status": "ok", "redis": cache.ping()}
