import pytest


@pytest.mark.anyio
async def test_create_novel(client):
    data = {
        "title": "Test Novel",
        "author": "Author Name",
        "cover_image_url": "http://example.com/image.jpg",
        "description": "Test description",
        "source_url": "http://example.com",
        "source_name": "Test Source",
        "source_language": "en",
        "tags": ["test", "novel"],
        "status": "ongoing",
        "type": "novel",
    }
    response = await client.post("api/v1/novels/", json=data)
    assert response.status_code == 201
    response_data = response.json()
    assert response_data["title"] == data["title"]
    assert response_data["author"] == data["author"]

    response = await client.get("api/v1/novels/")
