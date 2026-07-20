"""Manual test of document upload service without pytest."""
import asyncio
import tempfile
from pathlib import Path
from rag_agent.app import create_app
from rag_agent.core.config import Settings

async def main():
    """Test document upload endpoint."""
    with tempfile.TemporaryDirectory() as tmpdir:
        media_dir = Path(tmpdir) / "media"
        media_dir.mkdir()

        settings = Settings(
            database_url="sqlite+aiosqlite:///:memory:",
            media_dir=str(media_dir),
            max_upload_bytes=10 * 1024 * 1024,
        )

        app = create_app(settings=settings, test_mode=True)

        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            # Test 1: Upload a valid text file
            print("Test 1: Uploading valid .txt file...")
            test_content = b"Test document content"
            files = {"file": ("test.txt", test_content, "text/plain")}
            data = {"collection_name": "test_collection"}

            response = await client.post("/api/v1/documents/upload", files=files, data=data)
            print(f"  Status: {response.status_code}")
            print(f"  Response: {response.json()}")

            if response.status_code == 200:
                print("  ✓ Upload successful!")
            else:
                print(f"  ✗ Upload failed with status {response.status_code}")

            # Test 2: Upload invalid file type
            print("\nTest 2: Uploading invalid file type...")
            files = {"file": ("test.exe", b"malicious", "application/octet-stream")}
            response = await client.post("/api/v1/documents/upload", files=files)
            print(f"  Status: {response.status_code}")
            print(f"  Response: {response.json()}")

            if response.status_code == 400:
                print("  ✓ Correctly rejected invalid file type!")
            else:
                print(f"  ✗ Expected 400, got {response.status_code}")

            # Test 3: Upload empty filename
            print("\nTest 3: Uploading with empty filename...")
            files = {"file": ("", b"content", "text/plain")}
            response = await client.post("/api/v1/documents/upload", files=files)
            print(f"  Status: {response.status_code}")
            print(f"  Response: {response.json()}")

            if response.status_code == 400:
                print("  ✓ Correctly rejected empty filename!")
            else:
                print(f"  ✗ Expected 400, got {response.status_code}")

if __name__ == "__main__":
    asyncio.run(main())
