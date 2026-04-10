from decimal import Decimal

from src.db.session import SessionLocal
from src.domain import models


def seed_data():
    db = SessionLocal()

    try:
        print("Limpiando base de datos...")
        # 1. Borramos en orden: de hijos a padres para evitar FK violations
        db.query(models.OrderItem).delete()
        db.query(models.Order).delete()
        db.query(models.Inventory).delete()
        db.query(models.Product).delete()
        # Opcional: db.query(models.Customer).delete()

        db.commit()

        # 2. Crear el Catálogo
        ipa = models.Product(name="Pinta IPA", price=Decimal("3500.00"))
        burger = models.Product(name="Hamburguesa Môlt", price=Decimal("5500.00"))
        db.add_all([ipa, burger])
        db.commit()
        db.refresh(ipa)
        db.refresh(burger)

        # 3. Asignar Stock al Inventario
        inv_ipa = models.Inventory(product_id=ipa.id, stock_available=50)
        inv_burger = models.Inventory(product_id=burger.id, stock_available=20)
        db.add_all([inv_ipa, inv_burger])
        db.commit()

        print("✅ Datos iniciales insertados en PostgreSQL.")
        print(f"🍺 Pinta IPA ID: {ipa.id}")
        print(f"🍔 Hamburguesa ID: {burger.id}")

    except Exception as e:
        db.rollback()
        print(f"❌ Error durante el seed: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
