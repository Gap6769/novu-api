import pytest


@pytest.mark.anyio
async def test_fetch_chapters(client, created_sources, created_novels):
    """Test que verifica la obtención de todos los capítulos de una novela."""
    novel_id = created_novels[0]["_id"]
    response = await client.post(f"api/v1/novels/{novel_id}/chapters/fetch")
    assert response.status_code == 200
    chapters = response.json()
    assert len(chapters) > 0
