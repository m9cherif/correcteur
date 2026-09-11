#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ide.py — بيئة تحرير وتصحيح للتلميذ (المكتبة القياسية فقط)
==========================================================
تعمل على ويندوز و Termux بلا أيّ تثبيت: python ide.py ثم افتح المتصفّح.

    python ide.py
    python ide.py -s solution.py -t tests.json -e enonce.txt
    python ide.py -s solution.py --python "C:\\Python312\\python.exe" --lang fr
    python ide.py --port 8080 --essais ./essais

الجديد في هذه النسخة:
  • ترجمة حقيقية بـ python.exe (py_compile) عند كل تحليل → أخطاء نسخة بايثون
    المستهدَفة و SyntaxWarning تظهر مثل بقيّة الملاحظات
  • تلوين الصياغة (كلمات مفتاحية، نصوص، تعليقات، أرقام، دوال)
  • علامات ❌/⚠️ في هامش الأسطر + قفز إلى السطر بالنقر
  • تحليل تلقائي أثناء الكتابة (مؤجَّل 700 ملّي)
  • اختصارات: Ctrl+↵ تحليل · F5 تنفيذ · Ctrl+S حفظ · Ctrl+/ تعليق ·
    Tab / Shift+Tab إزاحة الكتلة · إغلاق تلقائي للأقواس والعلامات
  • اختيار لغة الشرح (ar/fr/en) ومظهر فاتح/داكن وحجم الخطّ
  • تنزيل الملف المشروح، فتح ملف من الجهاز، تنسيق سريع
  • سجلّ المحاولات مع النقاط واستعادة أيّ محاولة سابقة
  • شريط حالة: السطر/العمود، عدد الأسطر، نسخة المفسّر، زمن التنفيذ
"""

import argparse
import datetime
import difflib
import glob
import json
import os
import re
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import langues
from langues import U
import analyseur
from analyseur import (analyser_source, calculer_note, bloc_note, annoter,
                       detecter_python, version_python)
import correcteur
import interpreteurs as itp

CFG = {"solution": None, "tests": None, "enonce": "", "essais": "essais",
       "python": detecter_python(), "vu_solution": False}

PAGE = r"""<!DOCTYPE html><html lang="__LG__" dir="__DIR__"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITRE__</title><style>
:root{--bg:#0e1116;--pan:#161b22;--bd:#2a3442;--tx:#e6edf3;--mut:#8b98a8;--ok:#3fb950;
 --err:#f85149;--warn:#d29922;--acc:#58a6ff;--kw:#ff7b72;--str:#a5d6ff;--com:#8b949e;
 --num:#79c0ff;--fn:#d2a8ff;--edit:#0d1117}
body.clair{--bg:#f6f8fa;--pan:#fff;--bd:#d0d7de;--tx:#1f2328;--mut:#6a737d;--edit:#fff;
 --kw:#cf222e;--str:#0a3069;--com:#6e7781;--num:#0550ae;--fn:#8250df}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font-family:system-ui,"Segoe UI",sans-serif}
header{display:flex;gap:6px;align-items:center;padding:7px 10px;background:var(--pan);
 border-bottom:1px solid var(--bd);flex-wrap:wrap}
h1{font-size:14px;margin:0 6px 0 0}
button,select,input{background:#21262d33;color:var(--tx);border:1px solid var(--bd);
 border-radius:6px;padding:6px 10px;font-size:13px;cursor:pointer}
button:hover{border-color:var(--acc)}
button.p{background:var(--acc);color:#04121f;border:0;font-weight:600}
#badge{margin-inline-start:auto;font-weight:700;font-size:15px}
main{display:flex;gap:8px;padding:8px;height:calc(100vh - 92px)}
@media(max-width:860px){main{flex-direction:column;height:auto}}
.col{flex:1;min-width:0;display:flex;flex-direction:column}
.wrap{position:relative;display:flex;background:var(--edit);border:1px solid var(--bd);
 border-radius:8px;overflow:hidden;flex:1;min-height:320px;direction:ltr}
#gut{padding:10px 6px;background:#0000001a;color:var(--mut);text-align:right;
 user-select:none;min-width:52px;overflow:hidden;white-space:pre}
#gut b{color:var(--err)} #gut i{color:var(--warn);font-style:normal}
.zone{position:relative;flex:1;overflow:hidden}
#hl,#code{margin:0;padding:10px;border:0;white-space:pre;overflow:auto;
 width:100%;height:100%;tab-size:4}
#hl{position:absolute;inset:0;pointer-events:none;color:var(--tx)}
#code{position:absolute;inset:0;background:transparent;color:transparent;caret-color:var(--acc);
 resize:none;outline:0}
#gut,#hl,#code{font:var(--fs,13px)/1.55 ui-monospace,Consolas,"Courier New",monospace}
.k{color:var(--kw)}.s{color:var(--str)}.c{color:var(--com);font-style:italic}
.n{color:var(--num)}.f{color:var(--fn)}
.pan{background:var(--pan);border:1px solid var(--bd);border-radius:8px;padding:10px;
 overflow:auto;flex:1;min-height:220px}
.tabs{display:flex;gap:5px;margin-bottom:7px;flex-wrap:wrap}
.tab{padding:5px 9px;border-radius:6px;background:#21262d33;border:1px solid var(--bd);
 cursor:pointer;font-size:12px}
.tab.on{background:var(--acc);color:#04121f;font-weight:600;border-color:var(--acc)}
.it{border-inline-start:3px solid var(--warn);background:#8b949e1a;padding:8px 10px;
 border-radius:6px;margin-bottom:7px;font-size:13px;line-height:1.65}
.it.e{border-color:var(--err)}.it.g{border-color:var(--ok)}
.ln{color:var(--acc);cursor:pointer;text-decoration:underline}
pre{white-space:pre-wrap;font:12px/1.6 ui-monospace,monospace;margin:0}
table{width:100%;border-collapse:collapse;font-size:12px}
td,th{border-bottom:1px solid var(--bd);padding:5px;text-align:start}
.hide{display:none}.mut{color:var(--mut);font-size:12px}
footer{display:flex;gap:14px;padding:5px 12px;background:var(--pan);
 border-top:1px solid var(--bd);font-size:12px;color:var(--mut);flex-wrap:wrap}
code{background:#8b949e26;padding:1px 4px;border-radius:4px}
</style></head><body>
<header>
 <h1>🐍 <span id="t-app"></span></h1>
 <button class="p" onclick="act('analyser')" id="b1"></button>
 <button onclick="act('executer')" id="b2"></button>
 <button onclick="act('corriger')" id="b3"></button>
 <button onclick="voirSolution()" id="b4"></button>
 <button onclick="telecharger()" id="b5"></button>
 <button onclick="sauver()" id="b6"></button>
 <button onclick="formater()" id="b8"></button>
 <label class="mut"><input type="file" id="fich" accept=".py" hidden
   onchange="ouvrir(event)"><button onclick="fich.click()" id="b7"></button></label>
 <input type="text" id="stdin" size="14">
 <select id="py" onchange="chPy()" title="python.exe"></select>
 <input type="text" id="pypath" size="16" placeholder="python.exe">
 <button onclick="chPyManuel()">✔</button>
 <button onclick="scan(1)" id="b9">⟳</button>
 <select id="lang" onchange="chLang()">__OPTLANG__</select>
 <button onclick="theme()">🌗</button>
 <button onclick="zoom(1)">A+</button><button onclick="zoom(-1)">A−</button>
 <span id="badge">— / 20</span>
</header>
<main>
 <div class="col"><div class="wrap"><div id="gut">1</div>
   <div class="zone"><pre id="hl"></pre><textarea id="code" spellcheck="false"
     wrap="off"></textarea></div></div></div>
 <div class="col"><div class="tabs" id="tabs"></div>
  <div class="pan">
   <div id="p-err"></div>
   <div id="p-run" class="hide"><pre id="out"></pre></div>
   <div id="p-tst" class="hide"></div>
   <div id="p-bar" class="hide">—</div>
   <div id="p-sol" class="hide"></div>
   <div id="p-enn" class="hide"><pre id="enn"></pre></div>
   <div id="p-his" class="hide"></div>
   <div id="p-cmp" class="hide"></div>
  </div></div>
</main>
<footer><span id="st-pos">1:1</span><span id="st-n"></span>
 <span id="st-py"></span><span id="st-ms"></span><span id="st-msg"></span>
 <span id="aide" style="margin-inline-start:auto"></span></footer>
<script>
const T=__T__, PYV=__PYV__, ENONCE=__ENONCE__, ONGLETS=__ONGLETS__;
const $=s=>document.querySelector(s), code=$('#code');
function i18n(){["t-app","aide"].forEach(i=>{});
 $('#t-app').textContent=T.titre_app; $('#b1').textContent=T.bt_analyser+' (Ctrl+↵)';
 $('#b2').textContent='▶ '+T.bt_executer; $('#b3').textContent='✔ '+T.bt_corriger;
 $('#b4').textContent='📘 '+T.bt_solution; $('#b5').textContent='⬇ '+T.bt_telecharger;
 $('#b6').textContent='💾 '+T.bt_enregistrer; $('#b7').textContent='📂 '+T.bt_ouvrir;
 $('#b8').textContent='✨ '+T.bt_formater; $('#stdin').placeholder=T.ph_stdin;
 $('#aide').textContent=T.aide; $('#st-py').textContent='🐍 '+PYV;
 $('#b9').title=T.bt_scan; $('#pypath').placeholder=T.bt_parcourir;
 $('#p-err').textContent=T.msg_analyser; $('#p-tst').textContent=T.msg_corriger;
 $('#p-sol').textContent=T.msg_no_sol_defaut||T.bt_solution;
 $('#enn').textContent=ENONCE||'—';
 $('#tabs').innerHTML=ONGLETS.map((o,i)=>`<div class="tab${i?'':' on'}" data-t="${o[0]}"
   onclick="tab('${o[0]}')">${o[1]}</div>`).join('');}
i18n();

/* ---------- تلوين الصياغة ---------- */
const KW=/\b(and|as|assert|async|await|break|class|continue|def|del|elif|else|except|False|finally|for|from|global|if|import|in|is|lambda|None|nonlocal|not|or|pass|raise|return|True|try|while|with|yield|self|print|len|range|int|str|float|list|dict|set|open|input)\b/g;
function esc(t){return t.replace(/&/g,'&amp;').replace(/</g,'&lt;');}
function colorer(src){
 return esc(src).replace(/("{3}[\s\S]*?"{3}|'{3}[\s\S]*?'{3}|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|#[^\n]*)/g,
   m=>m[0]==='#'?`<span class="c">${m}</span>`:`<span class="s">${m}</span>`)
  .replace(/\b(\d+\.?\d*)\b/g,'<span class="n">$1</span>')
  .replace(KW,'<span class="k">$&</span>')
  .replace(/(?<=\bdef <span class="k">|\bdef )([A-Za-z_]\w*)/g,'<span class="f">$1</span>');}
let marques={};
function maj(){
 const src=code.value, n=src.split('\n').length;
 $('#hl').innerHTML=colorer(src)+'\n';
 $('#gut').innerHTML=Array.from({length:n},(_,i)=>{const m=marques[i+1];
   return m==='e'?`<b>${i+1}❌</b>`:m==='w'?`<i>${i+1}⚠</i>`:(i+1);}).join('\n');
 $('#st-n').textContent=n+' '+T.st_lignes;
 localStorage.setItem('essai',src);}
function sync(){$('#hl').scrollTop=code.scrollTop;$('#hl').scrollLeft=code.scrollLeft;
 $('#gut').scrollTop=code.scrollTop;}
function pos(){const s=code.value.slice(0,code.selectionStart).split('\n');
 $('#st-pos').textContent=s.length+':'+(s[s.length-1].length+1);}
code.value=localStorage.getItem('essai')||'# '+T.titre_app+'\n';
code.addEventListener('input',()=>{maj();auto();});
code.addEventListener('scroll',sync);
code.addEventListener('keyup',pos); code.addEventListener('click',pos);

/* ---------- اختصارات المحرّر ---------- */
const PAIRES={'(':')','[':']','{':'}','"':'"',"'":"'"};
code.addEventListener('keydown',e=>{
 const s=code.selectionStart,f=code.selectionEnd,v=code.value;
 if(e.key==='Tab'){e.preventDefault();
   if(s!==f){const d=v.lastIndexOf('\n',s-1)+1,bloc=v.slice(d,f);
     const nv=e.shiftKey?bloc.replace(/^ {1,4}/gm,''):bloc.replace(/^/gm,'    ');
     code.setRangeText(nv,d,f,'select');}
   else code.setRangeText('    ',s,f,'end'); maj(); return;}
 if(e.key==='Enter'&&e.ctrlKey){e.preventDefault();act('analyser');return;}
 if(e.key==='F5'){e.preventDefault();act('executer');return;}
 if(e.key.toLowerCase()==='s'&&e.ctrlKey){e.preventDefault();sauver();return;}
 if(e.key==='/'&&e.ctrlKey){e.preventDefault();
   const d=v.lastIndexOf('\n',s-1)+1,fin=v.indexOf('\n',f)<0?v.length:v.indexOf('\n',f);
   const bloc=v.slice(d,fin), off=bloc.split('\n').every(l=>!l.trim()||l.trimStart().startsWith('# '));
   code.setRangeText(off?bloc.replace(/^(\s*)# /gm,'$1'):bloc.replace(/^(\s*)(?=\S)/gm,'$1# '),
     d,fin,'select'); maj(); return;}
 if(PAIRES[e.key]&&s===f){e.preventDefault();
   code.setRangeText(e.key+PAIRES[e.key],s,f,'end');code.setSelectionRange(s+1,s+1);maj();return;}
 if(e.key==='Enter'){const d=v.lastIndexOf('\n',s-1)+1,t=v.slice(d,s);
   const ind=(t.match(/^\s*/)||[''])[0]+(t.trim().endsWith(':')?'    ':'');
   if(ind){e.preventDefault();code.setRangeText('\n'+ind,s,f,'end');maj();}}});

/* ---------- الأدوات ---------- */
let minuteur;
function auto(){clearTimeout(minuteur);minuteur=setTimeout(()=>act('analyser',true),700);}
function tab(t){document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('on',x.dataset.t===t));
 ONGLETS.forEach(o=>$('#p-'+o[0]).classList.toggle('hide',o[0]!==t));}
function aller(n){const ls=code.value.split('\n');let p=0;for(let i=0;i<n-1;i++)p+=ls[i].length+1;
 code.focus();code.setSelectionRange(p,p+(ls[n-1]||'').length);pos();}
function theme(){document.body.classList.toggle('clair');
 localStorage.setItem('clair',document.body.classList.contains('clair'));}
if(localStorage.getItem('clair')==='true')document.body.classList.add('clair');
let fs=+(localStorage.getItem('fs')||13);
function zoom(d){fs=Math.min(22,Math.max(10,fs+d));localStorage.setItem('fs',fs);
 document.documentElement.style.setProperty('--fs',fs+'px');}
zoom(0);
function flash(m){$('#st-msg').textContent=m;setTimeout(()=>$('#st-msg').textContent='',2500);}
function formater(){code.value=code.value.replace(/\t/g,'    ').replace(/[ \t]+$/gm,'')
 .replace(/\n{3,}/g,'\n\n').replace(/\s*$/,'\n');maj();flash('✨');}
function ouvrir(ev){const f=ev.target.files[0];if(!f)return;const r=new FileReader();
 r.onload=()=>{code.value=r.result;maj();act('analyser');};r.readAsText(f);}
async function post(u,d){const r=await fetch(u,{method:'POST',
 headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});return r.json();}
function chLang(){post('/api/langue',{lang:$('#lang').value}).then(()=>location.reload());}
async function telecharger(){const r=await post('/api/annoter',{code:code.value});
 const b=new Blob([r.texte],{type:'text/plain'});const a=document.createElement('a');
 a.href=URL.createObjectURL(b);a.download='essai_annote.py';a.click();}
async function sauver(){const r=await post('/api/sauver',{code:code.value});
 flash(T.msg_saved+' — '+r.fichier);histo();}

function pb(p){return `<div class="it ${p.gravite==='erreur'?'e':''}">
 ${p.gravite==='erreur'?'❌':'⚠️'} <span class="ln" onclick="aller(${p.ligne})">${T.ligne} ${p.ligne}</span>
 [${p.code}] ${p.message}<br>💡 <b>${T.cause}:</b> ${p.explication}<br>
 ✅ <b>${T.fix}:</b> ${p.correction}
 ${p.ligne_corrigee?`<br><code>${p.ligne_corrigee.trim().replace(/</g,'&lt;')}</code>`:''}</div>`;}

async function act(quoi,silencieux){
 if(quoi==='executer'){tab('run');$('#out').textContent=T.msg_running;const t0=Date.now();
  const r=await post('/api/executer',{code:code.value,stdin:$('#stdin').value});
  $('#st-ms').textContent=(Date.now()-t0)+' ms';
  $('#out').textContent=(r.sortie||'')+(r.ok?'':'\n⛔ '+r.erreur);return;}
 if(quoi==='analyser'){if(!silencieux)tab('err');
  const r=await post('/api/analyser',{code:code.value});
  marques={};r.problemes.forEach(p=>{if(marques[p.ligne]!=='e')
    marques[p.ligne]=p.gravite==='erreur'?'e':'w';});maj();
  $('#badge').textContent=r.note+' / 20';
  $('#p-err').innerHTML=r.problemes.length?r.problemes.map(pb).join(''):
   `<div class="it g">✅ ${T.aucun} — ${T.compile_ok}.</div>`;
  $('#p-bar').innerHTML='<pre>'+r.bareme+'</pre>';return;}
 if(quoi==='corriger'){tab('tst');$('#p-tst').textContent=T.msg_running;
  const r=await post('/api/corriger',{code:code.value});
  if(r.erreur){$('#p-tst').textContent=r.erreur;return;}
  $('#badge').textContent=r.note+' / 20';
  $('#p-tst').innerHTML=`<table><tr><th>${T.axe}</th><th>${T.note}</th><th>${T.sur}</th></tr>
   <tr><td>${T.ax_qualite}</td><td>${r.qualite}</td><td>6</td></tr>
   <tr><td>${T.ax_tests}</td><td>${r.tests}</td><td>10</td></tr>
   <tr><td>${T.ax_structure}</td><td>${r.structure}</td><td>4</td></tr>
   <tr><th>${T.total}</th><th>${r.note}</th><th>20</th></tr></table><br>`+
   r.resultats.map(t=>`<div class="it ${t.reussi?'g':'e'}">${t.reussi?'✅':'❌'} ${t.nom}
    ${t.reussi?'':`<br>${T.attendu}: <code>${t.attendu}</code><br>${T.obtenu}: <code>${t.obtenu}</code>`}</div>`).join('')+
   r.remarques.map(m=>`<div class="it">${m}</div>`).join('');
  marques={};r.problemes.forEach(p=>marques[p.ligne]=p.gravite==='erreur'?'e':'w');maj();
  $('#p-err').innerHTML=r.problemes.map(pb).join('')||`<div class="it g">✅ ${T.aucun}</div>`;
  histo();}}

async function voirSolution(){if(!confirm(T.msg_conf_sol))return;
 const r=await post('/api/solution',{code:code.value});tab('sol');
 $('#p-sol').innerHTML=r.solution?'<pre>'+colorer(r.solution)+'</pre>'+
  (r.diff?`<h4>🔀 ${T.diff}</h4><pre>${esc(r.diff)}</pre>`:''):T.msg_no_sol;}

async function scan(forcer){const r=await post('/api/interpreteurs',{forcer:!!forcer});
 $('#py').innerHTML=r.liste.map(d=>`<option value="${d.chemin}"
  ${d.chemin===r.actif?'selected':''}>${d.etiquette}</option>`).join('')||
  `<option>${T.interp_aucun}</option>`;
 $('#st-py').textContent='🐍 '+(r.actif_etiquette||'');}
async function chPy(){const r=await post('/api/python',{chemin:$('#py').value});
 majPy(r);}
async function chPyManuel(){const v=$('#pypath').value.trim(); if(!v)return;
 majPy(await post('/api/python',{chemin:v}));}
function majPy(r){if(!r.ok){flash('⛔ '+T.interp_ko);return;}
 flash('✔ '+T.interp_ok+' — '+r.etiquette); $('#st-py').textContent='🐍 '+r.etiquette;
 scan(); act('analyser');}
async function compat(){tab('cmp');$('#p-cmp').textContent=T.msg_running;
 const r=await post('/api/compat',{code:code.value,stdin:$('#stdin').value});
 $('#p-cmp').innerHTML=`<table><tr><th>${T.c_interp}</th><th>${T.c_compile}</th>
  <th>${T.c_exec}</th><th>${T.c_ms}</th><th>${T.c_sortie}</th></tr>`+
  r.lignes.map(x=>`<tr><td>${x.etiquette}</td><td>${x.compile?'✅':'❌'}</td>
   <td>${x.execute?'✅':'❌'}</td><td>${x.ms} ms</td>
   <td><code>${esc((x.sortie||x.erreur||'').slice(0,120))}</code></td></tr>`).join('')+
  '</table>';}
async function histo(){const r=await post('/api/historique',{});
 $('#p-his').innerHTML=r.essais.length?r.essais.map(e=>`<div class="it">
  <span class="ln" onclick="restaurer('${e.fichier}')">${e.fichier}</span> —
  <b>${e.note}</b>/20 · ${e.date}${e.vu?' · 📘':''}</div>`).join(''):T.msg_vide;}
async function restaurer(f){const r=await post('/api/restaurer',{fichier:f});
 if(r.code){code.value=r.code;maj();act('analyser');}}
maj();histo();scan();act('analyser',true);
$('#p-cmp').innerHTML='<button onclick="compat()">🧩 '+T.bt_compat+'</button>';
</script></body></html>"""


# ---------------------------------------------------------------------------
def fichier_temp(code: str) -> str:
    f = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8")
    f.write(code)
    f.close()
    return f.name


def journaliser(code: str, note, etiquette: str) -> str:
    os.makedirs(CFG["essais"], exist_ok=True)
    h = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nom = f"essai_{h}.py"
    with open(os.path.join(CFG["essais"], nom), "w", encoding="utf-8") as f:
        f.write(f"# note={note} date={h} vu_solution={CFG['vu_solution']} "
                f"({etiquette})\n{code}")
    return nom


def historique():
    out = []
    for c in sorted(glob.glob(os.path.join(CFG["essais"], "essai_*.py")), reverse=True)[:30]:
        try:
            entete = open(c, encoding="utf-8").readline()
        except OSError:
            continue
        note = re.search(r"note=(\S+)", entete)
        date = re.search(r"date=(\d{8}_\d{6})", entete)
        d = date.group(1) if date else ""
        out.append({"fichier": os.path.basename(c),
                    "note": note.group(1) if note else "—",
                    "date": f"{d[6:8]}/{d[4:6]} {d[9:11]}:{d[11:13]}" if d else "",
                    "vu": "vu_solution=True" in entete})
    return out


class H(BaseHTTPRequestHandler):
    def _rep(self, obj, ctype="application/json"):
        data = (json.dumps(obj, ensure_ascii=False) if ctype.startswith("application")
                else obj).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass

    # --- الصفحة -----------------------------------------------------------
    def do_GET(self):
        if self.path not in ("/", "/index.html"):
            return self.send_error(404)
        lg = langues.langue()
        cles = ["titre_app", "bt_analyser", "bt_executer", "bt_corriger", "bt_solution",
                "bt_telecharger", "bt_enregistrer", "bt_ouvrir", "bt_formater",
                "ph_stdin", "msg_analyser", "msg_corriger", "msg_running", "msg_conf_sol",
                "msg_no_sol", "msg_saved", "msg_vide", "st_lignes", "aide", "ligne",
                "cause", "fix", "aucun", "compile_ok", "axe", "note", "sur", "total",
                "ax_qualite", "ax_tests", "ax_structure", "attendu", "obtenu", "diff",
                "bt_scan", "bt_parcourir", "bt_compat", "c_interp", "c_compile",
                "c_exec", "c_ms", "c_sortie", "interp_ok", "interp_ko", "interp_aucun"]
        onglets = [["err", "🔍 " + U("tab_notes")], ["run", "▶ " + U("tab_run")],
                   ["tst", "🧪 " + U("tab_tests")], ["bar", "📊 " + U("tab_bareme")],
                   ["sol", "📘 " + U("tab_sol")], ["enn", "📄 " + U("tab_enonce")],
                   ["his", "🕘 " + U("tab_hist")],
                   ["cmp", "🧩 " + U("tab_compat")]]
        opts = "".join(f'<option value="{c}"{" selected" if c == lg else ""}>{n}</option>'
                       for c, n in langues.LANGUES.items())
        page = (PAGE.replace("__LG__", lg)
                    .replace("__DIR__", "rtl" if lg == "ar" else "ltr")
                    .replace("__TITRE__", U("titre_app"))
                    .replace("__OPTLANG__", opts)
                    .replace("__T__", json.dumps({k: U(k) for k in cles},
                                                 ensure_ascii=False))
                    .replace("__PYV__", json.dumps(version_python(CFG["python"])))
                    .replace("__ENONCE__", json.dumps(CFG["enonce"], ensure_ascii=False))
                    .replace("__ONGLETS__", json.dumps(onglets, ensure_ascii=False)))
        self._rep(page, "text/html")

    # --- الواجهة البرمجية --------------------------------------------------
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        d = json.loads(self.rfile.read(n) or "{}")
        code = d.get("code", "")
        r = self.path

        if r == "/api/langue":
            langues.definir_langue(d.get("lang", "ar"))
            return self._rep({"ok": True})

        if r == "/api/interpreteurs":
            liste = itp.scanner(forcer=bool(d.get("forcer")))
            return self._rep({"liste": liste, "actif": CFG["python"],
                              "actif_etiquette": itp.info(CFG["python"]).get(
                                  "etiquette", CFG["python"])})

        if r == "/api/python":
            v = itp.valider(d.get("chemin", ""))
            if not v.get("ok"):
                return self._rep({"ok": False})
            CFG["python"] = v["chemin"]
            analyseur.PYTHON = correcteur.PYTHON = v["chemin"]
            return self._rep({"ok": True, "etiquette": v["etiquette"]})

        if r == "/api/compat":
            return self._rep({"lignes": itp.matrice_compatibilite(
                code, stdin=d.get("stdin", ""))})

        if r == "/api/analyser":
            probs = analyser_source(code, "essai.py", py=CFG["python"])
            note, mention, detail = calculer_note(probs)
            return self._rep({"note": note, "mention": mention,
                              "problemes": [p.__dict__ for p in probs],
                              "bareme": "\n".join(bloc_note(note, mention, detail))})

        if r == "/api/annoter":
            probs = analyser_source(code, "essai.py", py=CFG["python"])
            return self._rep({"texte": annoter(code.splitlines(), probs, "essai.py")})

        if r == "/api/executer":
            f = fichier_temp(code)
            try:
                return self._rep(correcteur.executer(f, None, [], d.get("stdin", "")))
            finally:
                os.unlink(f)

        if r == "/api/corriger":
            if not CFG["solution"]:
                return self._rep({"erreur": U("msg_no_sol")})
            f = fichier_temp(code)
            try:
                res = correcteur.corriger(f, CFG["solution"], CFG["tests"])
            finally:
                os.unlink(f)
            journaliser(code, res["note"], "correction")
            return self._rep({k: res[k] for k in
                              ("note", "qualite", "tests", "structure",
                               "resultats", "remarques")}
                             | {"problemes": [p.__dict__ for p in res["problemes"]]})

        if r == "/api/solution":
            if not CFG["solution"]:
                return self._rep({"solution": None})
            CFG["vu_solution"] = True
            src = open(CFG["solution"], encoding="utf-8").read()
            diff = "\n".join(difflib.unified_diff(
                code.splitlines(), src.splitlines(), lineterm="", n=2))
            journaliser(code, "—", "vue-solution")
            return self._rep({"solution": src, "diff": diff})

        if r == "/api/sauver":
            return self._rep({"fichier": journaliser(code, "—", "sauvegarde")})

        if r == "/api/historique":
            return self._rep({"essais": historique()})

        if r == "/api/restaurer":
            f = os.path.join(CFG["essais"], os.path.basename(d.get("fichier", "")))
            if not os.path.isfile(f):
                return self._rep({"code": None})
            txt = open(f, encoding="utf-8").read().split("\n", 1)
            return self._rep({"code": txt[1] if len(txt) > 1 else ""})

        self.send_error(404)


def main():
    ap = argparse.ArgumentParser(description="IDE محلّي للتلميذ")
    ap.add_argument("-s", "--solution")
    ap.add_argument("-t", "--tests")
    ap.add_argument("-e", "--enonce")
    ap.add_argument("--essais", default="essais")
    ap.add_argument("--python", default=detecter_python(),
                    help="مسار python.exe للترجمة والتنفيذ")
    ap.add_argument("--lang", choices=list(langues.LANGUES), default=langues.langue())
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()

    langues.definir_langue(a.lang)
    CFG.update(solution=a.solution, tests=a.tests, essais=a.essais, python=a.python)
    analyseur.PYTHON = a.python
    correcteur.PYTHON = a.python
    if a.enonce and os.path.isfile(a.enonce):
        CFG["enonce"] = open(a.enonce, encoding="utf-8").read()

    print(f"🌐 http://127.0.0.1:{a.port}")
    print(f"🐍 {U('interpreteur')}: {a.python}  ({version_python(a.python)})")
    print(f"📘 {U('solution')}: {a.solution or '—'}   🗣 {langues.LANGUES[a.lang]}")
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()


if __name__ == "__main__":
    main()
