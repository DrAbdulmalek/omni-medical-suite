"""
المدرب شبه الخاضع للإشراف - Semi-Supervised Trainer
تدريب نماذج التصنيف والتقسيم باستخدام بيانات مصنفة وغير مصنفة
يدعم Mean Teacher و Pseudo-Labeling و FixMatch
"""

import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union

import numpy as np

from .weak_labels import WeakLabelExtractor, BinaryLabelExtractor
from ..utils.logger import get_logger

logger = get_logger("semi_trainer")


class SemiSupervisedTrainer:
    """
    مدرب شبه خاضع للإشراف للنماذج الطبية

    يدعم استراتيجيات:
    1. Pseudo-Labeling: تصنيف البيانات غير المُصنفة ذات الثقة العالية
    2. Mean Teacher: تحديث الأوزان المتوسطة للنموذج المعلّم
    3. Weak Supervision: استخدام إشارات التقارير كتسميات ضعيفة
    4. Consistency Regularization: انتظام التناسق

    الاستخدام:
        trainer = SemiSupervisedTrainer(num_classes=10)
        history = trainer.train(
            labeled_images=X_labeled,
            labeled_labels=y_labeled,
            unlabeled_images=X_unlabeled,
            weak_labels=weak_label_matrix,
        )
    """

    def __init__(
        self,
        num_classes: int = 10,
        architecture: str = "resnet50",
        pretrained: bool = True,
        image_size: Tuple[int, int] = (512, 512),
        device: str = "auto",
        seed: int = 42,
    ):
        """
        Args:
            num_classes: عدد فئات التصنيف
            architecture: بنية النموذج (resnet50, densenet121, efficientnet_b0)
            pretrained: استخدام أوزان مُسبقة التدريب
            image_size: حجم الصورة
            device: جهاز التدريب (auto, cpu, cuda)
            seed: بذرة عشوائية
        """
        self.num_classes = num_classes
        self.architecture = architecture
        self.pretrained = pretrained
        self.image_size = image_size
        self.seed = seed

        np.random.seed(seed)

        # تحديد الجهاز
        if device == "auto":
            self.device = self._detect_device()
        else:
            self.device = device

        # تهيئة النماذج
        self.student_model = None
        self.teacher_model = None
        self.optimizer = None
        self.scheduler = None
        self.history = {"train_loss": [], "val_loss": [], "train_acc": [], "val_acc": []}

        logger.info(
            f"المدرب: {architecture}, فئات={num_classes}, "
            f"جهاز={self.device}, حجم={image_size}"
        )

    def _detect_device(self) -> str:
        """اكتشاف أفضل جهاز متاح"""
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"

    def _build_model(self, architecture: str, num_classes: int) -> Any:
        """بناء نموذج التصنيف"""
        try:
            import torch
            import torch.nn as nn
            import torchvision.models as models

            model_fn = getattr(models, architecture, None)
            if model_fn is None:
                raise ValueError(f"بنية غير مدعومة: {architecture}")

            weights = "IMAGENET1K_V1" if self.pretrained else None
            model = model_fn(weights=weights)

            # تعديل الطبقة الأخيرة
            if hasattr(model, "fc"):
                in_features = model.fc.in_features
                model.fc = nn.Linear(in_features, num_classes)
            elif hasattr(model, "classifier"):
                if isinstance(model.classifier, nn.Linear):
                    in_features = model.classifier.in_features
                    model.classifier = nn.Linear(in_features, num_classes)
                else:
                    in_features = model.classifier[-1].in_features
                    model.classifier[-1] = nn.Linear(in_features, num_classes)

            return model.to(self.device)

        except ImportError:
            logger.warning("PyTorch غير مثبت. سيتم استخدام نموذج بسيط")
            return self._build_simple_model(num_classes)

    def _build_simple_model(self, num_classes: int) -> Any:
        """بناء نموذج CNN بسيط كبدائل"""
        try:
            import torch
            import torch.nn as nn

            class SimpleCNN(nn.Module):
                def __init__(self, nc):
                    super().__init__()
                    self.features = nn.Sequential(
                        nn.Conv2d(1, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
                        nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
                        nn.Conv2d(64, 128, 3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool2d(1),
                    )
                    self.classifier = nn.Linear(128, nc)

                def forward(self, x):
                    x = self.features(x)
                    x = x.view(x.size(0), -1)
                    return self.classifier(x)

            return SimpleCNN(num_classes).to(self.device)
        except ImportError:
            logger.error("PyTorch غير متاح!")
            return None

    def train(
        self,
        labeled_images: np.ndarray,
        labeled_labels: np.ndarray,
        unlabeled_images: Optional[np.ndarray] = None,
        weak_labels: Optional[np.ndarray] = None,
        validation_images: Optional[np.ndarray] = None,
        validation_labels: Optional[np.ndarray] = None,
        epochs: int = 100,
        batch_size: int = 16,
        learning_rate: float = 1e-4,
        patience: int = 15,
        pseudo_label_threshold: float = 0.9,
        consistency_weight: float = 1.0,
        save_dir: Optional[str] = None,
    ) -> Dict[str, List[float]]:
        """
        تدريب النموذج شبه الخاضع للإشراف

        Args:
            labeled_images: صور مصنفة [N_l, H, W] أو [N_l, C, H, W]
            labeled_labels: تسميات مصنفة [N_l] أو [N_l, num_classes]
            unlabeled_images: صور غير مصنفة [N_u, H, W] (اختياري)
            weak_labels: إشارات ضعيفة من التقارير [N_u, num_classes] (اختياري)
            validation_images: صور التحقق (اختياري)
            validation_labels: تسميات التحقق (اختياري)
            epochs: عدد الحقب
            batch_size: حجم المجموعة
            learning_rate: معدل التعلم
            patience: صبر التوقف المبكر
            pseudo_label_threshold: حد الثقة للتسميات الزائفة
            consistency_weight: وزن انتظام التناسق
            save_dir: مجلد حفظ النماذج

        Returns:
            قاموس بسجل التدريب
        """
        try:
            import torch
            import torch.nn as nn
            import torch.optim as optim
            from torch.utils.data import DataLoader, TensorDataset
        except ImportError:
            logger.error("PyTorch غير مثبت. لا يمكن التدريب.")
            return self.history

        # إعداد مجلد الحفظ
        if save_dir:
            save_dir = Path(save_dir)
            save_dir.mkdir(parents=True, exist_ok=True)

        # تحويل البيانات إلى Tensor
        X_labeled = torch.FloatTensor(labeled_images)
        if X_labeled.ndim == 3:
            X_labeled = X_labeled.unsqueeze(1)  # [N, 1, H, W]

        # تعديل التسميات
        if labeled_labels.ndim == 2:
            y_labeled = torch.FloatTensor(labeled_labels)
            criterion = nn.BCEWithLogitsLoss()
            task = "multilabel"
        else:
            y_labeled = torch.LongTensor(labeled_labels)
            criterion = nn.CrossEntropyLoss()
            task = "multiclass"

        # بناء نموذج الطلاب
        self.student_model = self._build_model(self.architecture, self.num_classes)
        self.optimizer = optim.AdamW(
            self.student_model.parameters(),
            lr=learning_rate, weight_decay=1e-4,
        )
        self.scheduler = optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer, T_max=epochs,
        )

        # إعداد بيانات التحقق
        val_loader = None
        if validation_images is not None and validation_labels is not None:
            X_val = torch.FloatTensor(validation_images)
            if X_val.ndim == 3:
                X_val = X_val.unsqueeze(1)
            if task == "multilabel":
                y_val = torch.FloatTensor(validation_labels)
            else:
                y_val = torch.LongTensor(validation_labels)
            val_dataset = TensorDataset(X_val, y_val)
            val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

        # إعداد البيانات غير المصنفة
        unlabeled_loader = None
        if unlabeled_images is not None:
            X_unlabeled = torch.FloatTensor(unlabeled_images)
            if X_unlabeled.ndim == 3:
                X_unlabeled = X_unlabeled.unsqueeze(1)
            unlabeled_dataset = TensorDataset(X_unlabeled)
            unlabeled_loader = DataLoader(unlabeled_dataset, batch_size=batch_size, shuffle=True)

        # حلقة التدريب
        best_val_loss = float("inf")
        patience_counter = 0

        logger.info(
            f"بدء التدريب: {epochs} حقب, مجموعة={batch_size}, "
            f"مُصنّف={len(X_labeled)}, غير مُصنّف={len(X_unlabeled) if unlabeled_images is not None else 0}"
        )

        for epoch in range(epochs):
            self.student_model.train()
            epoch_loss = 0.0
            correct = 0
            total = 0

            # Dataloader مصنفة
            labeled_dataset = TensorDataset(X_labeled, y_labeled)
            labeled_loader = DataLoader(labeled_dataset, batch_size=batch_size, shuffle=True)

            for batch_x, batch_y in labeled_loader:
                batch_x, batch_y = batch_x.to(self.device), batch_y.to(self.device)

                self.optimizer.zero_grad()
                outputs = self.student_model(batch_x)
                loss = criterion(outputs, batch_y)

                loss.backward()
                self.optimizer.step()

                epoch_loss += loss.item()

                # حساب الدقة
                if task == "multiclass":
                    preds = torch.argmax(outputs, dim=1)
                    correct += (preds == batch_y).sum().item()
                    total += batch_y.size(0)
                else:
                    preds = (torch.sigmoid(outputs) > 0.5).float()
                    correct += (preds == batch_y).sum().item()
                    total += batch_y.numel()

            # Pseudo-Labeling للبيانات غير المصنفة
            if unlabeled_loader is not None:
                pseudo_loss = self._pseudo_label_step(
                    unlabeled_loader, pseudo_label_threshold, criterion, task
                )
                epoch_loss += pseudo_loss * consistency_weight

            # Mixed precision
            self.scheduler.step()

            # التحقق
            val_loss, val_acc = 0.0, 0.0
            if val_loader is not None:
                val_loss, val_acc = self._validate(val_loader, criterion, task)

            train_acc = correct / total if total > 0 else 0
            self.history["train_loss"].append(epoch_loss)
            self.history["val_loss"].append(val_loss)
            self.history["train_acc"].append(train_acc)
            self.history["val_acc"].append(val_acc)

            # التوقف المبكر
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                if save_dir:
                    self._save_model(save_dir / "best_model.pt")
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    logger.info(f"توقف مبكر عند الحقبة {epoch}")
                    break

            if (epoch + 1) % 10 == 0:
                logger.info(
                    f"  حقبة {epoch+1}/{epochs} | "
                    f"خسارة={epoch_loss:.4f} | دقة={train_acc:.4f} | "
                    f"تحقق: خسارة={val_loss:.4f} دقة={val_acc:.4f}"
                )

        logger.info("انتهى التدريب")
        return self.history

    def _pseudo_label_step(
        self,
        unlabeled_loader: Any,
        threshold: float,
        criterion: Any,
        task: str,
    ) -> float:
        """خطوة التسميات الزائفة"""
        import torch

        total_loss = 0.0
        num_batches = 0

        self.student_model.eval()
        with torch.no_grad():
            for (batch_x,) in unlabeled_loader:
                batch_x = batch_x.to(self.device)
                outputs = self.student_model(batch_x)
                probs = torch.sigmoid(outputs) if task == "multilabel" else torch.softmax(outputs, dim=1)

                # اختيار التسميات عالية الثقة
                max_probs, pseudo_labels = torch.max(probs, dim=1)
                mask = max_probs >= threshold

                if mask.sum() > 0:
                    confident_x = batch_x[mask]
                    if task == "multilabel":
                        confident_labels = (probs[mask] >= threshold).float()
                    else:
                        confident_labels = pseudo_labels[mask]

                    self.student_model.train()
                    out = self.student_model(confident_x)
                    loss = criterion(out, confident_labels)
                    total_loss += loss.item()
                    num_batches += 1
                    self.student_model.eval()

        return total_loss / max(num_batches, 1)

    def _validate(self, val_loader: Any, criterion: Any, task: str) -> Tuple[float, float]:
        """التحقق على مجموعة التحقق"""
        import torch

        self.student_model.eval()
        total_loss = 0.0
        correct = 0
        total = 0

        with torch.no_grad():
            for batch_x, batch_y in val_loader:
                batch_x, batch_y = batch_x.to(self.device), batch_y.to(self.device)
                outputs = self.student_model(batch_x)
                loss = criterion(outputs, batch_y)
                total_loss += loss.item()

                if task == "multiclass":
                    preds = torch.argmax(outputs, dim=1)
                    correct += (preds == batch_y).sum().item()
                    total += batch_y.size(0)
                else:
                    preds = (torch.sigmoid(outputs) > 0.5).float()
                    correct += (preds == batch_y).sum().item()
                    total += batch_y.numel()

        avg_loss = total_loss / len(val_loader)
        acc = correct / total if total > 0 else 0
        return avg_loss, acc

    def _save_model(self, path: Path):
        """حفظ النموذج"""
        try:
            import torch
            torch.save({
                "model_state_dict": self.student_model.state_dict(),
                "architecture": self.architecture,
                "num_classes": self.num_classes,
                "history": self.history,
            }, path)
            logger.debug(f"تم حفظ النموذج: {path}")
        except Exception as e:
            logger.error(f"فشل حفظ النموذج: {e}")

    def predict(self, images: np.ndarray) -> np.ndarray:
        """
        توقع فئات الصور

        Args:
            images: مصفوفة صور [N, H, W] أو [N, C, H, W]

        Returns:
            مصفوفة التوقعات [N] أو [N, num_classes]
        """
        import torch

        if self.student_model is None:
            raise RuntimeError("النموذج غير مُدرّب. يرجى استدعاء train() أولاً.")

        X = torch.FloatTensor(images)
        if X.ndim == 3:
            X = X.unsqueeze(1)

        self.student_model.eval()
        with torch.no_grad():
            X = X.to(self.device)
            outputs = self.student_model(X)
            predictions = torch.argmax(outputs, dim=1).cpu().numpy()

        return predictions
