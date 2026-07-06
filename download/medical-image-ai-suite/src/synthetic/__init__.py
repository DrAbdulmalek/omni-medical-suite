"""
وحدة توليد البيانات الاصطناعية - Synthetic Data Generation
توليد صور طبية واقعية باستخدام شبكات الخصومة التوليدية (GANs)
"""

from .medgan import MedGAN, MedicalImageGenerator

__all__ = ["MedGAN", "MedicalImageGenerator"]
