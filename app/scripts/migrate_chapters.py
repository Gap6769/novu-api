import asyncio
from app.db.database import get_database, connect_to_mongo
from app.models.chapter import ChapterCreate
from app.repositories.chapter_repository import ChapterRepository
from app.repositories.novel_repository import NovelRepository


async def migrate_chapters():
    """Migrate chapters from novels collection to the new chapters collection."""
    # Initialize MongoDB connection
    await connect_to_mongo()
    db = get_database()

    chapter_repository = ChapterRepository(db)
    novel_repository = NovelRepository(db)

    # Get all novels
    novels = await novel_repository.get_all(limit=1000)

    total_chapters_migrated = 0
    total_novels_processed = 0

    for novel in novels:
        # Get the full novel document to access chapters
        novel_doc = await db.novels.find_one({"_id": novel.id})
        if not novel_doc or "chapters" not in novel_doc:
            continue

        chapters = novel_doc["chapters"]
        if not chapters:
            continue

        # Create chapters in the new collection
        for chapter in chapters:
            # Convert URL to string if it's an HttpUrl object
            url = str(chapter["url"]) if hasattr(chapter["url"], "str") else chapter["url"]

            chapter_create = ChapterCreate(
                novel_id=novel.id,
                title=chapter["title"],
                chapter_number=chapter["chapter_number"],
                chapter_title=chapter.get("chapter_title"),
                url=url,
                content_type="novel" if novel.type == "novel" else "manhwa",
                language=novel.source_language or "en",
            )

            # Create the chapter
            created_chapter = await chapter_repository.create(chapter_create)

            # Update chapter status if needed
            if chapter.get("read", False):
                await chapter_repository.mark_as_read(created_chapter.id)
            if chapter.get("downloaded", False):
                await chapter_repository.mark_as_downloaded(created_chapter.id, chapter.get("local_path", ""))

            total_chapters_migrated += 1

        # Remove chapters from the novel document
        await db.novels.update_one({"_id": novel.id}, {"$unset": {"chapters": ""}})

        total_novels_processed += 1
        print(f"Processed novel {novel.title} - Migrated {len(chapters)} chapters")

    print("\nMigration completed:")
    print(f"Total novels processed: {total_novels_processed}")
    print(f"Total chapters migrated: {total_chapters_migrated}")


if __name__ == "__main__":
    asyncio.run(migrate_chapters())
