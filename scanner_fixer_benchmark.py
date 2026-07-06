"""
Scanner Fixer Benchmark - Measure impact of preprocessing on OCR quality
"""

import subprocess
import os
from pathlib import Path
from typing import Dict, Any
import json
import csv
from datetime import datetime
import numpy as np

# Try to import OCR modules
try:
    import cv2
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


class OCRMetrics:
    """Calculate OCR quality metrics"""
    
    @staticmethod
    def character_error_rate(reference: str, hypothesis: str) -> float:
        """Calculate Character Error Rate (CER)"""
        ref_chars = list(reference)
        hyp_chars = list(hypothesis)
        edits = OCRMetrics.levenshtein_distance(ref_chars, hyp_chars)
        return edits / max(len(ref_chars), 1)
    
    @staticmethod
    def word_error_rate(reference: str, hypothesis: str) -> float:
        """Calculate Word Error Rate (WER)"""
        ref_words = reference.split()
        hyp_words = hypothesis.split()
        edits = OCRMetrics.levenshtein_distance(ref_words, hyp_words)
        return edits / max(len(ref_words), 1)
    
    @staticmethod
    def levenshtein_distance(s1: list, s2: list) -> int:
        """Calculate Levenshtein distance between two sequences"""
        if len(s1) < len(s2):
            return OCRMetrics.levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    @staticmethod
    def medical_term_accuracy(reference: str, hypothesis: str, medical_terms: list) -> float:
        """Calculate medical term accuracy"""
        ref_terms = [term for term in medical_terms if term.lower() in reference.lower()]
        hyp_terms = [term for term in medical_terms if term.lower() in hypothesis.lower()]
        
        if not ref_terms:
            return 1.0
        
        correct = sum(1 for term in ref_terms if term.lower() in hypothesis.lower())
        return correct / len(ref_terms)


class ScannerFixerBenchmark:
    """Benchmark scanner-fixer impact on OCR quality"""
    
    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.original_dir = self.output_dir / "original"
        self.fixed_dir = self.output_dir / "fixed"
        self.results_dir = self.output_dir / "results"
        
        # Create directories
        self.original_dir.mkdir(parents=True, exist_ok=True)
        self.fixed_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Medical terms for evaluation
        self.medical_terms = [
            "heart", "lung", "liver", "kidney", "blood", "pressure", "diabetes",
            "infection", "treatment", "diagnosis", "symptom", "disease",
            "patient", "doctor", "hospital", "medicine", "dose",
            "قلب", "رئة", "كبد", "كلى", "دم", "ضغط", "سكري",
            "عدوى", "علاج", "تشخيص", "أعراض", "مرض",
            "مريض", "طبيب", "مستشفى", "دواء", "جرعة"
        ]
    
    def run_ocr(self, image_path: Path, output_dir: Path) -> Dict[str, Any]:
        """Run OCR on an image or directory"""
        if not OCR_AVAILABLE:
            raise ImportError("OCR dependencies not available. Install with: pip install opencv-python pytesseract pillow")
        
        results = {}
        
        if image_path.is_file():
            # Process single image
            img = cv2.imread(str(image_path))
            if img is None:
                return {"error": f"Failed to read image: {image_path}"}
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Run OCR
            text = pytesseract.image_to_string(gray, lang='eng+ara')
            
            results[str(image_path.name)] = {
                "text": text,
                "image_path": str(image_path)
            }
        elif image_path.is_dir():
            # Process directory
            for img_path in image_path.glob("*.png") + image_path.glob("*.jpg") + image_path.glob("*.jpeg"):
                img = cv2.imread(str(img_path))
                if img is None:
                    continue
                
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                text = pytesseract.image_to_string(gray, lang='eng+ara')
                
                results[img_path.name] = {
                    "text": text,
                    "image_path": str(img_path)
                }
        
        return results
    
    def apply_scanner_fixer(self, image_path: Path) -> Path:
        """Apply scanner-fixer to an image"""
        try:
            # Use scanner-fixer CLI
            output_path = self.fixed_dir / image_path.name
            result = subprocess.run([
                "python", "-m", "scanner_fixer",
                "--input", str(image_path),
                "--output", str(output_path)
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Warning: scanner-fixer failed for {image_path.name}")
                print(f"Error: {result.stderr}")
                return image_path  # Return original if failed
            
            return output_path
        except Exception as e:
            print(f"Error applying scanner-fixer: {e}")
            return image_path
    
    def benchmark_single(self, image_path: Path, reference_text: str = "") -> Dict[str, Any]:
        """Benchmark a single image"""
        # Run OCR on original
        original_results = self.run_ocr(image_path, self.original_dir)
        original_text = list(original_results.values())[0]["text"] if original_results else ""
        
        # Apply scanner-fixer
        fixed_path = self.apply_scanner_fixer(image_path)
        
        # Run OCR on fixed
        fixed_results = self.run_ocr(fixed_path, self.fixed_dir)
        fixed_text = list(fixed_results.values())[0]["text"] if fixed_results else ""
        
        # Calculate metrics
        metrics = {
            "image": image_path.name,
            "original": {
                "text": original_text,
                "cer": None,
                "wer": None,
                "medical_terms": None
            },
            "fixed": {
                "text": fixed_text,
                "cer": None,
                "wer": None,
                "medical_terms": None
            }
        }
        
        if reference_text:
            metrics["original"]["cer"] = OCRMetrics.character_error_rate(reference_text, original_text)
            metrics["original"]["wer"] = OCRMetrics.word_error_rate(reference_text, original_text)
            metrics["original"]["medical_terms"] = OCRMetrics.medical_term_accuracy(
                reference_text, original_text, self.medical_terms
            )
            
            metrics["fixed"]["cer"] = OCRMetrics.character_error_rate(reference_text, fixed_text)
            metrics["fixed"]["wer"] = OCRMetrics.word_error_rate(reference_text, fixed_text)
            metrics["fixed"]["medical_terms"] = OCRMetrics.medical_term_accuracy(
                reference_text, fixed_text, self.medical_terms
            )
            
            metrics["improvement"] = {
                "cer": metrics["original"]["cer"] - metrics["fixed"]["cer"],
                "wer": metrics["original"]["wer"] - metrics["fixed"]["wer"],
                "medical_terms": metrics["fixed"]["medical_terms"] - metrics["original"]["medical_terms"]
            }
        
        return metrics
    
    def benchmark_directory(self, reference_data: Dict[str, str] = None) -> Dict[str, Any]:
        """Benchmark all images in input directory"""
        results = []
        
        for image_path in self.input_dir.glob("*.png") + self.input_dir.glob("*.jpg") + self.input_dir.glob("*.jpeg"):
            reference_text = reference_data.get(image_path.name, "") if reference_data else ""
            result = self.benchmark_single(image_path, reference_text)
            results.append(result)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_images": len(results),
            "results": results,
            "summary": self.calculate_summary(results)
        }
    
    def calculate_summary(self, results: list) -> Dict[str, Any]:
        """Calculate summary statistics"""
        if not results:
            return {}
        
        # Filter results with improvements
        with_ref = [r for r in results if "improvement" in r]
        if not with_ref:
            return {}
        
        cer_improvements = [r["improvement"]["cer"] for r in with_ref if r["improvement"]["cer"] is not None]
        wer_improvements = [r["improvement"]["wer"] for r in with_ref if r["improvement"]["wer"] is not None]
        medical_improvements = [r["improvement"]["medical_terms"] for r in with_ref if r["improvement"]["medical_terms"] is not None]
        
        return {
            "avg_cer_improvement": np.mean(cer_improvements) if cer_improvements else 0,
            "avg_wer_improvement": np.mean(wer_improvements) if wer_improvements else 0,
            "avg_medical_improvement": np.mean(medical_improvements) if medical_improvements else 0,
            "total_images": len(results),
            "images_with_reference": len(with_ref)
        }
    
    def save_results(self, results: Dict[str, Any], format: str = "json") -> None:
        """Save benchmark results"""
        if format == "json":
            output_path = self.results_dir / "benchmark_results.json"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
        elif format == "csv":
            output_path = self.results_dir / "benchmark_results.csv"
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["image", "original_cer", "fixed_cer", "improvement_cer", 
                                "original_wer", "fixed_wer", "improvement_wer"])
                for result in results["results"]:
                    if "improvement" in result:
                        writer.writerow([
                            result["image"],
                            result["original"]["cer"],
                            result["fixed"]["cer"],
                            result["improvement"]["cer"],
                            result["original"]["wer"],
                            result["fixed"]["wer"],
                            result["improvement"]["wer"]
                        ])
    
    def generate_report(self, results: Dict[str, Any]) -> str:
        """Generate a human-readable report"""
        summary = results.get("summary", {})
        
        report = """
# Scanner Fixer Benchmark Report

## Summary
- **Timestamp**: {timestamp}
- **Total Images**: {total_images}
- **Images with Reference**: {images_with_reference}

## Improvements
- **Average CER Improvement**: {avg_cer:.2%}
- **Average WER Improvement**: {avg_wer:.2%}
- **Average Medical Terms Improvement**: {avg_medical:.2%}

## Detailed Results
""".format(
            timestamp=summary.get("timestamp", "N/A"),
            total_images=summary.get("total_images", 0),
            images_with_reference=summary.get("images_with_reference", 0),
            avg_cer=summary.get("avg_cer_improvement", 0),
            avg_wer=summary.get("avg_wer_improvement", 0),
            avg_medical=summary.get("avg_medical_improvement", 0)
        )
        
        for result in results.get("results", []):
            report += f"
### {result.get('image', 'Unknown')}
"
            if "improvement" in result:
                report += f"- CER: {result['original']['cer']:.2%} -> {result['fixed']['cer']:.2%} ({result['improvement']['cer']:+.2%})
"
                report += f"- WER: {result['original']['wer']:.2%} -> {result['fixed']['wer']:.2%} ({result['improvement']['wer']:+.2%})
"
                report += f"- Medical Terms: {result['original']['medical_terms']:.2%} -> {result['fixed']['medical_terms']:.2%} ({result['improvement']['medical_terms']:+.2%})
"
        
        return report


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Scanner Fixer Benchmark")
    parser.add_argument("--input", type=str, required=True, help="Input directory with images")
    parser.add_argument("--output", type=str, required=True, help="Output directory for results")
    parser.add_argument("--reference", type=str, help="JSON file with reference texts")
    parser.add_argument("--format", type=str, default="json", choices=["json", "csv"], help="Output format")
    parser.add_argument("--report", action="store_true", help="Generate human-readable report")
    
    args = parser.parse_args()
    
    # Load reference data if provided
    reference_data = {}
    if args.reference:
        with open(args.reference, "r", encoding="utf-8") as f:
            reference_data = json.load(f)
    
    # Run benchmark
    benchmark = ScannerFixerBenchmark(args.input, args.output)
    results = benchmark.benchmark_directory(reference_data)
    
    # Save results
    benchmark.save_results(results, args.format)
    
    # Generate report if requested
    if args.report:
        report = benchmark.generate_report(results)
        report_path = Path(args.output) / "benchmark_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Report saved to: {report_path}")
    
    print(f"Benchmark completed. Results saved to: {args.output}")
