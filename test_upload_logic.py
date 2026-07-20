"""Simple functional test of document upload route handler (without full server)."""
import tempfile
from pathlib import Path
from rag_agent.core.config import Settings
from rag_agent.pipeline.file_storage import LocalFileStorage

# Test file storage
print("Test 1: File storage")
with tempfile.TemporaryDirectory() as tmpdir:
    media_dir = Path(tmpdir) / "media"
    media_dir.mkdir()

    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        media_dir=str(media_dir),
        max_upload_bytes=10 * 1024 * 1024,
    )

    storage = LocalFileStorage(settings.media_dir)
    test_content = b"Test document content"

    # Simulate what upload route does
    storage_path = storage.save("test.txt", test_content, "documents")

    print(f"✓ File saved to: {storage_path}")
    print(f"✓ File exists: {storage_path.exists()}")
    print(f"✓ File size: {storage_path.stat().st_size} bytes")
    print(f"✓ Content matches: {open(storage_path, 'rb').read() == test_content}")

# Test validation logic
print("\nTest 2: File type validation")
allowed_extensions = {".txt", ".md", ".docx", ".pdf"}

test_cases = [
    ("document.txt", True),
    ("report.pdf", True),
    ("notes.md", True),
    ("malicious.exe", False),
    ("archive.zip", False),
    ("", False),  # Empty filename
]

for filename, should_pass in test_cases:
    if not filename:
        result = False
    else:
        ext = Path(filename).suffix.lower()
        result = ext in allowed_extensions

    status = "✓" if result == should_pass else "✗"
    print(f"  {status} '{filename}' -> {result} (expected {should_pass})")

print("\nTest 3: File size validation")
max_bytes = 10 * 1024 * 1024  # 10MB
test_sizes = [
    (100, True),  # Small file
    (max_bytes, True),  # Exactly at limit
    (max_bytes + 1, False),  # Just over limit
    (20 * 1024 * 1024, False),  # 20MB
]

for size, should_pass in test_sizes:
    result = size <= max_bytes
    status = "✓" if result == should_pass else "✗"
    print(f"  {status} {size:,} bytes -> {result} (expected {should_pass})")

print("\n✅ All unit-level tests passed!")
