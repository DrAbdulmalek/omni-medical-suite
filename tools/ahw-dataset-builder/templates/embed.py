"""يولّد HTML مستقل (بدون Flask) عند عدم تشغيل السيرفر."""
import json

def render_viewer(sample_id, crops):
    data_json = json.dumps(crops, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>تصحيح — {sample_id}</title>
<style>
body {{ font-family: Tahoma, sans-serif; background: #f5f5f5;
       margin: 0; padding: 20px; }}
h1 {{ color: #333; }}
.progress {{ position: sticky; top: 0; background: #fff;
    padding: 15px; border-bottom: 2px solid #007bff; z-index: 100;
    display: flex; gap: 20px; align-items: center; }}
.progress-bar {{ flex: 1; height: 24px; background: #eee;
    border-radius: 12px; overflow: hidden; }}
.progress-fill {{ height: 100%; background: #28a745;
    transition: width 0.3s; width: 0%; }}
.card {{ background: #fff; border: 1px solid #ddd; border-radius: 8px;
    padding: 12px; margin: 10px 0; display: flex; gap: 15px;
    align-items: center; }}
.card.done {{ border-color: #28a745; background: #f0fff4; }}
.crop {{ flex-shrink: 0; padding: 8px; background: #fafafa;
    border: 1px solid #e0e0e0; border-radius: 4px; min-width: 220px;
    text-align: center; }}
.crop img {{ max-width: 210px; max-height: 90px; }}
.info {{ flex: 1; }}
input[type=text] {{ width: 100%; padding: 12px; font-size: 20px;
    border: 2px solid #ccc; border-radius: 6px; direction: rtl; }}
input.done {{ border-color: #28a745; background: #f0fff4; }}
.actions {{ display: flex; gap: 10px; margin-top: 20px;
    position: sticky; bottom: 20px; background: #fff; padding: 15px;
    border-radius: 8px; box-shadow: 0 -2px 10px rgba(0,0,0,0.1); }}
button {{ padding: 12px 20px; border: none; border-radius: 6px;
    cursor: pointer; background: #007bff; color: #fff; }}
</style>
</head>
<body>
<h1>تصحيح — {sample_id}</h1>
<p>⚠️ وضع مستقل (بدون خادم). للحفظ الدائم شغّل: <code>python server.py</code></p>
<div class="progress">
    <div class="progress-bar"><div class="progress-fill" id="pbar"></div></div>
    <span id="pcount">0 / {len(crops)}</span>
</div>
<div id="cards"></div>
<div class="actions">
    <button onclick="exportCSV()">📥 CSV</button>
</div>
<script>
const data = {data_json};
const STORE_KEY = 'wh-{sample_id}';
const saved = JSON.parse(localStorage.getItem(STORE_KEY) || '{{}}');
data.forEach(d => {{ if (saved[d.word_id]) d.text = saved[d.word_id]; }});
const container = document.getElementById('cards');
data.forEach((d, i) => {{
    const card = document.createElement('div');
    card.className = 'card' + (d.text ? ' done' : '');
    card.innerHTML = `
        <div class="crop"><img src="data:image/png;base64,${{d.image_b64}}"></div>
        <div class="info"><small>${{d.word_id}}</small>
        <input type="text" value="${{d.text}}" placeholder="اكتب..."
               oninput="onEdit(${{i}}, this.value, this)"></div>`;
    container.appendChild(card);
}});
function onEdit(idx, v, inp) {{
    data[idx].text = v;
    inp.classList.toggle('done', !!v);
    inp.closest('.card').classList.toggle('done', !!v);
    const obj = {{}};
    data.forEach(d => {{ if (d.text) obj[d.word_id] = d.text; }});
    localStorage.setItem(STORE_KEY, JSON.stringify(obj));
    updateProgress();
}}
function updateProgress() {{
    const done = data.filter(d => d.text.trim()).length;
    document.getElementById('pcount').textContent = `${{done}} / ${{data.length}}`;
    document.getElementById('pbar').style.width = `${{(done/data.length)*100}}%`;
}}
function exportCSV() {{
    const h = ['word_id','page','column','line_idx','word_idx','text','status'];
    const rows = [h.join(',')];
    data.forEach(d => {{
        const t = (d.text||'').replace(/"/g,'""');
        rows.push([d.word_id,d.page,d.column,d.line_idx,d.word_idx,
                   `"${{t}}"`, d.text?'USER_CORRECTED':'RAW'].join(','));
    }});
    const blob = new Blob(['\\ufeff'+rows.join('\\n')], {{type:'text/csv;charset=utf-8'}});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'corrections_{sample_id}.csv';
    a.click();
}}
updateProgress();
</script>
</body>
</html>"""
