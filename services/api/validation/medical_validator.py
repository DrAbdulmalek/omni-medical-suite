"""
LLM-Based Medical Validator
Validates extracted medical text for clinical plausibility using LLM reasoning.
Checks: dosage logic, drug interactions, temporal consistency, terminology validity.
"""

import json
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class ValidationSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """A single validation issue."""
    category: str
    severity: ValidationSeverity
    message: str
    suggestion: str
    confidence: float  # 0.0 - 1.0
    source_text: str
    location: Optional[str] = None


@dataclass
class ValidationResult:
    """Complete validation result."""
    is_valid: bool
    overall_confidence: float
    issues: List[ValidationIssue]
    suggestions: List[str]
    validated_entities: List[Dict[str, Any]]


class MedicalValidator:
    """
    Medical text validator using rule-based + LLM hybrid approach.

    Validation Categories:
    1. Dosage Logic — Is 50mg reasonable for this drug?
    2. Drug Interactions — Conflicting medications?
    3. Temporal Consistency — Dates make sense?
    4. Terminology — Valid medical terms?
    5. Laterality — Right/left consistent?
    6. Severity — Appropriate severity markers?

    Usage:
        validator = MedicalValidator(llm_gateway)
        result = await validator.validate(extracted_text, context="prescription")
    """

    # Common drug dosage ranges (simplified — production should use FDA/EMA database)
    DRUG_DOSAGES = {
        "paracetamol": {"min_mg": 250, "max_mg": 1000, "unit": "mg", "frequency": "q4-6h"},
        "acetaminophen": {"min_mg": 250, "max_mg": 1000, "unit": "mg", "frequency": "q4-6h"},
        "ibuprofen": {"min_mg": 200, "max_mg": 800, "unit": "mg", "frequency": "q6-8h"},
        "amoxicillin": {"min_mg": 250, "max_mg": 1000, "unit": "mg", "frequency": "q8h"},
        "metformin": {"min_mg": 500, "max_mg": 2000, "unit": "mg", "frequency": "daily-bid"},
        "atorvastatin": {"min_mg": 10, "max_mg": 80, "unit": "mg", "frequency": "daily"},
        "lisinopril": {"min_mg": 2.5, "max_mg": 40, "unit": "mg", "frequency": "daily"},
        "amlodipine": {"min_mg": 2.5, "max_mg": 10, "unit": "mg", "frequency": "daily"},
        "omeprazole": {"min_mg": 10, "max_mg": 40, "unit": "mg", "frequency": "daily"},
        "aspirin": {"min_mg": 75, "max_mg": 325, "unit": "mg", "frequency": "daily"},
    }

    # Known drug interactions (simplified)
    DRUG_INTERACTIONS = {
        ("warfarin", "aspirin"): "Increased bleeding risk",
        ("metformin", "contrast"): "Lactic acidosis risk",
        ("lisinopril", "spironolactone"): "Hyperkalemia risk",
        ("simvastatin", "clarithromycin"): "Rhabdomyolysis risk",
    }

    # Arabic medical terminology patterns
    ARABIC_MEDICAL_PATTERNS = {
        "dosage": r"(\d+(?:\.\d+)?)\s*(ملغ|مجم|mg|mcg|ml|مل|جرام|g)",
        "frequency": r"(مرة|مرتين|ثلاث|أربع|خمس|يومياً|أسبوعياً|شهرياً|q\d+h|bid|tid|qid)",
        "duration": r"(لمدة|لـ)\s*(\d+)\s*(يوم|أسبوع|شهر|سنة)",
    }

    def __init__(self, llm_gateway=None):
        """
        Args:
            llm_gateway: Optional AI gateway for LLM-based validation
        """
        self.llm = llm_gateway

    async def validate(
        self,
        text: str,
        context: Optional[str] = None,
        language: str = "auto"
    ) -> ValidationResult:
        """
        Validate medical text.

        Args:
            text: Extracted medical text
            context: Document context ("prescription", "report", "lab", "discharge")
            language: "ar", "en", or "auto"

        Returns:
            ValidationResult with issues and suggestions
        """
        issues = []
        suggestions = []

        # 1. Dosage validation
        dosage_issues = await self._validate_dosage(text)
        issues.extend(dosage_issues)

        # 2. Drug interaction check
        interaction_issues = await self._check_interactions(text)
        issues.extend(interaction_issues)

        # 3. Temporal consistency
        temporal_issues = await self._validate_temporal(text)
        issues.extend(temporal_issues)

        # 4. Terminology validation
        term_issues = await self._validate_terminology(text, language)
        issues.extend(term_issues)

        # 5. Laterality consistency
        laterality_issues = await self._validate_laterality(text)
        issues.extend(laterality_issues)

        # 6. LLM-based deep validation (if gateway available)
        if self.llm:
            llm_issues = await self._llm_validate(text, context)
            issues.extend(llm_issues)

        # Calculate overall validity
        critical_count = sum(1 for i in issues if i.severity == ValidationSeverity.CRITICAL)
        error_count = sum(1 for i in issues if i.severity == ValidationSeverity.ERROR)

        # Stricter medical safety: any error should be flagged
        is_valid = critical_count == 0 and error_count == 0

        # Generate suggestions from issues
        suggestions = [i.suggestion for i in issues if i.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL)]

        # Overall confidence
        if not issues:
            confidence = 0.95
        else:
            weights = {ValidationSeverity.INFO: 0.05, ValidationSeverity.WARNING: 0.15, 
                      ValidationSeverity.ERROR: 0.30, ValidationSeverity.CRITICAL: 0.50}
            total_penalty = sum(weights.get(i.severity, 0.1) * (1 - i.confidence) for i in issues)
            confidence = max(0.3, 1.0 - total_penalty)

        return ValidationResult(
            is_valid=is_valid,
            overall_confidence=round(confidence, 2),
            issues=issues,
            suggestions=suggestions,
            validated_entities=self._extract_entities(text)
        )

    async def _validate_dosage(self, text: str) -> List[ValidationIssue]:
        """Validate drug dosages against known ranges."""
        issues = []

        # Find dosage patterns
        for match in re.finditer(self.ARABIC_MEDICAL_PATTERNS["dosage"], text, re.IGNORECASE):
            amount = float(match.group(1))
            unit = match.group(2).lower()

            # Try to find nearby drug name
            context_window = text[max(0, match.start()-50):match.end()+50]
            drug_name = self._extract_drug_name(context_window)

            if drug_name and drug_name in self.DRUG_DOSAGES:
                drug_info = self.DRUG_DOSAGES[drug_name]

                if amount < drug_info["min_mg"]:
                    issues.append(ValidationIssue(
                        category="dosage",
                        severity=ValidationSeverity.WARNING,
                        message=f"جرعة {drug_name} ({amount}{unit}) أقل من الحد الأدنى ({drug_info['min_mg']}{drug_info['unit']})",
                        suggestion=f"تأكد من الجرعة. الحد الأدنى الموصى به: {drug_info['min_mg']}{drug_info['unit']}",
                        confidence=0.85,
                        source_text=match.group(0),
                        location=f"char_{match.start()}"
                    ))
                elif amount > drug_info["max_mg"]:
                    issues.append(ValidationIssue(
                        category="dosage",
                        severity=ValidationSeverity.ERROR,
                        message=f"جرعة {drug_name} ({amount}{unit}) تتجاوز الحد الأقصى ({drug_info['max_mg']}{drug_info['unit']})",
                        suggestion=f"⚠️ جرعة مرتفعة! الحد الأقصى الآمن: {drug_info['max_mg']}{drug_info['unit']}. استشر الطبيب.",
                        confidence=0.92,
                        source_text=match.group(0),
                        location=f"char_{match.start()}"
                    ))
            elif drug_name:
                issues.append(ValidationIssue(
                    category="dosage",
                    severity=ValidationSeverity.INFO,
                    message=f"دواء غير معروف في قاعدة البيانات: {drug_name}",
                    suggestion="تأكد من صحة اسم الدواء أو أضفه إلى قاعدة البيانات",
                    confidence=0.60,
                    source_text=match.group(0)
                ))

        return issues

    async def _check_interactions(self, text: str) -> List[ValidationIssue]:
        """Check for known drug interactions."""
        issues = []
        found_drugs = []

        # Extract all drug mentions
        for drug in self.DRUG_DOSAGES.keys():
            if re.search(rf"\b{drug}\b", text, re.IGNORECASE):
                found_drugs.append(drug)

        # Check pairs
        for i, drug1 in enumerate(found_drugs):
            for drug2 in found_drugs[i+1:]:
                pair = tuple(sorted([drug1, drug2]))
                if pair in self.DRUG_INTERACTIONS:
                    issues.append(ValidationIssue(
                        category="drug_interaction",
                        severity=ValidationSeverity.CRITICAL,
                        message=f"تعارض دوائي محتمل: {drug1} + {drug2}",
                        suggestion=f"⚠️ {self.DRUG_INTERACTIONS[pair]}. استشر الصيدلي أو الطبيب فوراً.",
                        confidence=0.90,
                        source_text=f"{drug1} + {drug2}"
                    ))

        return issues

    async def _validate_temporal(self, text: str) -> List[ValidationIssue]:
        """Validate temporal consistency."""
        issues = []

        # Check for future dates in past context
        date_pattern = r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})"
        dates = list(re.finditer(date_pattern, text))

        if len(dates) > 1:
            # Check chronological order
            parsed_dates = []
            for d in dates:
                try:
                    day, month, year = int(d.group(1)), int(d.group(2)), int(d.group(3))
                    if year < 100:
                        year += 2000
                    parsed_dates.append((year, month, day, d))
                except ValueError:
                    continue

            for i in range(len(parsed_dates) - 1):
                if parsed_dates[i] > parsed_dates[i+1]:
                    issues.append(ValidationIssue(
                        category="temporal",
                        severity=ValidationSeverity.WARNING,
                        message="تواريخ غير متسلسلة في المستند",
                        suggestion="تأكد من ترتيب التواريخ الزمني",
                        confidence=0.75,
                        source_text=f"{parsed_dates[i][3].group(0)} → {parsed_dates[i+1][3].group(0)}"
                    ))

        return issues

    async def _validate_terminology(self, text: str, language: str) -> List[ValidationIssue]:
        """Validate medical terminology."""
        issues = []

        # Check for common OCR errors in medical terms
        common_errors = {
            "التهاب": ["التهب", "التهابب", "التهبب"],
            "جرعة": ["جرعه", "جرع", "جرعتا"],
            "مريض": ["مريضض", "مريظ", "مريضة"],
            "دواء": ["دوا", "دواءء", "دواة"],
        }

        for correct, errors in common_errors.items():
            for error in errors:
                if error in text and correct not in text:
                    issues.append(ValidationIssue(
                        category="terminology",
                        severity=ValidationSeverity.WARNING,
                        message=f"خطأ إملائي محتمل: '{error}' → '{correct}'",
                        suggestion=f"هل تقصد '{correct}'؟",
                        confidence=0.80,
                        source_text=error
                    ))

        return issues

    async def _validate_laterality(self, text: str) -> List[ValidationIssue]:
        """Validate laterality consistency."""
        issues = []

        right_count = len(re.findall(r"\b(يمين|أيمن|right|rt)\b", text, re.IGNORECASE))
        left_count = len(re.findall(r"\b(يسار|أيسر|left|lt)\b", text, re.IGNORECASE))

        # Check for conflicting laterality in same context
        sentences = text.split(".")
        for sentence in sentences:
            has_right = bool(re.search(r"\b(يمين|أيمن|right)\b", sentence, re.IGNORECASE))
            has_left = bool(re.search(r"\b(يسار|أيسر|left)\b", sentence, re.IGNORECASE))

            if has_right and has_left:
                issues.append(ValidationIssue(
                    category="laterality",
                    severity=ValidationSeverity.ERROR,
                    message="تعارض في الجانبية في نفس الجملة: يمين + يسار",
                    suggestion="⚠️ تأكد من الجانب الصحيح — خطأ جانبي قد يؤدي إلى خطأ جراحي",
                    confidence=0.88,
                    source_text=sentence.strip()[:100]
                ))

        return issues

    async def _llm_validate(self, text: str, context: Optional[str]) -> List[ValidationIssue]:
        """Deep validation using LLM (placeholder for actual integration)."""
        issues = []

        if not self.llm:
            return issues

        # This would call the LLM gateway with a structured prompt
        # For now, return placeholder
        prompt = f"""Validate the following medical text for clinical plausibility:
        Context: {context or "unknown"}
        Text: {text[:1000]}

        Check for:
        1. Dosage appropriateness
        2. Drug interactions
        3. Diagnostic consistency
        4. Missing critical information

        Return JSON with issues found."""

        # Placeholder: actual implementation would call self.llm.complete(prompt)
        # and parse the structured response

        return issues

    def _extract_drug_name(self, context: str) -> Optional[str]:
        """Extract drug name from context window."""
        for drug in self.DRUG_DOSAGES.keys():
            if re.search(rf"\b{drug}\b", context, re.IGNORECASE):
                return drug
        return None

    def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract validated medical entities from text."""
        entities = []

        # Extract medications
        for match in re.finditer(self.ARABIC_MEDICAL_PATTERNS["dosage"], text, re.IGNORECASE):
            entities.append({
                "type": "dosage",
                "value": match.group(0),
                "amount": float(match.group(1)),
                "unit": match.group(2),
                "position": match.start()
            })

        # Extract frequencies
        for match in re.finditer(self.ARABIC_MEDICAL_PATTERNS["frequency"], text, re.IGNORECASE):
            entities.append({
                "type": "frequency",
                "value": match.group(0),
                "position": match.start()
            })

        return entities
