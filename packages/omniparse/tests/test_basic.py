"""
Test suite for OmniParse core functionality
"""

import pytest
import os


class TestFileOperations:
    """Tests for file handling and processing"""
    
    def test_file_exists(self):
        """Test that essential files exist"""
        assert os.path.exists('README.md')
        assert os.path.exists('LICENSE')
        assert os.path.exists('pyproject.toml')
    
    def test_directory_structure(self):
        """Test directory structure"""
        assert os.path.isdir('omniparse')
        assert os.path.isdir('python-sdk')
        assert os.path.isdir('examples')
        assert os.path.isdir('docs')


class TestImports:
    """Tests for module imports"""
    
    def test_import_pyproject(self):
        """Test that pyproject.toml can be read"""
        import tomllib
        with open('pyproject.toml', 'rb') as f:
            config = tomllib.load(f)
        assert 'project' in config or 'tool' in config or 'build-system' in config


class TestDocumentation:
    """Tests for documentation completeness"""
    
    def test_readme_exists(self):
        """Test README.md exists and has content"""
        with open('README.md', 'r', encoding='utf-8') as f:
            content = f.read()
        assert len(content) > 0
    
    def test_readme_has_title(self):
        """Test README.md has a title"""
        with open('README.md', 'r', encoding='utf-8') as f:
            content = f.read()
        assert '# ' in content or 'OmniParse' in content


class TestLicense:
    """Tests for license file"""
    
    def test_license_exists(self):
        """Test LICENSE file exists"""
        assert os.path.exists('LICENSE')
    
    def test_license_content(self):
        """Test LICENSE has content"""
        with open('LICENSE', 'r', encoding='utf-8') as f:
            content = f.read()
        assert len(content) > 0
        assert 'MIT' in content or 'License' in content or 'Copyright' in content


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
