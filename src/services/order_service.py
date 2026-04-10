from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.db.redis import redis_client
from src.domain import models, schemas


def create_order_transaction(db: Session, order_data: schemas.OrderCreate):
    # 1. Idempotencia en REDIS (Capa de memoria ultra-rápida)
    redis_key = f"idempotency:{order_data.idempotency_key}"

    # nx=True asegura que solo se cree si NO existe. ex=86400 es 24hs.
    is_new = redis_client.set(redis_key, "processing", ex=86400, nx=True)

    if not is_new:
        # Si ya existe en Redis, lo buscamos en la DB y devolvemos la misma orden
        existing_order = (
            db.query(models.Order)
            .filter(models.Order.idempotency_key == order_data.idempotency_key)
            .first()
        )
        if existing_order:
            return existing_order
        # Si estaba en Redis pero no en DB (caso raro de fallo previo), seguimos.

    # 2. Identidad: Buscar o crear cliente
    customer = (
        db.query(models.Customer)
        .filter(models.Customer.phone_number == order_data.phone_number)
        .first()
    )
    if not customer:
        customer = models.Customer(
            phone_number=order_data.phone_number, name=order_data.customer_name
        )
        db.add(customer)
        db.flush()

    total_amount = Decimal("0.0")
    order_items_models = []

    try:
        # 3. TRANSACCIÓN CRÍTICA: Inventario con Bloqueo Pesimista
        for item in order_data.items:
            inventory = (
                db.query(models.Inventory)
                .filter(models.Inventory.product_id == item.product_id)
                .with_for_update()  # <-- LOCK DE FILA EN POSTGRES
                .first()
            )

            if not inventory:
                raise HTTPException(status_code=404, detail=f"Producto {item.product_id} no existe")

            if inventory.stock_available < item.quantity:
                raise HTTPException(
                    status_code=400, detail=f"Stock insuficiente para {item.product_id}"
                )

            # Descontar stock y calcular precios
            inventory.stock_available -= item.quantity
            product = db.query(models.Product).filter(models.Product.id == item.product_id).first()

            total_amount += product.price * item.quantity
            order_items_models.append(
                models.OrderItem(
                    product_id=product.id, quantity=item.quantity, unit_price=product.price
                )
            )

        # 4. Consolidar Orden
        new_order = models.Order(
            customer_id=customer.id,
            total_amount=total_amount,
            idempotency_key=order_data.idempotency_key,
            items=order_items_models,
        )
        db.add(new_order)
        db.commit()
        db.refresh(new_order)
        return new_order

    except Exception as e:
        db.rollback()
        # Si falló la DB, borramos la llave de Redis para permitir reintento
        redis_client.delete(redis_key)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail="Error interno del motor transaccional") from e
