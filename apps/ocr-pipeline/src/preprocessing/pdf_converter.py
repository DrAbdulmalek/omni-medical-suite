"""
PDF-to-image converter for the Omni Medical OCR Pipeline.

Supports two backends:

1. **PyMuPDF (fitz)** — fast, pure-Python, no system dependencies.
2. **pdf2image** — wraps Poppler; produces high-quality output.

The converter automatically detects scanned vs. text-based PDFs, handles
encrypted documents, and converts pages to ``PIL.Image`` objects at a
configurable DPI.
"""

from __future__ import annotations

import logging

from PIL import Image

logger = logging.getLogger(__name__)


class PDFConverter:
    """Convert PDF files to PIL images for OCR processing.

    Parameters
    ----------
    dpi : int
        Default resolution for page rendering (default 300).
    backend : str
        Preferred backend: ``"fitz"`` (PyMuPDF) or ``"pdf2image"``.
        If the preferred backend is unavailable, the other is tried.
        Set to ``"auto"`` to let the class pick automatically.
    poppler_path : str | None
        Path to the Poppler ``bin`` directory (required for ``pdf2image``
        on Windows).
    """

    def __init__(
        self,
        dpi: int = 300,
        backend: str = "auto",
        poppler_path: str | None = None,
    ) -> None:
        self._dpi = dpi
        self._poppler_path = poppler_path
        self._backend_name: str | None = None
        self._backend = self._select_backend(backend)

    # ==================================================================
    # Backend selection
    # ==================================================================

    def _select_backend(self, preference: str) -> str:
        """Select and validate a PDF rendering backend.

        Parameters
        ----------
        preference : str
            ``"fitz"``, ``"pdf2image"``, or ``"auto"``.

        Returns
        -------
        str
            The selected backend name.

        Raises
        ------
        RuntimeError
            If no backend is available.
        """
        available: list[str] = []

        # Check PyMuPDF
        try:
            import fitz  # noqa: F401
            available.append("fitz")
        except ImportError:
            logger.debug("PyMuPDF (fitz) is not installed.")

        # Check pdf2image
        try:
            from pdf2image import convert_from_path  # noqa: F401
            available.append("pdf2image")
        except ImportError:
            logger.debug("pdf2image is not installed.")

        if not available:
            raise RuntimeError(
                "No PDF backend available. Install one of:\n"
                "  pip install PyMuPDF\n"
                "  pip install pdf2image  (also requires Poppler)"
            )

        if preference == "auto":
            selected = available[0]
        elif preference in available:
            selected = preference
        else:
            logger.warning(
                "Preferred backend '%s' not available. Falling back to '%s'.",
                preference,
                available[0],
            )
            selected = available[0]

        self._backend_name = selected
        logger.info("PDF backend selected: %s", selected)
        return selected

    # ==================================================================
    # Public API
    # ==================================================================

    def convert_page(
        self,
        pdf_path: str,
        page_num: int,
        dpi: int | None = None,
    ) -> Image.Image:
        """Convert a single PDF page to a PIL Image.

        Parameters
        ----------
        pdf_path : str
            Path to the PDF file.
        page_num : int
            Zero-based page index.
        dpi : int | None
            Rendering DPI.  If *None*, uses the default ``self._dpi``.

        Returns
        -------
        PIL.Image.Image
            Rendered page image.

        Raises
        ------
        ValueError
            If *page_num* is out of range.
        FileNotFoundError
            If *pdf_path* does not exist.
        """
        import os

        if not os.path.isfile(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        render_dpi = dpi or self._dpi

        if self._backend_name == "fitz":
            return self._convert_page_fitz(pdf_path, page_num, render_dpi)
        else:
            return self._convert_page_pdf2image(pdf_path, page_num, render_dpi)

    def convert_all_pages(
        self,
        pdf_path: str,
        dpi: int | None = None,
    ) -> list[Image.Image]:
        """Convert all pages of a PDF to PIL Images.

        Parameters
        ----------
        pdf_path : str
            Path to the PDF file.
        dpi : int | None
            Rendering DPI.  If *None*, uses the default ``self._dpi``.

        Returns
        -------
        list[PIL.Image.Image]
            List of rendered page images.
        """
        import os

        if not os.path.isfile(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        render_dpi = dpi or self._dpi

        if self._backend_name == "fitz":
            return self._convert_all_fitz(pdf_path, render_dpi)
        else:
            return self._convert_all_pdf2image(pdf_path, render_dpi)

    def get_page_count(self, pdf_path: str) -> int:
        """Return the number of pages in a PDF.

        Parameters
        ----------
        pdf_path : str
            Path to the PDF file.

        Returns
        -------
        int
            Page count.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        """
        import os

        if not os.path.isfile(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        if self._backend_name == "fitz":
            import fitz
            doc = fitz.open(pdf_path)
            count = len(doc)
            doc.close()
            return count
        else:
            import fitz  # type: ignore
            # pdf2image doesn't expose page count easily; use fitz as fallback
            try:
                doc = fitz.open(pdf_path)
                count = len(doc)
                doc.close()
                return count
            except Exception:
                # Last resort: convert all and count
                images = self.convert_all_pages(pdf_path, dpi=72)
                return len(images)

    def detect_pdf_type(self, pdf_path: str) -> str:
        """Detect whether a PDF is text-based or scanned.

        Analyses the extracted text content of the first few pages to
        determine if the PDF contains selectable text or is purely
        image-based (scanned).

        Parameters
        ----------
        pdf_path : str
            Path to the PDF file.

        Returns
        -------
        str
            ``"text"`` if the PDF contains selectable text,
            ``"scanned"`` if it appears to be scanned images,
            ``"mixed"`` if some pages have text and others do not.
        """
        import os

        if not os.path.isfile(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # Try PyMuPDF for text extraction
        try:
            import fitz
            doc = fitz.open(pdf_path)
            text_pages = 0
            empty_pages = 0
            total_pages = min(len(doc), 5)  # check first 5 pages

            for i in range(total_pages):
                page = doc[i]
                text = page.get_text("text").strip()
                if len(text) > 20:  # more than 20 chars of text
                    text_pages += 1
                else:
                    empty_pages += 1

            doc.close()

            if text_pages == total_pages:
                return "text"
            elif empty_pages == total_pages:
                return "scanned"
            else:
                return "mixed"

        except Exception as exc:
            logger.warning(
                "Could not detect PDF type for '%s': %s. Assuming 'scanned'.",
                pdf_path,
                exc,
            )
            return "scanned"

    def is_encrypted(self, pdf_path: str) -> bool:
        """Check whether a PDF is encrypted.

        Parameters
        ----------
        pdf_path : str
            Path to the PDF file.

        Returns
        -------
        bool
            ``True`` if the PDF requires a password to open.
        """
        import os

        if not os.path.isfile(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        try:
            import fitz
            doc = fitz.open(pdf_path)
            encrypted = doc.is_encrypted
            doc.close()
            return encrypted
        except Exception:
            return True  # assume encrypted if we can't open it

    # ==================================================================
    # PyMuPDF (fitz) backend
    # ==================================================================

    def _convert_page_fitz(
        self,
        pdf_path: str,
        page_num: int,
        dpi: int,
    ) -> Image.Image:
        """Render a single page using PyMuPDF."""
        import fitz

        doc = fitz.open(pdf_path)
        self._handle_encryption_fitz(doc, pdf_path)

        if page_num < 0 or page_num >= len(doc):
            doc.close()
            raise ValueError(
                f"Page {page_num} is out of range (PDF has {len(doc)} pages)."
            )

        page = doc[page_num]

        # Calculate zoom factor from DPI (fitz default is 72 DPI)
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)

        # Render page to pixmap
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        doc.close()

        # Convert to PIL Image
        img_data = pixmap.tobytes("png")
        image = Image.open(__import__("io").BytesIO(img_data))
        image.load()  # materialise the image

        logger.debug(
            "Rendered page %d (%d DPI) via fitz: %s",
            page_num,
            dpi,
            image.size,
        )
        return image

    def _convert_all_fitz(
        self,
        pdf_path: str,
        dpi: int,
    ) -> list[Image.Image]:
        """Render all pages using PyMuPDF."""
        import fitz

        doc = fitz.open(pdf_path)
        self._handle_encryption_fitz(doc, pdf_path)

        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        images: list[Image.Image] = []

        for _i, page in enumerate(doc):
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            img_data = pixmap.tobytes("png")
            image = Image.open(__import__("io").BytesIO(img_data))
            image.load()
            images.append(image)

        doc.close()
        logger.info(
            "Rendered %d pages (%d DPI) via fitz.",
            len(images),
            dpi,
        )
        return images

    @staticmethod
    def _handle_encryption_fitz(doc, pdf_path: str) -> None:
        """Handle encrypted PDFs by attempting to open with an empty password.

        Raises
        ------
        RuntimeError
            If the PDF is encrypted and cannot be opened.
        """
        if doc.is_encrypted:
            if not doc.authenticate(""):
                raise RuntimeError(
                    f"PDF '{pdf_path}' is encrypted and requires a password. "
                    "Password-protected PDFs are not supported."
                )
            logger.info("Decrypted PDF '%s' with empty password.", pdf_path)

    # ==================================================================
    # pdf2image backend
    # ==================================================================

    def _convert_page_pdf2image(
        self,
        pdf_path: str,
        page_num: int,
        dpi: int,
    ) -> Image.Image:
        """Render a single page using pdf2image."""
        from pdf2image import convert_from_path

        images = convert_from_path(
            pdf_path,
            dpi=dpi,
            first_page=page_num + 1,  # pdf2image is 1-based
            last_page=page_num + 1,
            poppler_path=self._poppler_path,
        )

        if not images:
            raise RuntimeError(
                f"pdf2image returned no images for page {page_num}."
            )

        logger.debug(
            "Rendered page %d (%d DPI) via pdf2image: %s",
            page_num,
            dpi,
            images[0].size,
        )
        return images[0]

    def _convert_all_pdf2image(
        self,
        pdf_path: str,
        dpi: int,
    ) -> list[Image.Image]:
        """Render all pages using pdf2image."""
        from pdf2image import convert_from_path

        images = convert_from_path(
            pdf_path,
            dpi=dpi,
            poppler_path=self._poppler_path,
        )

        logger.info(
            "Rendered %d pages (%d DPI) via pdf2image.",
            len(images),
            dpi,
        )
        return images
