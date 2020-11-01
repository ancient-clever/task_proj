import uuid
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, AsyncIterator, Dict

import aiohttp_jinja2
import aiosqlite
import jinja2
from aiohttp import web

from logger import logger
from settings import UPLOAD_DIR, CHUNK_SIZE


router = web.RouteTableDef()


@router.get("/")
@aiohttp_jinja2.template("index.html")
async def index(request: web.Request) -> Dict[str, Any]:
    """Index page with files list"""
    files = []
    db = request.config_dict["db"]

    # get all files and their identifiers for urls
    async with db.execute("SELECT id, filename, identifier FROM files") as cursor:
        async for row in cursor:
            files.append(
                {
                    "filename": row["filename"],
                    "identifier": row["identifier"]
                }
            )
    return {"files": files}
    
    
@router.get("/upload")
@aiohttp_jinja2.template("upload.html")
async def new_file(request: web.Request) -> Dict[str, Any]:
    """Page with html form for uploading"""
    return {}


@router.post("/upload")
@aiohttp_jinja2.template("error.html")
async def new_file_upload(request: web.Request) -> Dict[str, Any]:
    """Upload files and create unique links"""
    db = request.config_dict["db"]
    upload_dir = request.config_dict["UPLOAD_DIR"]
    errors = []
    reader = await request.multipart()
    
    while True:
        # get body part of reader
        file = await reader.next()

        # break the loop when there are no more parts
        if not file:
            break

        # simple validation
        filename = file.filename
        if not filename:
            break

        # generate file unique name
        identifier = str(uuid.uuid4())

        # destination path for a file
        dst_path = upload_dir / filename
        if dst_path.is_file():
            errors.append(
                {
                    "filename": filename,
                    "message": "A file with the same name already exists."
                }
            )
            continue

        size = 0
        logger("INFO", "file {} start uploading".format(filename))
        # write file in chunks
        with open(dst_path, 'wb') as f:
            while True:
                chunk = await file.read_chunk()
                if not chunk:
                    logger("INFO", "file {} uploaded".format(filename))
                    break
                size += len(chunk)
                f.write(chunk)

            # create a new record in db
            await db.execute(
                "INSERT INTO files (filename, identifier, local_path) VALUES(?, ?, ?)",
                [filename, identifier, str(dst_path)],
            )
            await db.commit()
            logger("INFO", "file {} db record created".format(filename))

    if errors:
        # return errors page
        return {"errors": errors}

    # redirect to index page
    raise web.HTTPSeeOther("/")


@router.get('/download/{identifier}', name='download')
async def file_download(request: web.Request) -> web.StreamResponse:
    """Create a stream response to send a file"""
    identifier = request.match_info["identifier"]
    db = request.config_dict["db"]

    # get file local path
    async with db.execute("SELECT filename, local_path FROM files WHERE identifier = ?", [identifier]) as cursor:
        row = await cursor.fetchone()
        if not row or not row["local_path"]:
            file_path = Path('no-such-file')
        else:
            filename = row["filename"]
            file_path = Path(row["local_path"])

    # check if the file exists
    if not file_path.exists():
        return web.Response(text="File Not Found", status=404)

    # create stream response
    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Disposition': 'attachment; filename={}'.format(filename)
        }
    )
    stats = file_path.stat()
    response.content_length = stats.st_size
    await response.prepare(request)

    # send file in chunks
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                return response
            await response.write(chunk)


async def init_db(app: web.Application) -> AsyncIterator[None]:
    """Connect to sqlite db"""
    sqlite_db = app["DB_PATH"]
    db = await aiosqlite.connect(sqlite_db)
    db.row_factory = aiosqlite.Row
    app["db"] = db
    yield
    await db.close()


async def init_app(db_path: Path, upload_dir: Path) -> web.Application:
    """Create app"""
    app = web.Application()
    app["DB_PATH"] = db_path
    app["UPLOAD_DIR"] = upload_dir
    app.add_routes(router)
    app.cleanup_ctx.append(init_db)
    aiohttp_jinja2.setup(
        app, loader=jinja2.FileSystemLoader(str(Path(__file__).parent / "templates"))
    )

    return app


def try_make_db(sqlite_db: Path) -> None:
    """Create sqlite db"""
    if sqlite_db.exists():
        return

    with sqlite3.connect(sqlite_db) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE files (
            id INTEGER PRIMARY KEY,
            filename TEXT,
            identifier TEXT,
            local_path TEXT)
            """
        )
        conn.commit()
    logger("INFO", "new db created")


def get_db_path() -> Path:
    """Return the pathname of the sqlite db"""
    db_path = Path.cwd() / "db.sqlite3"
    return db_path


def get_upload_path() -> Path:
    """Return the pathname of the uploading directory"""
    dt = datetime.now()
    upload_dir = Path.cwd() / UPLOAD_DIR / dt.strftime('%y%m%d')
    if not upload_dir.exists():
        upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


if __name__ == "__main__":
    db_path = get_db_path()
    upload_path = get_upload_path()
    try_make_db(db_path)
    logger("INFO", "app will start in a few seconds")
    logging.basicConfig(level=logging.INFO)
    web.run_app(init_app(db_path, upload_path))
