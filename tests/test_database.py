import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from app.db.database import db_manager, connect_to_mongo, close_mongo_connection


@pytest.mark.asyncio
async def test_connect_to_mongo():
    # Conectar a la base de datos
    await connect_to_mongo()
    
    # Comprobar si la conexión fue exitosa
    assert db_manager.client is not None
    assert db_manager.db is not None
    
    # Comprobar si se puede obtener la base de datos
    db = db_manager.get_db()
    assert db is not None

    # Verificar que la base de datos responde
    response = await db.command('ping')
    assert response.get('ok') == 1

    # Cerrar la conexión
    await close_mongo_connection()
    
    # Verificar que la conexión fue cerrada
    assert db_manager.client is None
    assert db_manager.db is None
