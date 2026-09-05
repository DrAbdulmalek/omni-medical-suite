# tests/test_calibre_manager.py
import pytest
from src.integrations.calibre_manager import CalibreManager

def test_missing_library_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError): CalibreManager(tmp_path/'missing')
def test_existing_library_constructs(tmp_path):
    assert CalibreManager(tmp_path).library_path == tmp_path.resolve()
def test_unsafe_specialty_rejected(tmp_path):
    with pytest.raises(ValueError): CalibreManager(tmp_path).search_by_specialty('bad"; rm -rf /')
def test_empty_specialty_rejected(tmp_path):
    with pytest.raises(ValueError): CalibreManager(tmp_path).search_by_specialty('   ')
def test_public_search_ids_removed(tmp_path):
    assert not hasattr(CalibreManager(tmp_path),'search_ids')
def test_internal_empty_query_is_safe(tmp_path):
    assert CalibreManager(tmp_path,calibredb_executable='/nonexistent/calibredb')._search_ids('') == []
@pytest.mark.parametrize('field,value',[('title','bad; $(rm -rf /)'),('authors','`whoami`'),('tags','& shell-meta')])
def test_unsafe_metadata_rejected(tmp_path,field,value):
    p=tmp_path/'book.pdf'; p.write_bytes(b'%PDF-1.4')
    with pytest.raises(ValueError): CalibreManager(tmp_path).add_book(p,**{field:value})
def test_add_book_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError): CalibreManager(tmp_path).add_book(tmp_path/'none.pdf')
