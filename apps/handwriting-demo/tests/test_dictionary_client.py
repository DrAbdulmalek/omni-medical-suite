from app.dictionary_client import DictionaryManager


class TestDictionaryManager:
    def test_without_token(self):
        manager = DictionaryManager(token=None)
        assert not manager.enabled
        status = manager.get_status()
        assert not status['enabled']

    def test_invalid_token_format(self):
        manager = DictionaryManager(token="invalid_token")
        assert not manager.enabled

    def test_status_without_token(self):
        manager = DictionaryManager()
        status = manager.get_status()
        assert 'setup_instructions' in status
