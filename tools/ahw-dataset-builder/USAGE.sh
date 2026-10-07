# 1. التقطيع على دفعات (PDF كبير)
python batch_segment.py scan.pdf --sample S001 --pages-per-batch 5

# 2. دمج الدفعات
python merge_batches.py --sample-dir output/S001

# 3. التصحيح (خادم ويب)
python server.py --sample S001
# افتح http://127.0.0.1:5000

# 4. تصدير corrections.xlsx → ضعه في output/S001/

# 5. التدريب (واجهة ويب تفاعلية)
python train_server.py
# افتح http://127.0.0.1:5001

# 6. أو التدريب من Docker
docker-compose up training-ui
