# Project Bifrost: Môlt Core Engine 🍺

**Bifrost** es el núcleo transaccional de grado Enterprise diseñado para la gestión operativa y de fidelización de Môlt. El sistema está optimizado para garantizar integridad absoluta en el manejo de inventario bajo escenarios de alta concurrencia y telemetría en tiempo real.

## 🛠️ Filosofía de Ingeniería
El proyecto se aleja de las soluciones commodity (CRUDs tradicionales) para enfocarse en:
- **Integridad Transaccional:** Uso de bloqueos pesimistas (`SELECT ... FOR UPDATE`) para garantizar 0% de overbooking.
- **Resiliencia:** Capa de idempotencia distribuida mediante Redis para mitigar fallos de red en el cliente.
- **Baja Latencia:** Comunicación asíncrona vía WebSockets para Live-Ops en cocina y barra.
- **Código Estricto:** Validación estática con Ruff (+700 reglas) y tipado fuerte con Pydantic v2.

## 🏗️ Stack Tecnológico
- **Lenguaje:** Python 3.12+ (Gestionado con `uv` para máxima velocidad).
- **Framework:** FastAPI (Asíncrono).
- **ORM:** SQLAlchemy 2.0 (Mapeo imperativo y DeclarativeBase).
- **Infraestructura:** PostgreSQL 16 + Redis 7 (Dockerized).
- **Migraciones:** Alembic.

## 🚀 Key Features Implementadas

### 1. Motor de Órdenes Atómico
Implementación de un flujo de checkout que bloquea las filas de inventario a nivel de hardware/base de datos, asegurando que cada pinta de cerveza descontada tenga un respaldo real en stock, eliminando Race Conditions.

### 2. Escudo de Idempotencia Híbrido
Uso de un patrón **Cache-Aside con Redis** para interceptar peticiones duplicadas en nanosegundos, protegiendo a la base de datos relacional de carga innecesaria.

### 3. Live-Ops Broadcast
Sistema de notificación push basado en WebSockets que reduce el *Ticket Time* operativo, enviando los pedidos a la cocina de forma instantánea tras la confirmación del pago.

## 📦 Instalación y Setup (Linux Pop!_OS)

1. **Clonar y Entorno:**
   ```bash
   git clone [https://github.com/baltasarblanco/molt-core-backend.git](https://github.com/baltasarblanco/molt-core-backend.git)
   cd molt-core-backend
   uv venv && source .venv/bin/activate
   uv pip install -e ".[dev]"
   ```
2. **Infraestructura:**
    ```bash
    docker compose up -d
    ```
3. **Migraciones y Seed:**
    ```bash
    alembic upgrade head
    python -m src.seed
    ```
## 📈 KPIs de Ingeniería (Target)

| Métrica          | Objetivo                          |
|------------------|-----------------------------------|
| 🔹 Latencia P99  | `< 50ms` (API) / `< 10ms` (WS)    |
| 🔹 Consistencia  | `100%` (0 colisiones de stock)    |
| 🔹 Cobertura     | `> 90%` logic coverage            |