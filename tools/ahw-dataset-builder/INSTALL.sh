# 1. أنشئ المجلد
mkdir ahw-dataset-builder
cd ahw-dataset-builder
mkdir templates

# 2. انسخ الملفات الثمانية في أماكنها

# 3. ثبّت
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 4. قطّع
python segment.py "618002dc-....pdf" --sample S001 --pages 4 7 8 10 12 13 15

# 5. صحّح
python server.py --sample S001
# افتح http://127.0.0.1:5000

# 6. صدّر (من المتصفح) → corrections.xlsx

# 7. درّب
python train_trocr.py --data output/S001 --epochs 20 --batch 8
