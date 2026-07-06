import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import fs from 'fs';
import path from 'path';
import sharp from 'sharp';
import { smartCrop, calculateBlurScore, applyCrop, removeShadow } from '@/lib/image-processing';
import { extractFeatures } from '@/lib/trainable-algorithm';

const UPLOADS_DIR = '/home/z/my-project/uploads';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const image = await db.processedImage.findUnique({ where: { id } });

    if (!image) {
      return NextResponse.json({ error: 'الصورة غير موجودة' }, { status: 404 });
    }

    const filePath = path.join(UPLOADS_DIR, image.fileName);
    if (!fs.existsSync(filePath)) {
      return NextResponse.json({ error: 'الملف غير موجود على الخادم' }, { status: 404 });
    }

    const buffer = fs.readFileSync(filePath);
    const body = await request.json();
    const { action, cropLeft, cropTop, cropRight, cropBottom, deskewAngle, grayThreshold } = body;

    let resultBuffer = buffer;
    const ops: string[] = [...JSON.parse(image.operations || '[]')];

    if (action === 'smart_crop') {
      const cropResult = await smartCrop(buffer, grayThreshold || 200);
      resultBuffer = cropResult.cropped;
      ops.push('قص ذكي تلقائي');

      const blurAfter = await calculateBlurScore(resultBuffer);

      const updated = await db.processedImage.update({
        where: { id },
        data: {
          cropLeft: cropResult.cropLeft,
          cropTop: cropResult.cropTop,
          cropRight: cropResult.cropRight,
          cropBottom: cropResult.cropBottom,
          blurAfter,
          status: 'processed',
          operations: JSON.stringify(ops),
        }
      });

      fs.writeFileSync(filePath, resultBuffer);

      await db.processingLog.create({
        data: {
          imageId: id,
          imageName: image.originalName,
          action: 'قص ذكي',
          details: `L=${cropResult.cropLeft} T=${cropResult.cropTop} R=${cropResult.cropRight} B=${cropResult.cropBottom}`,
          quality: Math.round(blurAfter),
        }
      });

      // Create training record with extracted features
      try {
        const features = await extractFeatures(buffer);
        await db.trainingRecord.create({
          data: {
            imageName: image.originalName,
            features: JSON.stringify(features),
            initialParams: JSON.stringify({ crop: [image.cropLeft, image.cropTop, image.cropRight, image.cropBottom] }),
            finalParams: JSON.stringify({
              pageThreshold: grayThreshold || 200,
              grayThreshold: grayThreshold || 200,
              padding: 5,
            }),
            operations: JSON.stringify(ops),
            quality: JSON.stringify({ blur_before: image.blurBefore, blur_after: blurAfter }),
            confidence: 0.9,
          }
        });
      } catch {
        // Non-critical: training record creation failed
      }

      return NextResponse.json({ success: true, image: updated });
    }

    if (action === 'remove_gray') {
      const cropResult = await smartCrop(buffer, grayThreshold || 230);
      resultBuffer = cropResult.cropped;
      ops.push('إزالة رمادي');

      const blurAfter = await calculateBlurScore(resultBuffer);

      const updated = await db.processedImage.update({
        where: { id },
        data: {
          cropLeft: cropResult.cropLeft,
          cropTop: cropResult.cropTop,
          cropRight: cropResult.cropRight,
          cropBottom: cropResult.cropBottom,
          blurAfter,
          operations: JSON.stringify(ops),
        }
      });

      fs.writeFileSync(filePath, resultBuffer);

      await db.processingLog.create({
        data: {
          imageId: id,
          imageName: image.originalName,
          action: 'إزالة رمادي',
          details: `L=${cropResult.cropLeft} T=${cropResult.cropTop} R=${cropResult.cropRight} B=${cropResult.cropBottom}`,
          quality: Math.round(blurAfter),
        }
      });

      // Create training record with extracted features
      try {
        const features = await extractFeatures(buffer);
        await db.trainingRecord.create({
          data: {
            imageName: image.originalName,
            features: JSON.stringify(features),
            initialParams: JSON.stringify({ crop: [image.cropLeft, image.cropTop, image.cropRight, image.cropBottom] }),
            finalParams: JSON.stringify({
              pageThreshold: 200,
              grayThreshold: grayThreshold || 230,
              padding: 5,
            }),
            operations: JSON.stringify(ops),
            quality: JSON.stringify({ blur_before: image.blurBefore, blur_after: blurAfter }),
            confidence: 0.9,
          }
        });
      } catch {
        // Non-critical: training record creation failed
      }

      return NextResponse.json({ success: true, image: updated });
    }

    if (action === 'detect_skew') {
      const angle = deskewAngle || 0;
      ops.push(`ميلان تلقائي: ${angle}°`);

      const updated = await db.processedImage.update({
        where: { id },
        data: {
          deskewAngle: angle,
          operations: JSON.stringify(ops),
        }
      });

      await db.processingLog.create({
        data: {
          imageId: id,
          imageName: image.originalName,
          action: 'كشف ميلان',
          details: `ميلان مكتشف: ${angle}°`,
          quality: Math.round(image.blurBefore),
        }
      });

      return NextResponse.json({ success: true, image: updated, detectedAngle: angle });
    }

    if (action === 'detect_skew_auto') {
      // Projection profile deskew: test angles -10° to +10° in 0.5° increments
      const { data, info } = await sharp(buffer)
        .resize(600, null, { withoutEnlargement: true })
        .greyscale()
        .threshold(128)
        .raw()
        .toBuffer({ resolveWithObject: true });

      const w = info.width;
      const h = info.height;

      let bestAngle = 0;
      let bestScore = -1;

      for (let angle = -10; angle <= 10; angle += 0.5) {
        const rad = (angle * Math.PI) / 180;
        const projection = new Float64Array(w);

        for (let y = 0; y < h; y++) {
          const shiftedX = Math.round(y * Math.tan(rad));
          for (let x = 0; x < w; x++) {
            const sx = x + shiftedX;
            if (sx >= 0 && sx < w) {
              projection[sx] += data[y * w + x];
            }
          }
        }

        let sum = 0;
        let sumSq = 0;
        let count = 0;
        for (let i = 0; i < w; i++) {
          if (projection[i] > 0) {
            sum += projection[i];
            sumSq += projection[i] * projection[i];
            count++;
          }
        }

        if (count > 0) {
          const mean = sum / count;
          const variance = sumSq / count - mean * mean;
          if (variance > bestScore) {
            bestScore = variance;
            bestAngle = angle;
          }
        }
      }

      ops.push(`ميلان تلقائي (إسقاط): ${bestAngle}°`);

      // Apply rotation
      resultBuffer = await sharp(buffer)
        .rotate(bestAngle, { background: { r: 255, g: 255, b: 255, alpha: 1 } })
        .png()
        .toBuffer();

      const blurAfter = await calculateBlurScore(resultBuffer);

      const updated = await db.processedImage.update({
        where: { id },
        data: {
          deskewAngle: bestAngle,
          blurAfter,
          status: 'processed',
          operations: JSON.stringify(ops),
        }
      });

      fs.writeFileSync(filePath, resultBuffer);

      await db.processingLog.create({
        data: {
          imageId: id,
          imageName: image.originalName,
          action: 'كشف ميلان تلقائي (إسقاط)',
          details: `ميلان مكتشف: ${bestAngle}° | طريقة: Projection Profile`,
          quality: Math.round(blurAfter),
        }
      });

      return NextResponse.json({ success: true, image: updated, detectedAngle: bestAngle });
    }

    if (action === 'auto_crop_smart') {
      // Phase 1: Basic threshold scan
      const { data: phase1Data, info: phase1Info } = await sharp(buffer)
        .greyscale()
        .raw()
        .toBuffer({ resolveWithObject: true });

      const w1 = phase1Info.width;
      const h1 = phase1Info.height;
      const threshold1 = 240;
      const margin1 = 5;

      let top = 0;
      outer_top: for (let y = 0; y < h1; y++) {
        for (let x = 0; x < w1; x++) {
          if (phase1Data[y * w1 + x] < threshold1) {
            top = Math.max(0, y - margin1);
            break outer_top;
          }
        }
      }

      let bottom = 0;
      outer_bottom: for (let y = h1 - 1; y >= 0; y--) {
        for (let x = 0; x < w1; x++) {
          if (phase1Data[y * w1 + x] < threshold1) {
            bottom = Math.max(0, (h1 - 1 - y) - margin1);
            break outer_bottom;
          }
        }
      }

      let left = 0;
      outer_left: for (let x = 0; x < w1; x++) {
        for (let y = top; y < h1 - bottom; y++) {
          if (phase1Data[y * w1 + x] < threshold1) {
            left = Math.max(0, x - margin1);
            break outer_left;
          }
        }
      }

      let right = 0;
      outer_right: for (let x = w1 - 1; x >= 0; x--) {
        for (let y = top; y < h1 - bottom; y++) {
          if (phase1Data[y * w1 + x] < threshold1) {
            right = Math.max(0, (w1 - 1 - x) - margin1);
            break outer_right;
          }
        }
      }

      // Phase 2: Smart refinement within the trimmed area
      const startX = Math.round(w1 * left / (left + (w1 - right - left)));
      const startY = top;
      const endX = w1 - right;
      const endY = h1 - bottom;

      const contentThreshold = 220;
      const contentMargin = 3;

      let contentTop = startY;
      ct: for (let y = startY; y < endY; y++) {
        for (let x = left; x < endX; x++) {
          if (phase1Data[y * w1 + x] < contentThreshold) {
            contentTop = Math.max(startY, y - contentMargin);
            break ct;
          }
        }
      }

      let contentBottom = h1 - endY;
      cb: for (let y = endY - 1; y >= startY; y--) {
        for (let x = left; x < endX; x++) {
          if (phase1Data[y * w1 + x] < contentThreshold) {
            contentBottom = Math.max(0, (h1 - 1 - y) - contentMargin);
            break cb;
          }
        }
      }

      let contentLeft = left;
      cl: for (let x = left; x < endX; x++) {
        for (let y = contentTop; y < h1 - contentBottom; y++) {
          if (phase1Data[y * w1 + x] < contentThreshold) {
            contentLeft = Math.max(0, x - contentMargin);
            break cl;
          }
        }
      }

      let contentRight = w1 - endX;
      cr: for (let x = endX - 1; x >= left; x--) {
        for (let y = contentTop; y < h1 - contentBottom; y++) {
          if (phase1Data[y * w1 + x] < contentThreshold) {
            contentRight = Math.max(0, (w1 - 1 - x) - contentMargin);
            break cr;
          }
        }
      }

      resultBuffer = await sharp(buffer)
        .extract({
          left: contentLeft,
          top: contentTop,
          width: w1 - contentLeft - contentRight,
          height: h1 - contentTop - contentBottom,
        })
        .png()
        .toBuffer();

      ops.push('قص ذكي (مرحلتين)');

      const blurAfter = await calculateBlurScore(resultBuffer);
      const meta = await sharp(resultBuffer).metadata();

      const updated = await db.processedImage.update({
        where: { id },
        data: {
          cropLeft: contentLeft,
          cropTop: contentTop,
          cropRight: contentRight,
          cropBottom: contentBottom,
          blurAfter,
          status: 'processed',
          width: meta.width || image.width,
          height: meta.height || image.height,
          operations: JSON.stringify(ops),
        }
      });

      fs.writeFileSync(filePath, resultBuffer);

      await db.processingLog.create({
        data: {
          imageId: id,
          imageName: image.originalName,
          action: 'قص ذكي (مرحلتين)',
          details: `L=${contentLeft} T=${contentTop} R=${contentRight} B=${contentBottom}`,
          quality: Math.round(blurAfter),
        }
      });

      return NextResponse.json({ success: true, image: updated });
    }

    if (action === 'manual_crop') {
      resultBuffer = await applyCrop(buffer, cropLeft || 0, cropTop || 0, cropRight || 0, cropBottom || 0);
      ops.push('قص يدوي');

      const blurAfter = await calculateBlurScore(resultBuffer);
      const meta = await sharp(resultBuffer).metadata();

      const updated = await db.processedImage.update({
        where: { id },
        data: {
          cropLeft: cropLeft || 0,
          cropTop: cropTop || 0,
          cropRight: cropRight || 0,
          cropBottom: cropBottom || 0,
          blurAfter,
          status: 'processed',
          width: meta.width || image.width,
          height: meta.height || image.height,
          operations: JSON.stringify(ops),
        }
      });

      fs.writeFileSync(filePath, resultBuffer);

      await db.processingLog.create({
        data: {
          imageId: id,
          imageName: image.originalName,
          action: 'قص يدوي',
          details: `L=${cropLeft} T=${cropTop} R=${cropRight} B=${cropBottom}`,
          quality: Math.round(blurAfter),
        }
      });

      // Create training record with full features
      try {
        const features = await extractFeatures(buffer);
        await db.trainingRecord.create({
          data: {
            imageName: image.originalName,
            features: JSON.stringify(features),
            initialParams: JSON.stringify({ crop: [image.cropLeft, image.cropTop, image.cropRight, image.cropBottom] }),
            finalParams: JSON.stringify({ crop: [cropLeft, cropTop, cropRight, cropBottom] }),
            operations: JSON.stringify(ops),
            quality: JSON.stringify({ blur_before: image.blurBefore, blur_after: blurAfter }),
            confidence: 1.0,
          }
        });
      } catch {
        // Non-critical
      }

      return NextResponse.json({ success: true, image: updated });
    }

    if (action === 'save') {
      const blurAfter = await calculateBlurScore(buffer);
      const updated = await db.processedImage.update({
        where: { id },
        data: {
          blurAfter,
          status: 'processed',
        }
      });

      await db.processingLog.create({
        data: {
          imageId: id,
          imageName: image.originalName,
          action: 'حفظ',
          details: `حفظ ${image.originalName} | جودة: ${Math.round(blurAfter)}`,
          quality: Math.round(blurAfter),
        }
      });

      return NextResponse.json({ success: true, image: updated });
    }

    if (action === 'remove_shadow') {
      resultBuffer = await removeShadow(buffer);
      ops.push('إزالة الظلال');

      const blurAfter = await calculateBlurScore(resultBuffer);

      const updated = await db.processedImage.update({
        where: { id },
        data: {
          blurAfter,
          shadowRemoved: true,
          status: 'processed',
          operations: JSON.stringify(ops),
        }
      });

      fs.writeFileSync(filePath, resultBuffer);

      await db.processingLog.create({
        data: {
          imageId: id,
          imageName: image.originalName,
          action: 'إزالة الظلال',
          details: `تطبيع الإضاءة + زيادة سطوع 5% + حدة خفيفة`,
          quality: Math.round(blurAfter),
        }
      });

      return NextResponse.json({ success: true, image: updated });
    }

    if (action === 'skip') {
      const updated = await db.processedImage.update({
        where: { id },
        data: { status: 'skipped' }
      });

      await db.processingLog.create({
        data: {
          imageId: id,
          imageName: image.originalName,
          action: 'تخطي',
          details: `تخطي ${image.originalName}`,
          quality: 0,
        }
      });

      return NextResponse.json({ success: true, image: updated });
    }

    return NextResponse.json({ error: 'إجراء غير معروف' }, { status: 400 });
  } catch (error) {
    console.error('Process error:', error);
    return NextResponse.json({ error: 'حدث خطأ أثناء المعالجة' }, { status: 500 });
  }
}
