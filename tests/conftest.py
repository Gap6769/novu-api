import pytest
from httpx import AsyncClient  # Usamos AsyncClient de httpx para manejo asíncrono
from motor.motor_asyncio import AsyncIOMotorClient
from app.main import app
from app.db.database import get_database
from tests.data import SOURCES_DATA, NOVELS_DATA


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


@pytest.fixture
def source_data():
    """Fixture que devuelve los datos de prueba para una fuente."""
    return SOURCES_DATA


@pytest.fixture
def all_sources_data():
    """Fixture que devuelve todos los datos de prueba de fuentes."""
    return SOURCES_DATA


@pytest.fixture
def tbate_novel():
    """Fixture que devuelve los datos de prueba para la novela de TBATE."""
    return NOVELS_DATA[0]


@pytest.fixture
def shadow_slave_novel():
    """Fixture que devuelve los datos de prueba para la novela de Shadow Slave."""
    return NOVELS_DATA[1]


@pytest.fixture
def eleceed_novel():
    """Fixture que devuelve los datos de prueba para la novela de Eleceed."""
    return NOVELS_DATA[2]


@pytest.fixture
def all_novels_data():
    """Fixture que devuelve todos los datos de prueba de novelas."""
    return NOVELS_DATA


@pytest.fixture
async def created_novels(client, all_novels_data):
    """Fixture que crea las novelas y las devuelve para su uso en los tests."""
    novels = []
    for novel_data in all_novels_data:
        response = await client.post("api/v1/novels/", json=novel_data)
        assert response.status_code == 201
        novels.append(response.json())
    return novels


@pytest.fixture
async def created_sources(client, all_sources_data):
    """Fixture que crea todas las fuentes en la base de datos y las devuelve."""
    sources = []
    for source_data in all_sources_data:
        response = await client.post("api/v1/sources/", json=source_data)
        assert response.status_code == 201
        sources.append(response.json())
    return sources
