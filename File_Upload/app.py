import uuid
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.staticfiles import StaticFiles
from PIL import Image

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOULDER = BASE_DIR / "upload"
UPLOAD_FOULDER.mkdir(parents=True, exist_ok=True)
app.mount("/upload", StaticFiles(directory=str(UPLOAD_FOULDER)), name="static")

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}


@app.post("/upload")
async def upload_file(files:UploadFile = File(...)):


    ext = str(files.filename).rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Error image"
        )


    content = await files.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="حجم الصورة كبير جدًا (الحد 5MB).")

    try:
        img = Image.open(BytesIO(content))
        img = img.convert("RGB") if img.mode in ("RGBA", "p") else img
        img = img.resize((200, 200))
    except:
        raise HTTPException(status_code=400, detail="ملف الصورة تالف أو غير صالح.")

    unique_filename = f"{uuid.uuid4().hex}.jpg"
    file_path = f"{UPLOAD_FOULDER}/{unique_filename}"
    img.save(file_path, format="JPEG", quality=85)

    return {
        "message": "File saved",
        "path": file_path,
        "filename": files.filename,
        "content_type": files.content_type,
    }
    

# @app.post("/upload-multiple")
# async def upload_multiple(files: list[UploadFile] = File(...)):
#     results = []
    
#     for file in files:
#         content = await file.read()
#         results.append({
#             "filename": file.filename,
#             "size": len(content)
#         })
    
#     return results
