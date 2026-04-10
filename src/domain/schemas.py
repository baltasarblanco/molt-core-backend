from uuid import UUID

from pydantic import BaseModel, Field


class OrderItemCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0, description="La cantidad debe ser mayor a 0")


class OrderCreate(BaseModel):
    phone_number: str = Field(..., max_length=20)
    customer_name: str = Field(..., max_length=100)
    items: list[OrderItemCreate]
    idempotency_key: str = Field(
        ..., description="Clave única generada por el frontend para evitar pagos dobles"
    )
