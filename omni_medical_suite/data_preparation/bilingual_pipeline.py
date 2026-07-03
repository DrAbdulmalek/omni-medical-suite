"""
Bilingual Data Pipeline - Integration of ai-fuel-engine and bilingual-extractor
This module provides a unified pipeline for processing scanned medical books into AI-ready datasets
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import json
import subprocess
import tempfile
import shutil


class BilingualDataPipeline:
    """
    Pipeline for transforming scanned medical books into AI-ready datasets.
    
    This pipeline integrates:
    - ai-fuel-engine: Transforms scanned books to datasets
    - bilingual-extractor: Extracts bilingual (Arabic-English) terms
    
    Features:
    - Bilingual corpus building
    - Medical domain classification
    - Quality filtering
    - Multiple export formats
    """
    
    def __init__(self, output_dir: Union[str, Path] = "output", temp_dir: Union[str, Path] = None):
        """
        Initialize the pipeline.
        
        Args:
            output_dir: Directory to save processed data
            temp_dir: Temporary directory for intermediate files
        """
        self.output_dir = Path(output_dir)
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.mkdtemp())
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def process_book(self, book_path: Union[str, Path], book_name: str = None) -> Dict[str, Any]:
        """
        Process a single scanned book.
        
        Args:
            book_path: Path to the scanned book (PDF or image directory)
            book_name: Name of the book (optional)
            
        Returns:
            Dictionary with processing results
        """
        book_path = Path(book_path)
        book_name = book_name or book_path.stem
        
        # Create working directory
        work_dir = self.temp_dir / book_name
        work_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Step 1: Extract text using ai-fuel-engine
            print(f"Extracting text from {book_name}...")
            text_data = self._extract_text(book_path, work_dir)
            
            # Step 2: Extract bilingual terms using bilingual-extractor
            print(f"Extracting bilingual terms from {book_name}...")
            bilingual_terms = self._extract_bilingual_terms(text_data, work_dir)
            
            # Step 3: Create dataset
            print(f"Creating dataset for {book_name}...")
            dataset = self._create_dataset(text_data, bilingual_terms, book_name)
            
            # Step 4: Save results
            print(f"Saving results for {book_name}...")
            output_path = self._save_results(dataset, book_name)
            
            return {
                "book": book_name,
                "status": "success",
                "pages": len(text_data),
                "bilingual_terms": len(bilingual_terms),
                "output_path": str(output_path),
                "dataset": dataset
            }
            
        except Exception as e:
            return {
                "book": book_name,
                "status": "error",
                "error": str(e)
            }
        finally:
            # Clean up
            shutil.rmtree(work_dir, ignore_errors=True)
    
    def _extract_text(self, book_path: Path, work_dir: Path) -> List[Dict[str, Any]]:
        """Extract text using ai-fuel-engine"""
        # Use ai-fuel-engine CLI
        cmd = [
            "python", "-m", "ai_fuel_engine",
            "--input", str(book_path),
            "--output", str(work_dir / "text"),
            "--format", "json"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"ai-fuel-engine failed: {result.stderr}")
        
        # Load extracted text
        text_file = work_dir / "text" / "output.json"
        if not text_file.exists():
            raise FileNotFoundError(f"Text output not found: {text_file}")
        
        with open(text_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _extract_bilingual_terms(self, text_data: List[Dict[str, Any]], work_dir: Path) -> List[Dict[str, Any]]:
        """Extract bilingual terms using bilingual-extractor"""
        # Save text to temporary file
        text_file = work_dir / "text.txt"
        with open(text_file, 'w', encoding='utf-8') as f:
            for item in text_data:
                f.write(item.get('text', '') + '\n')
        
        # Run bilingual-extractor
        cmd = [
            "python", "-m", "bilingual_extractor",
            "--input", str(text_file),
            "--output", str(work_dir / "terms"),
            "--format", "json"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"bilingual-extractor failed: {result.stderr}")
        
        # Load extracted terms
        terms_file = work_dir / "terms" / "output.json"
        if not terms_file.exists():
            raise FileNotFoundError(f"Terms output not found: {terms_file}")
        
        with open(terms_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _create_dataset(self, text_data: List[Dict[str, Any]], 
                       bilingual_terms: List[Dict[str, Any]], 
                       book_name: str) -> Dict[str, Any]:
        """Create structured dataset"""
        dataset = {
            "book": book_name,
            "pages": [],
            "bilingual_terms": bilingual_terms,
            "metadata": {
                "processing_date": str(Path(".").resolve()),
                "pipeline_version": "1.0.0"
            }
        }
        
        # Add page data
        for i, page in enumerate(text_data):
            dataset["pages"].append({
                "page_number": i + 1,
                "text": page.get("text", ""),
                "language": page.get("language", "unknown"),
                "confidence": page.get("confidence", 0.0)
            })
        
        return dataset
    
    def _save_results(self, dataset: Dict[str, Any], book_name: str) -> Path:
        """Save dataset to output directory"""
        # Create output directory
        book_output_dir = self.output_dir / book_name
        book_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save JSON
        json_path = book_output_dir / f"{book_name}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)
        
        # Save CSV
        csv_path = book_output_dir / f"{book_name}.csv"
        self._save_as_csv(dataset, csv_path)
        
        # Save terms only
        terms_path = book_output_dir / f"{book_name}_terms.json"
        with open(terms_path, 'w', encoding='utf-8') as f:
            json.dump(dataset["bilingual_terms"], f, indent=2, ensure_ascii=False)
        
        return json_path
    
    def _save_as_csv(self, dataset: Dict[str, Any], csv_path: Path) -> None:
        """Save dataset as CSV"""
        import csv
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['page_number', 'text', 'language', 'confidence'])
            
            for page in dataset.get('pages', []):
                writer.writerow([
                    page.get('page_number', ''),
                    page.get('text', ''),
                    page.get('language', ''),
                    page.get('confidence', '')
                ])
    
    def process_directory(self, input_dir: Union[str, Path]) -> List[Dict[str, Any]]:
        """
        Process all books in a directory.
        
        Args:
            input_dir: Directory containing books to process
            
        Returns:
            List of results for each book
        """
        input_dir = Path(input_dir)
        results = []
        
        for book_path in input_dir.iterdir():
            if book_path.is_file() and book_path.suffix.lower() in ['.pdf', '.png', '.jpg', '.jpeg']:
                result = self.process_book(book_path)
                results.append(result)
            elif book_path.is_dir():
                # Assume directory contains images of a book
                result = self.process_book(book_path, book_path.name)
                results.append(result)
        
        return results
    
    def cleanup(self) -> None:
        """Clean up temporary files"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


# Context manager for easy usage
class BilingualPipelineContext:
    """Context manager for bilingual pipeline"""
    
    def __init__(self, output_dir: str = "output"):
        self.pipeline = BilingualDataPipeline(output_dir)
    
    def __enter__(self):
        return self.pipeline
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.pipeline.cleanup()


# Convenience function
def process_bilingual(input_path: Union[str, Path], output_dir: str = "output") -> List[Dict[str, Any]]:
    """
    Process input and return results.
    
    Args:
        input_path: Path to book or directory of books
        output_dir: Directory to save results
        
    Returns:
        List of processing results
    """
    with BilingualPipelineContext(output_dir) as pipeline:
        input_path = Path(input_path)
        
        if input_path.is_file():
            return [pipeline.process_book(input_path)]
        else:
            return pipeline.process_directory(input_path)
