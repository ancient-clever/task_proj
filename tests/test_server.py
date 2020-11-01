import io
import re
from pathlib import Path
from typing import Any

import pytest
from aiohttp import MultipartWriter
from aiohttp.test_utils import TestClient

from app import init_app
from settings import TEST_FILES


@pytest.fixture
async def client(aiohttp_client: Any, db_path: Path, upload_path: Path) -> TestClient:
    app = await init_app(db_path, upload_path)
    return await aiohttp_client(app)


async def test_list_empty(client: TestClient) -> None:
    """Test index page with empty files list"""
    response = await client.get("/")
    assert response.status == 200
    text = await response.text()
    assert "Files" in text
    assert "Upload files" in text


async def test_upload_file(client: TestClient) -> None:
    """Test single file upload"""
    test_file = TEST_FILES[0]
    file = Path(test_file)
    data = io.FileIO(test_file)
    response = await client.post("/upload", data={'file': data})
    assert response.status == 200
    text = await response.text()
    assert file.name in text


async def test_upload_multiple(client: TestClient) -> None:
    """Test multiple files upload"""
    files = []
    with MultipartWriter('mixed') as mpwriter:
        for test_file in TEST_FILES:
            file = Path(test_file)
            files.append(file.name)
            part = mpwriter.append(open(test_file, 'rb'))
            part.set_content_disposition('attachment', filename=file.name)
        response = await client.post("/upload", data=mpwriter)

        assert response.status == 200
        text = await response.text()
        for file in files:
            assert file in text


async def test_download_file(client: TestClient) -> None:
    """Test file download"""
    # first upload a file
    test_file = TEST_FILES[1]
    file = Path(test_file)
    data = io.FileIO(test_file)
    response = await client.post("/upload", data={'file': data})
    assert response.status == 200
    text = await response.text()
    assert file.name in text

    # then test downloading it
    url = re.findall(r'(?<=<a href=")[^"]*', text)[0]
    resp = await client.get(url)
    assert resp.status == 200
    remote_file = await resp.read()
    with open(test_file, 'rb') as source:
        real_file_length = len(source.read())
        assert real_file_length == len(remote_file)


async def test_file_not_found(client: TestClient) -> None:
    """Test wrong download url"""
    response = await client.get("/download/test_unique_name")
    assert response.status == 404
    text = await response.text()
    assert text == "File Not Found"
