import pytest


@pytest.mark.anyio
async def test_create_novels(created_novels):
    """Test que verifica que las novelas se crearon correctamente."""
    assert len(created_novels) == 3

    # Verificar que cada novela tiene los campos requeridos
    for novel in created_novels:
        assert "title" in novel
        assert "author" in novel
        assert "type" in novel
        assert "_id" in novel
        assert "added_at" in novel
        assert "total_chapters" in novel
        assert "read_chapters" in novel
        assert "downloaded_chapters" in novel
        assert "reading_progress" in novel


@pytest.mark.anyio
async def test_get_all_novels(client, created_novels):
    """Test que verifica la obtención de todas las novelas."""
    response = await client.get("api/v1/novels/")
    assert response.status_code == 200
    novels = response.json()

    # Verificar que tenemos las tres novelas
    assert len(novels) == 3

    # Verificar que cada novela tiene los campos requeridos
    for novel in novels:
        assert "title" in novel
        assert "author" in novel
        assert "type" in novel
        assert "_id" in novel
        assert "added_at" in novel


@pytest.mark.anyio
async def test_filter_novels_by_type(client, created_novels):
    """Test que verifica el filtrado de novelas por tipo."""
    # Filtrar por tipo "novel"
    response = await client.get("api/v1/novels/?type=novel")
    assert response.status_code == 200
    novels = response.json()
    assert len(novels) == 2  # TBATE y Shadow Slave

    # Filtrar por tipo "manhwa"
    response = await client.get("api/v1/novels/?type=manhwa")
    assert response.status_code == 200
    novels = response.json()
    assert len(novels) == 1  # Eleceed


@pytest.mark.anyio
async def test_get_novel_by_id(client, created_novels):
    """Test que verifica la obtención de una novela por ID."""
    # Usar la primera novela creada (TBATE)
    novel_id = created_novels[0]["_id"]

    # Obtener la novela por ID
    response = await client.get(f"api/v1/novels/{novel_id}")
    assert response.status_code == 200
    novel = response.json()

    # Verificar que es la misma novela
    assert novel["_id"] == novel_id
    assert novel["title"] == created_novels[0]["title"]
    assert novel["author"] == created_novels[0]["author"]


@pytest.mark.anyio
async def test_update_novel(client, created_novels):
    """Test que verifica la actualización de una novela."""
    # Usar la primera novela creada (TBATE)
    novel_id = created_novels[0]["_id"]

    # Actualizar la novela
    update_data = {"title": "The Beginning After The End - Updated", "status": "Completed"}
    response = await client.patch(f"api/v1/novels/{novel_id}", json=update_data)
    assert response.status_code == 200
    updated_novel = response.json()

    # Verificar los cambios
    assert updated_novel["title"] == update_data["title"]
    assert updated_novel["status"] == update_data["status"]
    # Verificar que otros campos no cambiaron
    assert updated_novel["author"] == created_novels[0]["author"]
    assert updated_novel["description"] == created_novels[0]["description"]
