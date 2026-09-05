"""Security regression tests for the OCR upload route."""
import io
import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers, UploadFile
from PIL import Image
from src.api.ocr_routes import (
    MAX_UPLOAD_SIZE, MAX_IMAGE_PIXELS, UPLOAD_CHUNK_SIZE,
    _validate_image, process_image,
)

def upload(name, data):
    return UploadFile(file=io.BytesIO(data), filename=name, headers=Headers({"content-type":"application/octet-stream"}))

@pytest.mark.asyncio
async def test_oversized_upload_rejected_before_processing(monkeypatch):
    called={"pipeline":False}
    monkeypatch.setattr("src.api.ocr_routes.MedicalImageProcessor.full_pipeline", lambda _: called.__setitem__("pipeline",True))
    with pytest.raises(HTTPException) as exc:
        await process_image(upload("x.png", b"x"*(MAX_UPLOAD_SIZE+1)))
    assert exc.value.status_code==413
    assert called["pipeline"] is False

@pytest.mark.asyncio
async def test_fake_image_with_allowed_extension_rejected():
    with pytest.raises(HTTPException) as exc:
        await process_image(upload("fake.png", b"not an image"))
    assert exc.value.status_code==400

def test_validate_rejects_excessive_pixels(tmp_path):
    width=10000; height=(MAX_IMAGE_PIXELS//width)+1
    image=Image.new("1",(width,height))
    path=tmp_path/"large.png"; image.save(path)
    with pytest.raises(HTTPException) as exc: _validate_image(str(path))
    assert exc.value.status_code==400

@pytest.mark.asyncio
async def test_internal_error_is_not_leaked(monkeypatch):
    buf=io.BytesIO(); Image.new("RGB",(4,4)).save(buf,format="PNG")
    monkeypatch.setattr("src.api.ocr_routes.MedicalImageProcessor.full_pipeline", lambda _: (_ for _ in ()).throw(RuntimeError("/secret/path backend exploded")))
    with pytest.raises(HTTPException) as exc: await process_image(upload("ok.png",buf.getvalue()))
    assert exc.value.status_code==500
    assert exc.value.detail=="OCR processing failed"
    assert "secret" not in exc.value.detail

def test_chunk_size_is_bounded():
    assert 0 < UPLOAD_CHUNK_SIZE <= MAX_UPLOAD_SIZE
