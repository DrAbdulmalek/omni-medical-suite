"""
اختبارات وحدة القواميس الطبية — OmniMedical Suite

يغطي: BGL Converter, StarDict Reader, TMX Processor, Dictionary Pipeline
"""

import os
import sys
import json
import tempfile
import unittest

# إضافة المسار
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from packages.medical.bgl_converter import (
    BGLConverter, TextFilter, OutputFormat, DictionaryEntry, BGLReader
)
from packages.medical.tmx_processor import (
    TMXParser, TMXProcessor, TMXMedicalExtractor,
    TMXEntry, TMXHeader, EntryStatus, MedicalTermEntry
)
from packages.medical.dictionary_manager import MedicalDictionaryManager
from packages.medical.dictionary_pipeline import DictionaryPipeline


class TestTextFilter(unittest.TestCase):
    """اختبارات فلاتر النصوص"""

    def test_fix_characters(self):
        # استبدال الأحرف غير المطبوعة
        text = "Hello\x91World\x93Test\x94"
        result = TextFilter.fix_characters(text)
        self.assertNotIn("\x91", result)
        self.assertIn("'", result)

    def test_strip_html(self):
        html = "<p>Hello</p><br/>World<li>Item</li>"
        result = TextFilter.strip_html(html)
        self.assertNotIn("<p>", result)
        self.assertNotIn("<br", result)
        self.assertIn("Hello", result)

    def test_clean_definition(self):
        text = "<p>Definition</p>  of   <b>term</b>"
        result = TextFilter.clean_definition(text)
        self.assertNotIn("<", result)
        self.assertIn("Definition", result)

    def test_clean_term(self):
        text = "  Hello &amp; World  "
        result = TextFilter.clean_term(text)
        self.assertEqual(result, "Hello & World")


class TestBGLConverter(unittest.TestCase):
    """اختبارات محول BGL"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.converter = BGLConverter()

    def test_read_json_file(self):
        # إنشاء ملف JSON تجريبي
        test_data = [
            {"term": "fracture", "definition": "كسر", "category": "fractures"},
            {"term": "joint", "definition": "مفصل", "category": "anatomy"},
        ]
        json_path = os.path.join(self.temp_dir, "test.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        entries = self.converter.read_file(json_path)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].term, "fracture")

    def test_convert_json_to_json(self):
        test_data = [
            {"term": "bone", "definition": "عظم", "category": "anatomy"},
        ]
        input_path = os.path.join(self.temp_dir, "input.json")
        with open(input_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        output_path = os.path.join(self.temp_dir, "output.json")
        result = self.converter.convert(input_path, output_format="json",
                                        output_path=output_path)

        self.assertTrue(result["total_entries"] >= 1)
        self.assertTrue(os.path.exists(output_path))

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("_metadata", data)
        self.assertIn("entries", data)

    def test_convert_to_csv(self):
        test_data = [
            {"term": "test", "ar": "اختبار", "type": "general"},
        ]
        input_path = os.path.join(self.temp_dir, "input.json")
        with open(input_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        output_path = os.path.join(self.temp_dir, "output.csv")
        result = self.converter.convert(input_path, output_format="csv",
                                        output_path=output_path)
        self.assertTrue(os.path.exists(output_path))

    def test_convert_to_sqlite(self):
        test_data = [{"term": "sql_test", "definition": "SQL test entry"}]
        input_path = os.path.join(self.temp_dir, "input.json")
        with open(input_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        output_path = os.path.join(self.temp_dir, "output.db")
        result = self.converter.convert(input_path, output_format="sqlite",
                                        output_path=output_path)
        self.assertTrue(os.path.exists(output_path))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)


class TestTMXParser(unittest.TestCase):
    """اختبارات محلل TMX"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.parser = TMXParser()

    def test_parse_valid_tmx(self):
        tmx_content = """<?xml version="1.4" encoding="UTF-8"?>
<!DOCTYPE tmx SYSTEM "tmx14.dtd">
<tmx version="1.4">
  <header creationtool="test" creationtoolversion="1.0" datatype="plaintext"
          segtype="sentence" adminlang="en" srclang="en"/>
  <body>
    <tu tuid="1">
      <tuv xml:lang="en"><seg>fracture</seg></tuv>
      <tuv xml:lang="ar"><seg>كسر</seg></tuv>
    </tu>
    <tu tuid="2">
      <tuv xml:lang="en"><seg>bone</seg></tuv>
      <tuv xml:lang="ar"><seg>عظم</seg></tuv>
    </tu>
  </body>
</tmx>"""
        tmx_path = os.path.join(self.temp_dir, "test.tmx")
        with open(tmx_path, "w", encoding="utf-8") as f:
            f.write(tmx_content)

        header, entries = self.parser.parse(tmx_path)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].source_text, "fracture")
        self.assertEqual(entries[0].target_text, "كسر")
        self.assertEqual(entries[0].source_lang, "en")
        self.assertEqual(entries[0].target_lang, "ar")

    def test_parse_tmx_with_notes(self):
        tmx_content = """<?xml version="1.4" encoding="UTF-8"?>
<!DOCTYPE tmx SYSTEM "tmx14.dtd">
<tmx version="1.4">
  <header srclang="en"/>
  <body>
    <tu tuid="1">
      <tuv xml:lang="en"><seg>arthritis</seg></tuv>
      <tuv xml:lang="ar"><seg>التهاب المفاصل</seg></tuv>
      <note>medical term</note>
    </tu>
  </body>
</tmx>"""
        tmx_path = os.path.join(self.temp_dir, "test_notes.tmx")
        with open(tmx_path, "w", encoding="utf-8") as f:
            f.write(tmx_content)

        header, entries = self.parser.parse(tmx_path)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].notes, "medical term")

    def test_export_to_tmx(self):
        entries = [
            TMXEntry(tu_id="1", source_lang="en", target_lang="ar",
                     source_text="surgery", target_text="عملية"),
        ]
        header = TMXHeader(srclang="en")
        output_path = os.path.join(self.temp_dir, "export.tmx")

        result = self.parser.export_to_tmx(entries, header, output_path)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(output_path))

        # إعادة قراءة للتحقق
        _, reloaded = self.parser.parse(output_path)
        self.assertEqual(len(reloaded), 1)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)


class TestTMXMedicalExtractor(unittest.TestCase):
    """اختبارات مستخرج المصطلحات الطبية"""

    def setUp(self):
        self.extractor = TMXMedicalExtractor()

    def test_detect_medical_category_fracture(self):
        category = self.extractor._detect_medical_category("fracture of the femur")
        self.assertEqual(category, "fractures")

    def test_detect_medical_category_medication(self):
        category = self.extractor._detect_medical_category("patient needs ibuprofen tablets")
        self.assertEqual(category, "medications")

    def test_detect_medical_category_anatomy(self):
        category = self.extractor._detect_medical_category("shoulder joint and muscle")
        self.assertEqual(category, "anatomy")

    def test_detect_medical_category_generic(self):
        category = self.extractor._detect_medical_category("hello world test")
        self.assertEqual(category, "general_medical")

    def test_extract_from_entries(self):
        entries = [
            TMXEntry(tu_id="1", source_text="fracture", target_text="كسر",
                     source_lang="en", target_lang="ar"),
            TMXEntry(tu_id="2", source_text="hello", target_text="مرحبا",
                     source_lang="en", target_lang="ar"),
            TMXEntry(tu_id="3", source_text="ibuprofen 400mg", target_text="إيبوبروفين 400 ملغ",
                     source_lang="en", target_lang="ar"),
        ]
        terms = self.extractor.extract_medical_terms(entries)
        self.assertTrue(len(terms) >= 2)  # fracture + ibuprofen على الأقل

    def test_deduplicate(self):
        entries = [
            MedicalTermEntry(term_source="fracture", term_target="كسر", confidence=0.8),
            MedicalTermEntry(term_source="fracture", term_target="كسر", confidence=0.5),
            MedicalTermEntry(term_source="bone", term_target="عظم", confidence=0.7),
        ]
        result = self.extractor.deduplicate(entries)
        self.assertEqual(len(result), 2)

    def test_filter_by_confidence(self):
        entries = [
            MedicalTermEntry(term_source="a", term_target="a", confidence=0.9),
            MedicalTermEntry(term_source="b", term_target="b", confidence=0.3),
        ]
        result = self.extractor.filter_by_confidence(entries, 0.5)
        self.assertEqual(len(result), 1)


class TestDictionaryManager(unittest.TestCase):
    """اختبارات مدير القواميس"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_dict.db")
        self.manager = MedicalDictionaryManager(db_path=self.db_path)

    def test_import_json_dictionary(self):
        test_data = {
            "entries": [
                {"term": "fracture", "definition": "كسر عظمي", "category": "fractures"},
                {"term": "joint", "definition": "مفصل", "category": "anatomy"},
                {"term": "arthritis", "definition": "التهاب المفاصل", "category": "diseases"},
            ]
        }
        json_path = os.path.join(self.temp_dir, "test.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        result = self.manager.import_dictionary(json_path, title="Test Dictionary")
        self.assertTrue(result.success)
        self.assertTrue(result.total_entries >= 3)

    def test_search(self):
        # استيراد ثم بحث
        test_data = {"entries": [
            {"term": "fracture", "definition": "كسر"},
            {"term": "bone", "definition": "عظم"},
        ]}
        json_path = os.path.join(self.temp_dir, "search.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        self.manager.import_dictionary(json_path)
        results = self.manager.search("fracture")
        self.assertTrue(len(results) >= 1)

    def test_get_stats(self):
        stats = self.manager.get_dictionary_stats()
        self.assertIn("total_terms", stats)
        self.assertIn("total_dictionaries", stats)

    def test_add_and_lookup_correction(self):
        self.manager.add_correction("fractur", "fracture", language="en")
        correction = self.manager.lookup_correction("fractur")
        self.assertEqual(correction, "fracture")

    def test_protected_terms(self):
        self.manager.add_correction("test", "test", language="en")
        stats = self.manager.get_dictionary_stats()
        self.assertIn("total_protected_terms", stats)

    def test_export_to_json(self):
        test_data = {"entries": [
            {"term": "test", "definition": "اختبار"},
        ]}
        json_path = os.path.join(self.temp_dir, "export_input.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        self.manager.import_dictionary(json_path)

        output_path = os.path.join(self.temp_dir, "export_output.json")
        result = self.manager.export_to_json(output_path)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(output_path))

    def test_list_dictionaries(self):
        dicts = self.manager.list_dictionaries()
        self.assertIsInstance(dicts, list)

    def test_get_categories(self):
        categories = self.manager.get_categories()
        self.assertIsInstance(categories, list)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)


class TestDictionaryPipeline(unittest.TestCase):
    """اختبارات خط أنابيب القواميس"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.pipeline = DictionaryPipeline(
            db_path=os.path.join(self.temp_dir, "pipeline.db"),
            data_dir=os.path.join(self.temp_dir, "data"),
        )

    def test_import_json(self):
        test_data = {"entries": [
            {"term": "test", "definition": "اختبار", "category": "general_medical"},
        ]}
        json_path = os.path.join(self.temp_dir, "test.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        result = self.pipeline.import_bgl(json_path)
        # JSON يتم التعامل معه عبر dictionary_manager
        self.assertIn("success", result)

    def test_search(self):
        test_data = {"entries": [
            {"term": "medical", "definition": "طبي"},
        ]}
        json_path = os.path.join(self.temp_dir, "search.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        self.pipeline.import_bgl(json_path)
        results = self.pipeline.search("medical")
        self.assertIsInstance(results, list)

    def test_get_stats(self):
        stats = self.pipeline.get_stats()
        self.assertIn("total_terms", stats)

    def test_validate_integrity(self):
        validation = self.pipeline.validate_integrity()
        self.assertIn("valid", validation)
        self.assertIn("issues", validation)

    def test_list_dictionaries(self):
        dicts = self.pipeline.list_dictionaries()
        self.assertIsInstance(dicts, list)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
