# tests/test_calibre_manager.py
"""Unit tests for src.integrations.calibre_manager.CalibreManager."""
import pytest

from src.integrations.calibre_manager import CalibreManager, CalibreError


def test_missing_library_raises_file_not_found(tmp_path):
    missing = tmp_path / "missing-library"
    with pytest.raises(FileNotFoundError):
        CalibreManager(missing)


def test_existing_library_constructs(tmp_path):
    # Should not raise.
    manager = CalibreManager(tmp_path)
    assert manager.library_path == tmp_path.resolve()


def test_unsafe_specialty_rejected(tmp_path):
    manager = CalibreManager(tmp_path)
    with pytest.raises(ValueError):
        manager.search_by_specialty('bad"; rm -rf /')


def test_empty_specialty_rejected(tmp_path):
    manager = CalibreManager(tmp_path)
    with pytest.raises(ValueError):
        manager.search_by_specialty("   ")


def test_unsafe_title_rejected(tmp_path):
    # Create a real file so the path check passes; the title check must still fire.
    real_file = tmp_path / "book.pdf"
    real_file.write_bytes(b"%PDF-1.4 test")
    manager = CalibreManager(tmp_path)
    with pytest.raises(ValueError):
        manager.add_book(
            file_path=real_file,
            title="bad; $(rm -rf /)",
        )


def test_unsafe_authors_rejected(tmp_path):
    real_file = tmp_path / "book.pdf"
    real_file.write_bytes(b"%PDF-1.4 test")
    manager = CalibreManager(tmp_path)
    with pytest.raises(ValueError):
        manager.add_book(
            file_path=real_file,
            authors="`whoami`",
        )


def test_unsafe_tags_rejected(tmp_path):
    real_file = tmp_path / "book.pdf"
    real_file.write_bytes(b"%PDF-1.4 test")
    manager = CalibreManager(tmp_path)
    with pytest.raises(ValueError):
        manager.add_book(
            file_path=real_file,
            tags="& shell-meta",
        )


def test_is_available_returns_bool(tmp_path):
    """calibredb is not installed in CI; is_available() must return False, not raise."""
    manager = CalibreManager(tmp_path, calibredb_executable="/nonexistent/calibredb")
    assert manager.is_available() is False


def test_search_ids_empty_query_returns_empty(tmp_path):
    manager = CalibreManager(tmp_path, calibredb_executable="/nonexistent/calibredb")
    assert manager.search_ids("") == []
    assert manager.search_ids("   ") == []


def test_add_book_missing_file_raises(tmp_path):
    manager = CalibreManager(tmp_path)
    with pytest.raises(FileNotFoundError):
        manager.add_book(file_path=tmp_path / "nonexistent.pdf")
