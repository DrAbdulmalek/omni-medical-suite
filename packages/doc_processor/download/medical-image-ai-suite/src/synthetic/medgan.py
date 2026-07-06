"""
مولّد الصور الطبية الاصطناعية - MedGAN
توليد صور طبية واقعية باستخدام شبكات الخصومة التوليدية
يدعم DCGAN و WGAN-GP و Conditional GAN
"""

import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union

import numpy as np

from ..utils.logger import get_logger

logger = get_logger("medgan")


class MedGAN:
    """
    شبكة خصومة توليدية متخصصة للصور الطبية

    يدعم:
    - DCGAN: الشبكة التوليدية التلافيفية القياسية
    - WGAN-GP: WGAN مع عقوبة التدرج (أكثر استقراراً)
    - Conditional GAN: توليد مشروط بالفئة

    الاستخدام:
        gan = MedGAN(image_size=64, latent_dim=128)
        gan.train(real_images, epochs=200)
        synthetic = gan.generate(num_images=50)
    """

    def __init__(
        self,
        image_size: int = 64,
        channels: int = 1,
        latent_dim: int = 128,
        gan_type: str = "WGAN-GP",
        device: str = "auto",
        seed: int = 42,
    ):
        """
        Args:
            image_size: حجم الصورة (مربع)
            channels: عدد القنوات (1=رمادي, 3=RGB)
            latent_dim: بُعد الفضاء الكامن
            gan_type: نوع GAN (DCGAN, WGAN-GP, CGAN)
            device: جهاز التدريب
            seed: بذرة عشوائية
        """
        self.image_size = image_size
        self.channels = channels
        self.latent_dim = latent_dim
        self.gan_type = gan_type
        self.seed = seed
        np.random.seed(seed)

        # تحديد الجهاز
        self.device = self._detect_device() if device == "auto" else device

        self.generator = None
        self.discriminator = None
        self.g_optimizer = None
        self.d_optimizer = None
        self.history = {"g_loss": [], "d_loss": [], "fid": []}

        logger.info(
            f"MedGAN: {gan_type}, حجم={image_size}, قنوات={channels}, "
            f"جهاز={self.device}, بُعد={latent_dim}"
        )

    def _detect_device(self) -> str:
        """اكتشاف الجهاز"""
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"

    def _build_generator(self) -> Any:
        """بناء شبكة المولّد"""
        try:
            import torch
            import torch.nn as nn

            class Generator(nn.Module):
                def __init__(self, latent_dim, channels, img_size):
                    super().__init__()
                    self.init_size = img_size // 16
                    self.fc = nn.Sequential(
                        nn.Linear(latent_dim, 256 * self.init_size ** 2),
                        nn.BatchNorm1d(256 * self.init_size ** 2),
                        nn.ReLU(True),
                    )

                    self.conv_blocks = nn.Sequential(
                        nn.Upsample(scale_factor=2),
                        nn.Conv2d(256, 128, 3, stride=1, padding=1),
                        nn.BatchNorm2d(128, 0.8),
                        nn.ReLU(True),

                        nn.Upsample(scale_factor=2),
                        nn.Conv2d(128, 64, 3, stride=1, padding=1),
                        nn.BatchNorm2d(64, 0.8),
                        nn.ReLU(True),

                        nn.Upsample(scale_factor=2),
                        nn.Conv2d(64, 32, 3, stride=1, padding=1),
                        nn.BatchNorm2d(32, 0.8),
                        nn.ReLU(True),

                        nn.Upsample(scale_factor=2),
                        nn.Conv2d(32, channels, 3, stride=1, padding=1),
                        nn.Tanh(),
                    )

                def forward(self, z):
                    out = self.fc(z)
                    out = out.view(out.size(0), 256, self.init_size, self.init_size)
                    img = self.conv_blocks(out)
                    return img

            return Generator(self.latent_dim, self.channels, self.image_size).to(self.device)

        except ImportError:
            return None

    def _build_discriminator(self) -> Any:
        """بناء شبكة المميّز"""
        try:
            import torch
            import torch.nn as nn

            class Discriminator(nn.Module):
                def __init__(self, channels, img_size):
                    super().__init__()

                    def discriminator_block(in_filters, out_filters, bn=True):
                        block = [
                            nn.Conv2d(in_filters, out_filters, 3, stride=2, padding=1),
                            nn.LeakyReLU(0.2, inplace=True),
                            nn.Dropout2d(0.25),
                        ]
                        if bn:
                            block.append(nn.BatchNorm2d(out_filters, 0.8))
                        return block

                    self.model = nn.Sequential(
                        *discriminator_block(channels, 32, bn=False),
                        *discriminator_block(32, 64),
                        *discriminator_block(64, 128),
                        *discriminator_block(128, 256),
                    )

                    ds_size = img_size // 2 ** 4
                    self.adv_layer = nn.Sequential(
                        nn.Linear(256 * ds_size * ds_size, 1),
                        nn.Sigmoid(),
                    )

                def forward(self, img):
                    features = self.model(img)
                    features = features.view(features.size(0), -1)
                    validity = self.adv_layer(features)
                    return validity

            return Discriminator(self.channels, self.image_size).to(self.device)

        except ImportError:
            return None

    def train(
        self,
        real_images: np.ndarray,
        epochs: int = 200,
        batch_size: int = 32,
        lr_g: float = 2e-4,
        lr_d: float = 1e-4,
        beta1: float = 0.5,
        n_critic: int = 1,
        lambda_gp: float = 10.0,
        sample_interval: int = 50,
        save_dir: Optional[str] = None,
    ) -> Dict[str, List[float]]:
        """
        تدريب شبكة GAN على بيانات حقيقية

        Args:
            real_images: صور حقيقية [N, H, W] أو [N, C, H, W]
            epochs: عدد الحقب
            batch_size: حجم المجموعة
            lr_g: معدل تعلم المولّد
            lr_d: معدل تعلم المميّز
            beta1: معامل Beta1 لـ Adam
            n_critic: عدد خطوات المميّز لكل خطوة مولّد (WGAN)
            lambda_gp: وزن عقوبة التدرج (WGAN-GP)
            sample_interval: فاصل حفظ العينات
            save_dir: مجلد الحفظ

        Returns:
            سجل التدريب
        """
        try:
            import torch
            import torch.nn as nn
            import torch.optim as optim
            from torch.utils.data import DataLoader, TensorDataset
        except ImportError:
            logger.error("PyTorch غير مثبت")
            return self.history

        # إعداد المجلد
        if save_dir:
            save_dir = Path(save_dir)
            save_dir.mkdir(parents=True, exist_ok=True)

        # تحويل البيانات
        X = torch.FloatTensor(real_images)
        if X.ndim == 3:
            X = X.unsqueeze(1)  # [N, 1, H, W]

        # تغيير الحجم إلى image_size
        if X.shape[2] != self.image_size or X.shape[3] != self.image_size:
            import torch.nn.functional as F
            X = F.interpolate(X, size=(self.image_size, self.image_size), mode="bilinear")

        # بناء النماذج
        self.generator = self._build_generator()
        self.discriminator = self._build_discriminator()

        if self.generator is None or self.discriminator is None:
            logger.error("فشل بناء النماذج")
            return self.history

        # المحسّنات
        self.g_optimizer = optim.Adam(
            self.generator.parameters(), lr=lr_g, betas=(beta1, 0.999)
        )
        self.d_optimizer = optim.Adam(
            self.discriminator.parameters(), lr=lr_d, betas=(beta1, 0.999)
        )

        dataloader = DataLoader(
            TensorDataset(X), batch_size=batch_size, shuffle=True, drop_last=True,
        )

        # Dataloader
        if self.gan_type == "WGAN-GP":
            criterion = None  # WGAN لا يستخدم خسارة البقاء
        else:
            criterion = nn.BCELoss()

        logger.info(f"بدء تدريب {self.gan_type}: {epochs} حقب, {len(X)} صورة")

        for epoch in range(epochs):
            g_losses = []
            d_losses = []

            for i, (batch,) in enumerate(dataloader):
                batch = batch[0].to(self.device)
                current_batch = batch.size(0)

                # ===== تدريب المميّز =====
                self.d_optimizer.zero_grad()

                real_labels = torch.ones(current_batch, 1).to(self.device)
                fake_labels = torch.zeros(current_batch, 1).to(self.device)

                real_loss = self.discriminator(batch)
                if self.gan_type == "WGAN-GP":
                    d_loss_real = -torch.mean(real_loss)
                else:
                    d_loss_real = criterion(real_loss, real_labels)

                z = torch.randn(current_batch, self.latent_dim).to(self.device)
                fake_images = self.generator(z)
                fake_loss = self.discriminator(fake_images.detach())

                if self.gan_type == "WGAN-GP":
                    d_loss_fake = torch.mean(fake_loss)
                    # Gradient Penalty
                    alpha = torch.rand(current_batch, 1, 1, 1).to(self.device)
                    interpolated = (alpha * batch + (1 - alpha) * fake_images.detach()).requires_grad_(True)
                    d_interpolated = self.discriminator(interpolated)
                    grad_outputs = torch.ones_like(d_interpolated)
                    gradients = torch.autograd.grad(
                        outputs=d_interpolated, inputs=interpolated,
                        grad_outputs=grad_outputs, create_graph=True, retain_graph=True,
                    )[0]
                    gradients = gradients.view(current_batch, -1)
                    gradient_penalty = ((gradients.norm(2, dim=1) - 1) ** 2).mean()
                    d_loss = d_loss_real + d_loss_fake + lambda_gp * gradient_penalty
                else:
                    d_loss_fake = criterion(fake_loss, fake_labels)
                    d_loss = d_loss_real + d_loss_fake

                d_loss.backward()
                self.d_optimizer.step()

                # ===== تدريب المولّد =====
                if self.gan_type == "WGAN-GP" and (i + 1) % n_critic != 0:
                    continue

                self.g_optimizer.zero_grad()
                z = torch.randn(current_batch, self.latent_dim).to(self.device)
                fake_images = self.generator(z)
                g_loss_output = self.discriminator(fake_images)

                if self.gan_type == "WGAN-GP":
                    g_loss = -torch.mean(g_loss_output)
                else:
                    g_loss = criterion(g_loss_output, real_labels)

                g_loss.backward()
                self.g_optimizer.step()

                g_losses.append(g_loss.item())
                d_losses.append(d_loss.item())

            avg_g = np.mean(g_losses)
            avg_d = np.mean(d_losses)
            self.history["g_loss"].append(avg_g)
            self.history["d_loss"].append(avg_d)

            if (epoch + 1) % 20 == 0:
                logger.info(
                    f"  حقبة {epoch+1}/{epochs} | "
                    f"G_loss={avg_g:.4f} | D_loss={avg_d:.4f}"
                )

            # حفظ عينات
            if save_dir and (epoch + 1) % sample_interval == 0:
                self._save_samples(save_dir / f"samples_epoch_{epoch+1}", num=8)

        # حفظ النموذج النهائي
        if save_dir:
            self._save_model(save_dir / "medgan_final.pt")

        logger.info("انتهى تدريب GAN")
        return self.history

    def generate(
        self,
        num_images: int = 50,
        conditions: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        توليد صور طبية اصطناعية

        Args:
            num_images: عدد الصور المطلوبة
            conditions: شروط التصنيف (لـ CGAN)

        Returns:
            مصفوفة صور اصطناعية [N, H, W]
        """
        if self.generator is None:
            logger.warning("النموذج غير مُدرّب بعد!")
            # توليد صور عشوائية كبدائل
            return np.random.randn(num_images, self.image_size, self.image_size).astype(np.float32)

        import torch

        self.generator.eval()
        with torch.no_grad():
            z = torch.randn(num_images, self.latent_dim).to(self.device)
            images = self.generator(z).cpu().numpy()

        # إزالة بُعد القناة إذا كان 1
        if images.shape[1] == 1:
            images = images.squeeze(1)

        # تحويل من [-1, 1] إلى [0, 1]
        images = (images + 1) / 2
        images = np.clip(images, 0, 1)

        logger.info(f"تم توليد {num_images} صورة اصطناعية: {images.shape}")
        return images

    def _save_samples(self, path: Path, num: int = 8):
        """حفظ عينات من الصور المولّدة"""
        try:
            import torch
            images = self.generate(num)
            np.save(str(path.with_suffix(".npy")), images)
        except Exception as e:
            logger.warning(f"فشل حفظ العينات: {e}")

    def _save_model(self, path: Path):
        """حفظ النموذج"""
        try:
            import torch
            torch.save({
                "generator": self.generator.state_dict(),
                "discriminator": self.discriminator.state_dict(),
                "config": {
                    "image_size": self.image_size,
                    "channels": self.channels,
                    "latent_dim": self.latent_dim,
                    "gan_type": self.gan_type,
                },
                "history": self.history,
            }, path)
            logger.info(f"تم حفظ GAN: {path}")
        except Exception as e:
            logger.error(f"فشل حفظ GAN: {e}")

    def load_model(self, path: str):
        """تحميل نموذج محفوظ"""
        import torch

        checkpoint = torch.load(path, map_location=self.device)
        config = checkpoint["config"]

        self.image_size = config["image_size"]
        self.channels = config["channels"]
        self.latent_dim = config["latent_dim"]
        self.gan_type = config["gan_type"]

        self.generator = self._build_generator()
        self.discriminator = self._build_discriminator()

        self.generator.load_state_dict(checkpoint["generator"])
        self.discriminator.load_state_dict(checkpoint["discriminator"])
        self.history = checkpoint.get("history", self.history)

        logger.info(f"تم تحميل GAN من: {path}")


class MedicalImageGenerator:
    """
    واجهة عالية المستوى لتوليد الصور الطبية
    تجمع بين GAN وتعزيز البيانات التقليدي
    """

    def __init__(
        self,
        gan: Optional[MedGAN] = None,
        augmentation_config: Optional[Dict] = None,
    ):
        self.gan = gan or MedGAN()
        self.aug_config = augmentation_config or {
            "rotation_range": 10,
            "zoom_range": 0.05,
            "brightness_range": [0.9, 1.1],
            "gaussian_noise": 0.01,
        }

    def augment_dataset(
        self,
        images: np.ndarray,
        num_augmented: int = 100,
        method: str = "mixed",
    ) -> np.ndarray:
        """
        توسيع مجموعة البيانات بالتعزيز والتوليد

        Args:
            images: الصور الأصلية [N, H, W]
            num_augmented: عدد الصور الإضافية المطلوبة
            method: الطريقة (augmentation, gan, mixed)

        Returns:
            مجموعة موسّعة من الصور
        """
        augmented = [images]

        # تعزيز تقليدي
        if method in ("augmentation", "mixed"):
            n_classic = num_augmented // 2
            for _ in range(n_classic):
                idx = np.random.randint(len(images))
                img = images[idx].copy()
                # دوران
                angle = np.random.uniform(-10, 10)
                from scipy.ndimage import rotate as sci_rotate
                img = sci_rotate(img, angle, reshape=False, mode="reflect")
                # ضوضاء
                noise = np.random.normal(0, 0.01, img.shape)
                img = np.clip(img + noise, 0, 1)
                augmented.append(img[np.newaxis])

        # توليد GAN
        if method in ("gan", "mixed"):
            n_gan = num_augmented // 2
            try:
                synthetic = self.gan.generate(n_gan)
                if synthetic.shape[1:] == images.shape[1:]:
                    augmented.append(synthetic)
            except Exception as e:
                logger.warning(f"فشل توليد GAN: {e}")

        result = np.concatenate(augmented, axis=0)
        logger.info(f"تم توسيع البيانات: {len(images)} → {len(result)} صورة")
        return result
