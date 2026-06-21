#!/usr/bin/env python3
"""Render leaderboard.json into a premium glassmorphism BNB-Hack page (Cloudflare/Pages).
  python scripts/build_leaderboard.py <leaderboard.json> <out.html>
"""
import json, sys, time, os

src = sys.argv[1] if len(sys.argv) > 1 else "dashboard/leaderboard.json"
out = sys.argv[2] if len(sys.argv) > 2 else "leaderboard-site/public/index.html"
D = json.load(open(src))
D["built_ts"] = int(time.time())
for r in D.get("rows", []):
    r.pop("ours", None)

TEMPLATE = r"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta http-equiv="refresh" content="120"/>
<title>BNB Hack · Track 1 Live Leaderboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@500;700&family=Press+Start+2P&display=swap" rel="stylesheet">
<style>
:root{--bg:#070809;--txt:#f2f4f8;--mut:#888f9c;--gold:#F0B90B;--gold2:#FCD535;--g:#1fd286;--r:#ff5470;
--glass:rgba(255,255,255,.045);--glass2:rgba(255,255,255,.075);--line:rgba(255,255,255,.09);
--shadow:0 12px 44px rgba(0,0,0,.5);--mono:"JetBrains Mono",ui-monospace,monospace}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
body{min-height:100vh;color:var(--txt);font:15px/1.55 "Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
background:
 radial-gradient(900px 520px at 12% -6%,rgba(240,185,11,.18),transparent 60%),
 radial-gradient(820px 620px at 92% 2%,rgba(120,110,255,.10),transparent 55%),
 radial-gradient(760px 760px at 50% 118%,rgba(240,185,11,.07),transparent 60%),
 var(--bg);background-attachment:fixed;padding:36px 16px 76px}
.wrap{max-width:920px;margin:0 auto}
.glass{background:var(--glass);backdrop-filter:blur(24px) saturate(155%);-webkit-backdrop-filter:blur(24px) saturate(155%);
 border:1px solid var(--line);border-radius:20px;box-shadow:var(--shadow),inset 0 1px 0 rgba(255,255,255,.06)}
.hero{text-align:center;margin:2px 0 28px}
.mark{font:normal 22px/1.2 "Press Start 2P",monospace;color:var(--gold);letter-spacing:1px;
 text-shadow:0 2px 24px rgba(240,185,11,.45),0 0 1px rgba(0,0,0,.4)}
.ed{margin-top:13px;font:600 10.5px/1 var(--mono);letter-spacing:.34em;text-transform:uppercase;color:var(--mut)}
.h1{font:900 42px/1.03 "Inter";letter-spacing:-1.4px;margin:16px 0 9px;
 background:linear-gradient(180deg,#fff,#c4c9d2);-webkit-background-clip:text;background-clip:text;color:transparent}
.h1 b{background:linear-gradient(135deg,var(--gold2),var(--gold));-webkit-background-clip:text;background-clip:text;color:transparent}
.spon{color:var(--mut);font-size:13px}
.cd{margin-top:18px;display:inline-flex;gap:9px;align-items:center;padding:10px 20px;border-radius:999px;
 font:600 13px/1 var(--mono);color:var(--gold2);background:var(--glass);border:1px solid var(--line);
 backdrop-filter:blur(12px);box-shadow:inset 0 1px 0 rgba(255,255,255,.05)}
.cd::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--g);box-shadow:0 0 10px var(--g);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}.cd b{color:#fff}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(118px,1fr));gap:12px;margin:26px 0}
.st{padding:17px 14px;text-align:center;background:var(--glass);border:1px solid var(--line);border-radius:18px;
 backdrop-filter:blur(20px);box-shadow:inset 0 1px 0 rgba(255,255,255,.05)}
.st .v{font:800 23px/1 "Inter";letter-spacing:-.6px;background:linear-gradient(135deg,#fff,#a9afbc);-webkit-background-clip:text;background-clip:text;color:transparent}
.st .k{color:var(--mut);font-size:10px;letter-spacing:.16em;text-transform:uppercase;margin-top:7px}
.banner{padding:13px 16px;margin:0 0 18px;font-size:13px;color:var(--gold2);text-align:center;border-radius:16px;
 background:linear-gradient(90deg,rgba(240,185,11,.1),rgba(240,185,11,.02));border:1px solid rgba(240,185,11,.25)}
.bad{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:0 0 22px}
.b{padding:16px;background:var(--glass);border:1px solid var(--line);border-radius:18px;backdrop-filter:blur(20px);
 box-shadow:inset 0 1px 0 rgba(255,255,255,.05);transition:transform .2s}.b:hover{transform:translateY(-3px)}
.b .bl{font:600 10px/1 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--mut)}
.b .bn{font:600 13px/1 var(--mono);margin:10px 0 6px;display:flex;align-items:center;gap:7px}
.b .bv{font:800 18px/1 "Inter"}
.tools{display:flex;gap:10px;align-items:center;margin:24px 0 14px;flex-wrap:wrap}
.inp{background:var(--glass);border:1px solid var(--line);border-radius:14px;color:var(--txt);padding:12px 16px;
 font:14px "Inter";backdrop-filter:blur(14px);outline:none;transition:.2s;box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}
.inp::placeholder{color:var(--mut)}.inp:focus{border-color:rgba(240,185,11,.6);box-shadow:0 0 0 3px rgba(240,185,11,.13)}
#q{flex:1;min-width:170px}#minv{width:118px}#minv::-webkit-outer-spin-button,#minv::-webkit-inner-spin-button{-webkit-appearance:none}
.seg{display:inline-flex;background:var(--glass);border:1px solid var(--line);border-radius:14px;padding:4px;gap:3px;backdrop-filter:blur(14px)}
.seg button{border:0;background:transparent;color:var(--mut);font:600 13px "Inter";padding:9px 15px;border-radius:11px;cursor:pointer;transition:.18s}
.seg button:hover{color:var(--txt)}
.seg button.on{background:linear-gradient(135deg,var(--gold2),var(--gold));color:#0a0a0a;box-shadow:0 4px 16px rgba(240,185,11,.35)}
.tbl{overflow:hidden;background:var(--glass);border:1px solid var(--line);border-radius:20px;backdrop-filter:blur(24px);box-shadow:var(--shadow),inset 0 1px 0 rgba(255,255,255,.06)}
.thead,.row{display:grid;grid-template-columns:44px 1.5fr 82px 94px 78px 70px 122px;align-items:center;gap:10px;padding:14px 18px}
.thead{border-bottom:1px solid var(--line);font:600 10.5px/1 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--mut)}
.thead span{cursor:pointer;transition:.15s}.thead span:hover{color:var(--gold2)}
.thead .num,.row .num{text-align:right}
.rw{border-bottom:1px solid rgba(255,255,255,.05)}.rw:last-child{border:0}
.row{cursor:pointer;transition:background .15s}.row:hover{background:rgba(255,255,255,.035)}
.row.r1,.row.r2,.row.r3{background:linear-gradient(90deg,rgba(240,185,11,.08),transparent 70%)}
.n{font:700 14px/1 var(--mono);color:var(--mut);text-align:center}
.r1 .n{color:var(--gold)}.r2 .n{color:#d4d8df}.r3 .n{color:#e08a3c}
.ag{display:flex;align-items:center;gap:10px;min-width:0}
.dot{width:22px;height:22px;border-radius:50%;flex:none;box-shadow:0 0 0 1px rgba(255,255,255,.12)}
.adr{font:500 12.5px/1 var(--mono);overflow:hidden;text-overflow:ellipsis}
.ext{margin-left:auto;color:var(--mut);text-decoration:none;font-size:13px;opacity:.55;transition:.15s}.ext:hover{color:var(--gold);opacity:1}
.vv{font:700 13px/1 var(--mono);text-align:right}
.pos{color:var(--g)}.neg{color:var(--r)}.zero{color:var(--mut)}
.dqcell{display:flex;align-items:center;gap:8px}
.dqwrap{height:6px;flex:1;background:rgba(255,255,255,.08);border-radius:6px;overflow:hidden}
.dqv{font:600 11px/1 var(--mono);color:var(--mut);width:36px;text-align:right}
.det{max-height:0;overflow:hidden;transition:max-height .3s ease}.det.open{max-height:200px}
.dethold{display:flex;flex-wrap:wrap;gap:7px;padding:2px 18px 15px}
.chip{background:var(--glass2);border:1px solid var(--line);border-radius:10px;padding:5px 11px;font:600 11px/1 var(--mono);color:var(--mut)}
.chip b{color:var(--gold2)}
.foot{text-align:center;color:var(--mut);font-size:12px;margin-top:24px;line-height:1.9}.foot b{color:var(--txt)}
.foot a{color:var(--gold2);text-decoration:none}.foot a:hover{text-decoration:underline}
.by{margin-top:6px;font-size:12.5px}
@media(max-width:680px){.mark{font-size:15px}.h1{font-size:30px}.thead,.row{grid-template-columns:32px 1fr 76px 62px;gap:8px}
 .spk,.c24,.dqcol{display:none}.bad{grid-template-columns:1fr}.tools{flex-direction:column;align-items:stretch}#minv{width:100%}.seg{justify-content:center}}
</style></head><body><div class="wrap">
<div class="hero">
  <div class="mark">BNB HACK</div>
  <div class="ed">AI Trading Agent Edition</div>
  <div class="h1">Track 1 · <b>Live Leaderboard</b></div>
  <div class="spon">CoinMarketCap × Trust Wallet × BNB Chain · $24,000 · top 5 win</div>
  <div class="cd" id="cd"></div>
</div>
<div class="stats" id="stats"></div>
<div id="banner"></div>
<div class="bad" id="badges"></div>
<div class="tools">
  <input id="q" class="inp" placeholder="search agent address…"/>
  <input id="minv" class="inp" type="number" placeholder="min $"/>
  <div class="seg" id="flt">
    <button data-v="all" class="on">All</button>
    <button data-v="funded">Funded</button>
    <button data-v="profit">In&nbsp;profit</button>
  </div>
</div>
<div class="tbl"><div class="thead" id="thead"></div><div id="rows"></div></div>
<div class="foot">Built from on-chain data · <b>permissionless &amp; verifiable</b><br>
  Updated <span id="upd"></span> · refreshes every ~30 min · not affiliated with organizers.
  <div class="by">built by <b><a href="https://x.com/itsabigdill" target="_blank" rel="noopener">@itsabigdill</a></b>
   · <a href="https://github.com/DanMarteens" target="_blank" rel="noopener">github</a>
   · <a href="https://cto.monster" target="_blank" rel="noopener">cto.monster</a></div></div>
</div>
<script>
const D=/*DATA*/, R=D.rows||[], S=D.stats||{}, LIVE=D.has_baseline;
const $=id=>document.getElementById(id);
const short=a=>a.slice(0,6)+"…"+a.slice(-4);
const dot=a=>{let h=0;for(let i=2;i<10;i++)h=(h*31+a.charCodeAt(i))>>>0;return `hsl(${h%360} 72% 56%)`;};
const fmt=v=>"$"+(v>=1000?Math.round(v).toLocaleString():v.toFixed(2));
const pct=v=>v==null?'<span class="zero">—</span>':`<span class="${v>0?'pos':v<0?'neg':'zero'}">${v>0?'+':''}${v.toFixed(2)}%</span>`;
function spark(a){if(!a||a.length<2)return '';const w=72,h=20,mn=Math.min(...a),mx=Math.max(...a),rg=(mx-mn)||1;
 const p=a.map((v,i)=>`${(i/(a.length-1)*w).toFixed(1)},${(h-(v-mn)/rg*h).toFixed(1)}`).join(' ');
 return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><polyline points="${p}" fill="none" stroke="${a[a.length-1]>=a[0]?'var(--g)':'var(--r)'}" stroke-width="1.6" stroke-linejoin="round"/></svg>`;}
function dq(dd){const p=Math.min(100,dd/30*100),c=p<40?'var(--g)':p<70?'var(--gold)':'var(--r)';
 return `<div class="dqcell"><div class="dqwrap"><div style="height:100%;width:${p}%;background:${c}"></div></div><span class="dqv">${dd.toFixed(0)}%</span></div>`;}
const START=Date.UTC(2026,5,22),END=Date.UTC(2026,5,29);
function cd(){const n=Date.now();let t,l;if(n<START){t=START;l='Starts in';}else if(n<END){t=END;l='Time left';}else{$('cd').textContent='Competition ended';return;}
 const d=Math.max(0,t-n);$('cd').innerHTML=`${l} &nbsp;<b>${Math.floor(d/864e5)}d ${Math.floor(d%864e5/36e5)}h ${Math.floor(d%36e5/6e4)}m</b>`;}
cd();setInterval(cd,60000);
$('upd').textContent=new Date(D.built_ts*1000).toUTCString().replace('GMT','UTC');
$('stats').innerHTML=[['Agents',S.n],['Funded',S.funded],['Deployed',fmt(S.deployed||0)],
 LIVE?['In profit',S.in_profit]:null,LIVE?['Avg PnL',(S.avg_ret>=0?'+':'')+S.avg_ret+'%']:null,
 LIVE?['Survivors',S.survivors+'/'+S.n]:null].filter(Boolean)
 .map(([k,v])=>`<div class="st"><div class="v">${v}</div><div class="k">${k}</div></div>`).join('');
if(!LIVE){$('banner').className='banner';$('banner').innerHTML='⏳ <b>Competition starts Jun 22, 00:00 UTC.</b> Live ranking by total return begins then; showing registered agents + funding for now.';}
const funded=R.filter(r=>r.value>0);
if(funded.length){const pk=(k,d)=>funded.slice().sort((a,b)=>((b[k]??-1e9)-(a[k]??-1e9))*d)[0];
 const topR=pk('ret_pct',1),topM=pk('chg24h',1),safe=funded.slice().sort((a,b)=>a.dd_pct-b.dd_pct)[0];
 const card=(l,r,v)=>`<div class="b"><div class="bl">${l}</div><div class="bn"><span class="dot" style="display:inline-block;background:${dot(r.agent)};vertical-align:middle"></span>${short(r.agent)}</div><div class="bv">${v}</div></div>`;
 const c=[];if(LIVE&&topR&&topR.ret_pct!=null)c.push(card('🥇 Top return',topR,pct(topR.ret_pct)));
 if(topM&&topM.chg24h!=null)c.push(card('🔥 Top mover 24h',topM,pct(topM.chg24h)));
 if(LIVE&&safe)c.push(card('🛡️ Lowest drawdown',safe,safe.dd_pct.toFixed(1)+'%'));
 $('badges').innerHTML=c.join('');}
let key=LIVE?'ret_pct':'value',dir=-1;
const cols=[['#','rank',1],['Agent','agent',0],['Chart','',0,'spk'],['Value','value',1],['PnL','ret_pct',1],['24h','chg24h',1,'c24'],['DQ risk','dd_pct',1,'dqcol']];
$('thead').innerHTML=cols.map(c=>`<span class="${c[2]?'num':''} ${c[3]||''}" data-k="${c[1]}">${c[0]}</span>`).join('');
$('thead').querySelectorAll('span[data-k]').forEach(el=>{const k=el.dataset.k;if(k)el.onclick=()=>{dir=(key===k)?-dir:-1;key=k;render();};});
function rowHTML(r){const h=(r.holds||[]).map(x=>`<span class="chip">${x[0]} <b>$${x[1]}</b></span>`).join('')||'<span class="chip">no in-scope holdings</span>';
 return `<div class="rw"><div class="row ${r.rank<=3?'r'+r.rank:''}" onclick="this.nextElementSibling.classList.toggle('open')">
  <div class="n">${r.rank}</div>
  <div class="ag"><span class="dot" style="background:${dot(r.agent)}"></span><span class="adr">${short(r.agent)}</span>
   <a class="ext" href="https://bscscan.com/address/${r.agent}" target="_blank" rel="noopener" onclick="event.stopPropagation()">↗</a></div>
  <div class="spk">${spark(r.spark)}</div><div class="vv">${fmt(r.value)}</div><div class="vv">${pct(r.ret_pct)}</div>
  <div class="vv c24">${pct(r.chg24h)}</div><div class="dqcol">${dq(r.dd_pct||0)}</div></div>
  <div class="det"><div class="dethold">${h}</div></div></div>`;}
function render(){let rs=R.slice();
 const q=$('q').value.trim().toLowerCase();if(q)rs=rs.filter(r=>r.agent.toLowerCase().includes(q));
 const mv=parseFloat($('minv').value);if(!isNaN(mv))rs=rs.filter(r=>r.value>=mv);
 const f=$('flt').querySelector('button.on').dataset.v;if(f==='funded')rs=rs.filter(r=>r.value>0);else if(f==='profit')rs=rs.filter(r=>(r.ret_pct||0)>0);
 rs.sort((a,b)=>((a[key]??-1e9)-(b[key]??-1e9))*dir);
 $('rows').innerHTML=rs.map(rowHTML).join('')||'<div style="padding:22px;text-align:center;color:var(--mut)">no agents match</div>';}
$('q').oninput=render;$('minv').oninput=render;
$('flt').querySelectorAll('button').forEach(b=>b.onclick=()=>{$('flt').querySelectorAll('button').forEach(x=>x.classList.remove('on'));b.classList.add('on');render();});
render();
</script></body></html>"""

html = TEMPLATE.replace("/*DATA*/", json.dumps(D))
os.makedirs(os.path.dirname(out), exist_ok=True)
open(out, "w").write(html)
print("wrote", out, "(", len(html), "bytes,", len(D.get("rows", [])), "rows )")
