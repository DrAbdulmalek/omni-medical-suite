#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
medical_context_protector.py
Prevents semantic merging of medically conflicting information.
Even when vector similarity is high, certain medical attributes must NOT be merged.
"""

from typing import Dict, List, Optional, Set, Tuple


class MedicalContextProtector:
    """
    Medical context protection layer for semantic deduplication.
    
    Prevents merging of medical information that is semantically similar
    but clinically different (e.g., right vs left, acute vs chronic).
    
    Protected attribute categories:
    - laterality: anatomical sides (right/left/bilateral)
    - severity: condition severity levels
    - fracture_type: bone fracture classifications  
    - temporal: time-based descriptors
    - body_region: specific anatomical regions
    """

    PROTECTED_ATTRIBUTES: Dict[str, Dict] = {
        "laterality": {
            "values": {
                # Arabic
                "أيمن", "أيسر", "ثنائي", "أمامي", "خلفي", "جانبي", 
                "إنسي", "وحشي", "علوي", "سفلي", "قحفي", "ذيلي",
                "ظهري", "بطني", "إنسي", "جانبي",
                # English
                "right", "left", "bilateral", "anterior", "posterior",
                "lateral", "medial", "superior", "inferior", "cranial",
                "caudal", "dorsal", "ventral", "proximal", "distal",
            },
            "severity": "critical"  # wrong side = potential surgical error
        },
        "severity": {
            "values": {
                # Arabic
                "حاد", "مزمن", "خفيف", "متوسط", "شديد", "مهدد للحياة",
                "بسيط", "خطير", "مستعصٍ",
                # English
                "acute", "chronic", "mild", "moderate", "severe",
                "life-threatening", "critical", "minor", "serious",
                "refractory", "intractable",
            },
            "severity": "high"
        },
        "fracture_type": {
            "values": {
                # Arabic
                "مفتوح", "مغلق", "مضاعف", "شعري", "مُحيط", "منفصل",
                "مضغوط", "ملتوي", "منزلق",
                # English
                "open", "closed", "comminuted", "hairline", "greenstick",
                "displaced", "compressed", "spiral", "impacted",
                "transverse", "oblique", "pathological",
            },
            "severity": "critical"
        },
        "temporal": {
            "values": {
                # Arabic
                "حديث", "قديم", "متكرر", "مستعصٍ", "حادث", "سابق",
                "مبكر", "متأخر", "مؤقت", "دائم",
                # English
                "recent", "old", "recurrent", "persistent", "previous",
                "early", "late", "temporary", "permanent", "acute",
                "subacute",
            },
            "severity": "medium"
        },
        "body_region": {
            "values": {
                # Arabic
                "العنق", "الظهر", "الصدر", "البطن", "الحوض", "الركبة",
                "الكتف", "المرفق", "الرسغ", "الكاحل", "العمود الفقري",
                # English
                "cervical", "thoracic", "lumbar", "sacral", "pelvic",
                "shoulder", "elbow", "wrist", "ankle", "spine",
                "femoral", "tibial", "humeral", "radial",
            },
            "severity": "medium"
        }
    }

    def check_merge_safety(self, chunk1: str, chunk2: str) -> Tuple[bool, Optional[str]]:
        """
        Check if two text chunks can be safely merged without losing
        clinically significant differences.
        
        Args:
            chunk1: First text chunk
            chunk2: Second text chunk
            
        Returns:
            Tuple of (allow_merge: bool, conflict_reason: Optional[str])
        """
        c1 = chunk1.lower()
        c2 = chunk2.lower()

        for attr_name, config in self.PROTECTED_ATTRIBUTES.items():
            values = config["values"]
            v1 = {v for v in values if v in c1}
            v2 = {v for v in values if v in c2}
            if v1 and v2 and v1 != v2:
                return (False, 
                    f"Conflict in {attr_name}: '{v1}' vs '{v2}' "
                    f"(severity: {config['severity']})")
        return True, None

    def safe_merge(self, chunks: List[str]) -> List[Dict]:
        """
        Merge chunks with medical context protection.
        Items with conflicting medical attributes are kept as separate entries.
        
        Args:
            chunks: List of text chunks to merge
            
        Returns:
            List of dicts with keys: text, id, status, conflicts
        """
        merged: List[Dict] = []
        for i, chunk in enumerate(chunks):
            item = {"text": chunk, "id": i, "status": "pending", "conflicts": []}
            for existing in merged:
                allow, reason = self.check_merge_safety(chunk, existing["text"])
                if not allow:
                    item["status"] = "protected_unique"
                    item["conflicts"].append({
                        "with": existing["id"], "reason": reason
                    })
                    existing.setdefault("conflict_with", []).append(i)
            if item["status"] == "pending":
                item["status"] = "safe_to_merge"
            merged.append(item)
        return merged

    def get_conflict_report(self, merged_items: List[Dict]) -> List[Dict]:
        """
        Generate a list of conflicts for medical review.
        
        Args:
            merged_items: Output from safe_merge()
            
        Returns:
            List of conflict dicts for review
        """
        conflicts = []
        for item in merged_items:
            for c in item.get("conflicts", []):
                conflicts.append({
                    "chunk_id": item["id"],
                    "text": item["text"],
                    "conflicts_with": c["with"],
                    "reason": c["reason"],
                    "requires_doctor_review": "critical" in c["reason"]
                })
        return conflicts

    def is_medical_term(self, text: str) -> bool:
        """Check if text contains protected medical terminology."""
        text_lower = text.lower()
        for config in self.PROTECTED_ATTRIBUTES.values():
            if any(v in text_lower for v in config["values"]):
                return True
        return False
