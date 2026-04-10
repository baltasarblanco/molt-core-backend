from decimal import Decimal

from src.db.session import SessionLocal
from src.domain import models


def seed_data():
    db = SessionLocal()

    # Limpiar tablas para evitar duplicados si lo corrés dos veces
    db.query(models.Inventory).delete()
    db.query(models.Product).delete()

    # 1. Crear el Catálogo
    ipa = models.Product(name="Pinta IPA", price=Decimal("3500.00"))
    burger = models.Product(name="Hamburguesa Môlt", price=Decimal("5500.00"))
    db.add_all([ipa, burger])
    db.commit()
    db.refresh(ipa)
    db.refresh(burger)

    # 2. Asignar Stock al Inventario
    inv_ipa = models.Inventory(product_id=ipa.id, stock_available=50)  # Hay 50 pintas
    inv_burger = models.Inventory(product_id=burger.id, stock_available=20)  # Hay 20 burgers
    db.add_all([inv_ipa, inv_burger])
    db.commit()

    print("✅ Datos iniciales insertados en PostgreSQL.")
    print(f"🍺 Pinta IPA ID: {ipa.id}")
    print(f"🍔 Hamburguesa ID: {burger.id}")
    db.close()


if __name__ == "__main__":
    seed_data()
