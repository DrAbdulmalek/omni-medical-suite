"""
Test suite for OmniParse Study - Medical OCR Analysis
"""

import pytest
import os


class TestStudyFiles:
    """Tests for study-specific files"""
    
    def test_pdf_exists(self):
        """Test that analysis PDF exists"""
        assert os.path.exists('OmniParse_Analysis_Medical_OCR.pdf')
    
    def test_generate_report_script(self):
        """Test that report generation script exists"""
        assert os.path.exists('generate_omniparse_report.py')


class TestDirectoryStructure:
    """Tests for directory structure"""
    
    def test_essential_directories(self):
        """Test essential directories exist"""
        assert os.path.isdir('omniparse')
        assert os.path.isdir('python-sdk')
        assert os.path.isdir('examples')
        assert os.path.isdir('docs')


class TestDocumentation:
    """Tests for documentation"""
    
    def test_readme_has_study_info(self):
        """Test README.md contains study information"""
        with open('README.md', 'r', encoding='utf-8') as f:
            content = f.read()
        assert len(content) > 0
        # Should contain study-related keywords
        study_keywords = ['analysis', 'study', 'medical', 'ocr', 'omniparse']
        assert any(keyword.lower() in content.lower() for keyword in study_keywords)


class TestCodeOfConduct:
    """Tests for Code of Conduct"""
    
    def test_code_of_conduct_exists(self):
        """Test CODE_OF_CONDUCT.md exists"""
        assert os.path.exists('CODE_OF_CONDUCT.md')
    
    def test_code_of_conduct_content(self):
        """Test CODE_OF_CONDUCT.md has content"""
        with open('CODE_OF_CONDUCT.md', 'r', encoding='utf-8') as f:
            content = f.read()
        assert len(content) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
