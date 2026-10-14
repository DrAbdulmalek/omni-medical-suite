# packages/omni_preprocess/backends/stirling_client.py
import httpx
import time
from pathlib import Path
from ..contract.preprocessing_result import PreprocessingResult, PreprocessOperation

class StirlingPDFClient:
    """Client لـStirling PDF REST API."""

    def __init__(self, base_url: str = "http://localhost:8080", api_key: str = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.Client(timeout=300.0)
        self.headers = {"X-API-KEY": api_key} if api_key else {}

    def is_available(self) -> bool:
        try:
            r = self.client.get(f"{self.base_url}/api/v1/info/status", headers=self.headers)
            return r.status_code == 200
        except httpx.RequestError:
            return False

    def ocr_preprocess(
        self,
        input_path: str,
        output_path: str,
        languages: list = None,
        deskew: bool = True,
        clean: bool = True,
        clean_final: bool = True,
        ocr_type: str = "skip-text",
        sidecar: bool = False,
    ) -> PreprocessingResult:
        """يشغّل OCR مع preprocessing (deskew + clean)."""
        start = time.time()
        languages = languages or ["ara", "eng"]

        files = {"fileInput": open(input_path, "rb")}
        data = {
            "languages": languages,
            "ocrType": ocr_type,
            "ocrRenderType": "hocr",
            "deskew": str(deskew).lower(),
            "clean": str(clean).lower(),
            "cleanFinal": str(clean_final).lower(),
            "sidecar": str(sidecar).lower(),
        }

        try:
            r = self.client.post(
                f"{self.base_url}/api/v1/misc/ocr-pdf",
                files=files, data=data, headers=self.headers,
            )
            r.raise_for_status()
            Path(output_path).write_bytes(r.content)
            return PreprocessingResult(
                output_path=output_path,
                operation=PreprocessOperation.DESKEW,
                success=True,
                processing_time_ms=(time.time() - start) * 1000,
                source_path=input_path,
            )
        except Exception as e:
            return PreprocessingResult(
                output_path="",
                operation=PreprocessOperation.DESKEW,
                success=False,
                processing_time_ms=(time.time() - start) * 1000,
                source_path=input_path,
                errors=[str(e)],
            )
        finally:
            files["fileInput"].close()

    def split_pdf(self, input_path: str, output_dir: str,
                  pages: str = "1-5") -> PreprocessingResult:
        """يقسّم PDF."""
        start = time.time()
        files = {"fileInput": open(input_path, "rb")}
        data = {"pageNumbers": pages}

        try:
            r = self.client.post(
                f"{self.base_url}/api/v1/general/split-pages",
                files=files, data=data, headers=self.headers,
            )
            r.raise_for_status()
            out = Path(output_dir) / "split.zip"
            out.write_bytes(r.content)
            return PreprocessingResult(
                output_path=str(out),
                operation=PreprocessOperation.SPLIT,
                success=True,
                processing_time_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return PreprocessingResult(
                output_path="", operation=PreprocessOperation.SPLIT,
                success=False,
                processing_time_ms=(time.time() - start) * 1000,
                errors=[str(e)],
            )
        finally:
            files["fileInput"].close()

    def merge_pdfs(self, input_paths: list, output_path: str) -> PreprocessingResult:
        """يدمج ملفات PDF."""
        start = time.time()
        files = [("fileInput", open(p, "rb")) for p in input_paths]

        try:
            r = self.client.post(
                f"{self.base_url}/api/v1/general/merge-pdfs",
                files=files, headers=self.headers,
            )
            r.raise_for_status()
            Path(output_path).write_bytes(r.content)
            return PreprocessingResult(
                output_path=output_path,
                operation=PreprocessOperation.MERGE,
                success=True,
                processing_time_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return PreprocessingResult(
                output_path="", operation=PreprocessOperation.MERGE,
                success=False,
                processing_time_ms=(time.time() - start) * 1000,
                errors=[str(e)],
            )
        finally:
            for _, f in files:
                f.close()

    def close(self):
        self.client.close()
