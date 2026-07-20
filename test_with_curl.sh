#!/bin/bash
# Test document upload with curl
echo "Test 1: Upload a valid text file"
curl -X POST http://localhost:8100/api/v1/documents/upload \
  -F "file=@<(echo 'Test content' > /tmp/test.txt; cat /tmp/test.txt)" \
  -F "collection_name=test_collection"

echo -e "\n\nTest 2: Upload PDF file"
echo '%PDF-1.4\nTest PDF content' > /tmp/test.pdf
curl -X POST http://localhost:8100/api/v1/documents/upload \
  -F "file=@/tmp/test.pdf" \
  -F "collection_name=test_collection"

echo -e "\n\nTest 3: List documents"
curl http://localhost:8100/api/v1/documents

echo -e "\n\nTest 4: Upload invalid file type"
echo 'malicious' > /tmp/test.exe
curl -X POST http://localhost:8100/api/v1/documents/upload \
  -F "file=@/tmp/test.exe" \
  -F "collection_name=test_collection"
