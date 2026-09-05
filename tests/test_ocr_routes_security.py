# tests/test_ocr_routes_security.py
import pytest
pytest.importorskip('fastapi')
pytest.importorskip('PIL')
from src.api.ocr_routes import ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE, MAX_IMAGE_PIXELS, _validate_image

def test_upload_policy_limits_are_positive_and_bounded():
    assert MAX_UPLOAD_SIZE == 10 * 1024 * 1024
    assert 1 <= MAX_IMAGE_PIXELS <= 50_000_000

def test_extension_policy_is_allowlist():
    assert '.png' in ALLOWED_EXTENSIONS
    assert '.exe' not in ALLOWED_EXTENSIONS

def test_invalid_content_rejected_even_with_image_extension(tmp_path):
    p=tmp_path/'fake.jpg'; p.write_bytes(b'not an image')
    with pytest.raises(Exception) as exc: _validate_image(str(p))
    assert getattr(exc.value,'status_code',None) == 400

def test_oversized_dimensions_rejected(tmp_path, monkeypatch):
    from PIL import Image
    p=tmp_path/'big.png'; Image.new('RGB',(2,2)).save(p)
    monkeypatch.setattr('src.api.ocr_routes.MAX_IMAGE_PIXELS',1)
    with pytest.raises(Exception) as exc: _validate_image(str(p))
    assert getattr(exc.value,'status_code',None) == 400
