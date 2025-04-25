import pytest
from app.models.source import SourceCreate
from tests.data.sources import SOURCES_DATA


@pytest.fixture
def source_data():
    """Fixture que devuelve los datos de prueba para una fuente."""
    return SOURCES_DATA[0]  # Devuelve los datos de novelbin


@pytest.fixture
def all_sources_data():
    """Fixture que devuelve todos los datos de prueba de fuentes."""
    return SOURCES_DATA


@pytest.fixture
async def created_source(test_db, source_data):
    """Fixture que crea una fuente en la base de datos y la devuelve."""
    from app.repositories.source_repository import SourceRepository

    source_repo = SourceRepository(test_db)
    source = SourceCreate(**source_data)
    created_source = await source_repo.create(source)
    return created_source


@pytest.fixture
async def created_sources(test_db, all_sources_data):
    """Fixture que crea todas las fuentes en la base de datos y las devuelve."""
    from app.repositories.source_repository import SourceRepository

    source_repo = SourceRepository(test_db)
    created_sources = []

    for source_data in all_sources_data:
        source = SourceCreate(**source_data)
        created_source = await source_repo.create(source)
        created_sources.append(created_source)

    return created_sources
