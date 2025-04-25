import pytest
from httpx import AsyncClient  # Usamos AsyncClient de httpx para manejo asíncrono
from motor.motor_asyncio import AsyncIOMotorClient
from app.main import app
from app.db.database import get_database


@pytest.fixture(scope="function")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="function")
async def test_db():
    mongodb_url = "mongodb://localhost:27017"
    db_name = "test_novels_db"
    client = AsyncIOMotorClient(mongodb_url)
    db = client[db_name]

    # Limpiar la base de datos antes del test
    collections = await db.list_collection_names()
    for coll in collections:
        await db[coll].delete_many({})

    yield db

    # Limpiar después del test
    collections = await db.list_collection_names()
    for coll in collections:
        await db[coll].delete_many({})

    client.close()


@pytest.fixture(scope="function")
async def client(test_db):
    # Dependencia para sobrescribir la base de datos en las pruebas
    async def override_get_database():
        return test_db

    app.dependency_overrides[get_database] = override_get_database
    async with AsyncClient(app=app, base_url="http://test") as ac:  # Usamos AsyncClient
        yield ac
    app.dependency_overrides.clear()
