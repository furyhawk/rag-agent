"""Simple smoke test for document upload endpoint."""
import asyncio
from rag_agent.app import create_app
from rag_agent.core.config import Settings

async def test_app_creation():
    """Test that the app can be created without errors."""
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        media_dir="/tmp/test_media",
        max_upload_bytes=10 * 1024 * 1024,
    )

    try:
        app = create_app(settings=settings)
        print("✓ App created successfully")
        return True
    except Exception as e:
        print(f"✗ App creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_app_creation())
    exit(0 if success else 1)
