#!/usr/bin/env python3
"""
snippet_review_ui.py — Interactive Snippet Review & Correction Interface
========================================================================
Tkinter-based GUI for reviewing OCR snippets, correcting text,
and training the system from user feedback.

Supports Arabic RTL text with proper rendering.

Author: Dr. Abdulmalek
Version: 1.0.0
Date: 2026-06-04
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import json
import os
from pathlib import Path
from typing import Optional, Callable
import threading

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    ARABIC_UI = True
except ImportError:
    ARABIC_UI = False

# Import our trainer
from ocr_snippet_trainer import OCRSnippetTrainer, TextSnippet


class ArabicTextHandler:
    """Handle Arabic text display with proper RTL support."""

    @staticmethod
    def reshape(text: str) -> str:
        """Reshape Arabic text for display."""
        if ARABIC_UI and text:
            try:
                reshaped = arabic_reshaper.reshape(text)
                return get_display(reshaped)
            except:
                pass
        return text

    @staticmethod
    def unshape(text: str) -> str:
        """Convert displayed text back to logical order."""
        if ARABIC_UI and text:
            try:
                # Reverse bidi
                return get_display(text)
            except:
                pass
        return text


class SnippetReviewUI:
    """
    Interactive GUI for reviewing OCR snippets.

    Features:
    - Display image snippet with OCR text
    - Editable text field for corrections
    - Navigation between snippets
    - Auto-save corrections
    - Statistics dashboard
    - Arabic RTL support
    """

    def __init__(self, trainer: Optional[OCRSnippetTrainer] = None):
        self.trainer = trainer or OCRSnippetTrainer()
        self.current_snippets = []
        self.current_index = 0
        self.snippet_images = {}  # Cache for PhotoImage objects

        self.root = tk.Tk()
        self.root.title("OCR Snippet Review & Training — الطبيب المعالج")
        self.root.geometry("1200x800")
        self.root.configure(bg='#f0f0f0')

        # Arabic font
        self.arabic_font = ('Arial', 14)
        self.arabic_font_large = ('Arial', 16, 'bold')

        self._build_ui()
        self._load_stats()

    def _build_ui(self):
        """Build the user interface."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # === TOP BAR ===
        top_bar = ttk.Frame(main_frame)
        top_bar.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Button(top_bar, text="📁 فتح صورة", command=self._open_image).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_bar, text="📊 إحصائيات", command=self._show_stats).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_bar, text="💾 تصدير البيانات", command=self._export_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_bar, text="🔧 تطبيق التصحيحات", command=self._apply_corrections).pack(side=tk.LEFT, padx=5)

        self.progress_label = ttk.Label(top_bar, text="جاهز")
        self.progress_label.pack(side=tk.RIGHT, padx=10)

        # === LEFT PANEL: Image Display ===
        left_panel = ttk.LabelFrame(main_frame, text="القصاصة (Snippet)", padding="10")
        left_panel.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))

        self.image_label = ttk.Label(left_panel, text="[لا توجد صورة]")
        self.image_label.pack(expand=True, fill=tk.BOTH)

        # Image info
        self.image_info = ttk.Label(left_panel, text="")
        self.image_info.pack(pady=(10, 0))

        # === RIGHT PANEL: Text Review ===
        right_panel = ttk.Frame(main_frame)
        right_panel.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)

        # OCR Text (read-only)
        ocr_frame = ttk.LabelFrame(right_panel, text="نص OCR (غير قابل للتعديل)", padding="5")
        ocr_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        ocr_frame.columnconfigure(0, weight=1)

        self.ocr_text = scrolledtext.ScrolledText(
            ocr_frame, height=4, font=self.arabic_font,
            wrap=tk.WORD, state=tk.DISABLED,
            bg='#fff8f0', fg='#333'
        )
        self.ocr_text.grid(row=0, column=0, sticky=(tk.W, tk.E))

        # Confidence display
        self.confidence_label = ttk.Label(ocr_frame, text="الثقة: —")
        self.confidence_label.grid(row=1, column=0, sticky=tk.W, pady=(5, 0))

        # Corrected Text (editable)
        corr_frame = ttk.LabelFrame(right_panel, text="النص المصحح (قابل للتعديل)", padding="5")
        corr_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        corr_frame.columnconfigure(0, weight=1)
        corr_frame.rowconfigure(0, weight=1)

        self.corrected_text = scrolledtext.ScrolledText(
            corr_frame, height=6, font=self.arabic_font_large,
            wrap=tk.WORD, bg='#f0fff0', fg='#000'
        )
        self.corrected_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Suggestions
        self.suggestions_label = ttk.Label(corr_frame, text="💡 اقتراحات: —")
        self.suggestions_label.grid(row=1, column=0, sticky=tk.W, pady=(5, 0))

        # === BOTTOM: Navigation & Actions ===
        bottom_frame = ttk.Frame(right_panel)
        bottom_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))

        # Navigation
        nav_frame = ttk.Frame(bottom_frame)
        nav_frame.pack(side=tk.LEFT)

        ttk.Button(nav_frame, text="◀ السابق", command=self._prev_snippet).pack(side=tk.LEFT, padx=2)
        self.position_label = ttk.Label(nav_frame, text="0 / 0")
        self.position_label.pack(side=tk.LEFT, padx=10)
        ttk.Button(nav_frame, text="التالي ▶", command=self._next_snippet).pack(side=tk.LEFT, padx=2)

        # Action buttons
        action_frame = ttk.Frame(bottom_frame)
        action_frame.pack(side=tk.RIGHT)

        ttk.Button(action_frame, text="✓ صحيح", command=self._mark_correct).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="💾 حفظ التصحيح", command=self._save_correction).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="⏭ تخطي", command=self._skip_snippet).pack(side=tk.LEFT, padx=2)

        # Keyboard shortcuts
        self.root.bind('<Left>', lambda e: self._prev_snippet())
        self.root.bind('<Right>', lambda e: self._next_snippet())
        self.root.bind('<Return>', lambda e: self._save_correction())
        self.root.bind('<space>', lambda e: self._mark_correct())
        self.root.bind('<Escape>', lambda e: self._skip_snippet())

    def _open_image(self):
        """Open and process an image file."""
        file_path = filedialog.askopenfilename(
            title="اختر صورة مستند",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff"),
                ("All files", "*.*")
            ]
        )

        if not file_path:
            return

        self.progress_label.config(text="جاري المعالجة...")
        self.root.update()

        try:
            # Process image in background
            def process():
                self.current_snippets = self.trainer.process_image(file_path)
                self.current_index = 0
                self.root.after(0, self._on_image_loaded)

            threading.Thread(target=process, daemon=True).start()

        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في معالجة الصورة:
{str(e)}")
            self.progress_label.config(text="جاهز")

    def _on_image_loaded(self):
        """Called when image processing completes."""
        count = len(self.current_snippets)
        self.progress_label.config(text=f"تم تحميل {count} قصاصة")

        if count > 0:
            self._display_snippet(0)
        else:
            messagebox.showinfo("تنبيه", "لم يتم العثور على نصوص في الصورة")

    def _display_snippet(self, index: int):
        """Display a specific snippet."""
        if not self.current_snippets or index < 0 or index >= len(self.current_snippets):
            return

        self.current_index = index
        snippet = self.current_snippets[index]

        # Update image
        self._load_snippet_image(snippet)

        # Update OCR text
        self.ocr_text.config(state=tk.NORMAL)
        self.ocr_text.delete('1.0', tk.END)
        display_text = ArabicTextHandler.reshape(snippet.ocr_text)
        self.ocr_text.insert('1.0', display_text)
        self.ocr_text.config(state=tk.DISABLED)

        # Update corrected text
        self.corrected_text.delete('1.0', tk.END)
        corrected_display = ArabicTextHandler.reshape(snippet.corrected_text)
        self.corrected_text.insert('1.0', corrected_display)

        # Update labels
        self.confidence_label.config(text=f"الثقة: {snippet.confidence:.2%} | المحرك: {snippet.engine}")
        self.position_label.config(text=f"{index + 1} / {len(self.current_snippets)}")

        # Update image info
        bbox = snippet.bbox
        self.image_info.config(text=f"موقع: ({bbox[0]}, {bbox[1]}) | حجم: {bbox[2]}×{bbox[3]}")

        # Get suggestions
        self._update_suggestions(snippet)

    def _load_snippet_image(self, snippet: TextSnippet):
        """Load and display snippet image."""
        if not PIL_AVAILABLE:
            self.image_label.config(text="[PIL not available]")
            return

        try:
            crop_path = snippet.image_path
            # Try to find the actual crop file
            if hasattr(snippet, 'bbox') and snippet.bbox != (0, 0, 0, 0):
                # Look for snippet crop
                base = Path(snippet.image_path).stem
                snippet_dir = Path(snippet.image_path).parent / "snippets"
                # Find matching file
                for f in snippet_dir.glob(f"{base}_snippet_*.png"):
                    crop_path = str(f)
                    break

            img = Image.open(crop_path)

            # Resize to fit display (max 400x400)
            max_size = (400, 400)
            img.thumbnail(max_size, Image.LANCZOS)

            photo = ImageTk.PhotoImage(img)
            self.snippet_images[snippet.id] = photo  # Keep reference

            self.image_label.config(image=photo, text="")

        except Exception as e:
            self.image_label.config(text=f"[لا يمكن عرض الصورة]
{str(e)}")

    def _update_suggestions(self, snippet: TextSnippet):
        """Update suggestion label based on learned patterns."""
        suggestions = self.trainer.learner.get_suggestions(snippet.ocr_text, max_suggestions=3)

        if suggestions:
            sugg_text = "💡 اقتراحات: " + " | ".join(
                f"'{s['word']}'→'{s['suggestion']}' ({s['confidence']:.0%})"
                for s in suggestions
            )
        else:
            sugg_text = "💡 لا توجد اقتراحات تلقائية"

        self.suggestions_label.config(text=sugg_text)

    def _get_corrected_text(self) -> str:
        """Get corrected text from UI, converting back from display order."""
        text = self.corrected_text.get('1.0', tk.END).strip()
        return ArabicTextHandler.unshape(text)

    def _save_correction(self):
        """Save user correction and learn from it."""
        if not self.current_snippets:
            return

        snippet = self.current_snippets[self.current_index]
        corrected = self._get_corrected_text()

        if corrected == snippet.ocr_text:
            # Same as OCR, mark as correct
            self._mark_correct()
            return

        try:
            result = self.trainer.submit_correction(snippet.id, corrected)

            if result.get("success"):
                patterns = result.get("patterns_learned", 0)
                self.progress_label.config(
                    text=f"✓ تم الحفظ | أنماط متعلمة: {patterns}"
                )

                # Move to next
                self._next_snippet()
            else:
                messagebox.showerror("خطأ", result.get("error", "Unknown error"))

        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في حفظ التصحيح:
{str(e)}")

    def _mark_correct(self):
        """Mark current snippet as correct (no changes needed)."""
        if not self.current_snippets:
            return

        snippet = self.current_snippets[self.current_index]

        try:
            self.trainer.submit_correction(snippet.id, snippet.ocr_text)
            self.progress_label.config(text="✓ تم التأكيد: النص صحيح")
            self._next_snippet()
        except Exception as e:
            messagebox.showerror("خطأ", str(e))

    def _skip_snippet(self):
        """Skip current snippet without saving."""
        self._next_snippet()

    def _prev_snippet(self):
        """Go to previous snippet."""
        if self.current_index > 0:
            self._display_snippet(self.current_index - 1)

    def _next_snippet(self):
        """Go to next snippet."""
        if self.current_index < len(self.current_snippets) - 1:
            self._display_snippet(self.current_index + 1)
        else:
            messagebox.showinfo("انتهى", "تم مراجعة جميع القصاصات!")

    def _show_stats(self):
        """Show statistics window."""
        stats = self.trainer.get_stats()

        stats_window = tk.Toplevel(self.root)
        stats_window.title("إحصائيات التعلم")
        stats_window.geometry("400x300")

        text = f"""
📊 إحصائيات نظام التعلم
{'='*40}

إجمالي القصاصات: {stats['total_snippets']}
تمت مراجعتها: {stats['reviewed_snippets']}
صحيحة (بدون تعديل): {stats['correct_snippets']}

إجمالي الأنماط المتعلمة: {stats['total_patterns']}
أنماط مفعلة تلقائياً: {stats['promoted_patterns']}

متوسط الثقة بعد المراجعة: {stats['avg_confidence_after_review']:.1%}

{'='*40}
        """

        label = ttk.Label(stats_window, text=text, justify=tk.RIGHT, font=('Arial', 12))
        label.pack(padx=20, pady=20)

    def _export_data(self):
        """Export training data."""
        file_path = filedialog.asksaveasfilename(
            title="تصدير بيانات التدريب",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("CSV", "*.csv")]
        )

        if not file_path:
            return

        fmt = "csv" if file_path.endswith(".csv") else "json"

        try:
            count = self.trainer.export_training_data(file_path, format=fmt)
            messagebox.showinfo("تم", f"تم تصدير {count} مثال تدريبي")
        except Exception as e:
            messagebox.showerror("خطأ", str(e))

    def _apply_corrections(self):
        """Apply learned corrections to all unreviewed snippets."""
        if not self.current_snippets:
            return

        applied = 0
        for snippet in self.current_snippets:
            if not snippet.is_reviewed:
                result = self.trainer.auto_correct(snippet.ocr_text)
                if result["was_corrected"]:
                    snippet.corrected_text = result["corrected"]
                    applied += 1

        # Refresh display
        self._display_snippet(self.current_index)
        messagebox.showinfo("تم", f"تم تطبيق {applied} تصحيح تلقائي")

    def run(self):
        """Start the UI."""
        self.root.mainloop()

    def close(self):
        """Clean up resources."""
        self.trainer.close()
        self.root.destroy()


def main():
    """Entry point."""
    print("=" * 60)
    print("OCR Snippet Review & Training UI")
    print("=" * 60)
    print("\nStarting interactive review interface...")
    print("Shortcuts:")
    print("  ← →     Navigate snippets")
    print("  Enter   Save correction")
    print("  Space   Mark as correct")
    print("  Escape  Skip")
    print()

    app = SnippetReviewUI()
    try:
        app.run()
    finally:
        app.close()


if __name__ == "__main__":
    main()
