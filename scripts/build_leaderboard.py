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
:root{--bg:#080d24;--txt:#eef1f8;--mut:#8590ad;--gold:#F0B90B;--gold2:#FCD535;
--blue:#3861FB;--purple:#9b6bff;--cyan:#3fd0e0;--g:#1fd286;--r:#ff5470;
--glass:rgba(255,255,255,.04);--glass2:rgba(255,255,255,.07);--line:rgba(140,160,255,.13);
--shadow:0 12px 46px rgba(0,0,0,.55);--mono:"JetBrains Mono",ui-monospace,monospace}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
body{min-height:100vh;color:var(--txt);font:15px/1.55 "Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
background:
 radial-gradient(820px 480px at 9% -8%,rgba(240,185,11,.15),transparent 56%),
 radial-gradient(720px 560px at 48% -2%,rgba(155,107,255,.16),transparent 55%),
 radial-gradient(840px 620px at 93% 3%,rgba(56,97,251,.18),transparent 55%),
 radial-gradient(760px 760px at 50% 120%,rgba(63,208,224,.07),transparent 60%),
 var(--bg);background-attachment:fixed;padding:36px 16px 76px}
.wrap{max-width:920px;margin:0 auto}
.glass{background:var(--glass);backdrop-filter:blur(24px) saturate(155%);-webkit-backdrop-filter:blur(24px) saturate(155%);
 border:1px solid var(--line);border-radius:20px;box-shadow:var(--shadow),inset 0 1px 0 rgba(255,255,255,.06)}
.hero{text-align:center;margin:2px 0 28px}
.mark{font:normal 22px/1.3 "Press Start 2P",monospace;letter-spacing:1px;
 background:linear-gradient(95deg,#F0B90B 0%,#ff7a45 22%,#ff4d9d 44%,#b14dff 64%,#5b8cff 82%,#36cfe6 100%);
 -webkit-background-clip:text;background-clip:text;color:transparent;filter:drop-shadow(0 3px 22px rgba(155,107,255,.4))}
.ed{margin-top:13px;font:600 10.5px/1 var(--mono);letter-spacing:.34em;text-transform:uppercase;color:var(--cyan)}
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
.tools{display:flex;gap:10px;align-items:center;margin:24px 0 12px;flex-wrap:wrap}
.wbar{display:flex;align-items:center;gap:12px;margin:0 0 14px;flex-wrap:wrap}
.wl{font:600 10.5px/1 var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--mut)}
.inp{background:var(--glass);border:1px solid var(--line);border-radius:14px;color:var(--txt);padding:12px 16px;
 font:14px "Inter";backdrop-filter:blur(14px);outline:none;transition:.2s;box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}
.inp::placeholder{color:var(--mut)}.inp:focus{border-color:rgba(240,185,11,.6);box-shadow:0 0 0 3px rgba(240,185,11,.13)}
#q{flex:1;min-width:170px}#minv{width:118px}#minv::-webkit-outer-spin-button,#minv::-webkit-inner-spin-button{-webkit-appearance:none}
.seg{display:inline-flex;background:var(--glass);border:1px solid var(--line);border-radius:14px;padding:4px;gap:3px;backdrop-filter:blur(14px)}
.seg button{border:0;background:transparent;color:var(--mut);font:600 13px "Inter";padding:9px 15px;border-radius:11px;cursor:pointer;transition:.18s}
.seg button:hover{color:var(--txt)}
.seg button.on{background:linear-gradient(135deg,var(--gold2),var(--gold));color:#0a0a0a;box-shadow:0 4px 16px rgba(240,185,11,.35)}
.selwrap{position:relative;display:inline-block}
.selwrap::after{content:"▾";position:absolute;right:14px;top:50%;transform:translateY(-50%);color:var(--mut);pointer-events:none;font-size:11px}
.sel{appearance:none;-webkit-appearance:none;background:var(--glass);border:1px solid var(--line);border-radius:14px;color:var(--txt);padding:12px 36px 12px 16px;font:14px "Inter";backdrop-filter:blur(14px);cursor:pointer;outline:none;transition:.2s}
.sel:focus{border-color:rgba(56,97,251,.6);box-shadow:0 0 0 3px rgba(56,97,251,.13)}
.sel option{background:#0d1430;color:var(--txt)}
.tbl{overflow:hidden;background:var(--glass);border:1px solid var(--line);border-radius:20px;backdrop-filter:blur(24px);box-shadow:var(--shadow),inset 0 1px 0 rgba(255,255,255,.06)}
.thead,.row{display:grid;grid-template-columns:46px 1.6fr 112px 116px 78px 140px;align-items:center;gap:11px;padding:14px 18px}
.pnlcol{font-weight:800;font-size:15.5px}.thead .pnlcol{font-weight:700;font-size:10.5px}
.thead{border-bottom:1px solid var(--line);font:600 10.5px/1 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--mut)}
.thead span{cursor:pointer;transition:.15s}.thead span:hover{color:var(--gold2)}
.thead .num,.row .num{text-align:right}
.rw{border-bottom:1px solid rgba(255,255,255,.05)}.rw:last-child{border:0}
.row{cursor:pointer;transition:background .15s}.row:hover{background:rgba(255,255,255,.035)}
.row.r1,.row.r2,.row.r3{background:linear-gradient(90deg,rgba(240,185,11,.09),transparent 72%);box-shadow:inset 3px 0 0 var(--gold)}
.row.r4,.row.r5{background:linear-gradient(90deg,rgba(240,185,11,.045),transparent 72%);box-shadow:inset 3px 0 0 rgba(240,185,11,.45)}
.n{font:700 14px/1 var(--mono);color:var(--mut);text-align:center}
.r1 .n{color:var(--gold)}.r2 .n{color:#d4d8df}.r3 .n{color:#e08a3c}.r4 .n,.r5 .n{color:var(--gold2)}
.prize{font:700 9px/1 var(--mono);background:linear-gradient(135deg,var(--gold2),var(--gold));color:#0a0a0a;border-radius:5px;padding:3px 6px;margin-left:7px;letter-spacing:.04em;flex:none}
.dep{font:600 9px/1 var(--mono);background:rgba(91,140,255,.16);color:#9db4ff;border:1px solid rgba(91,140,255,.3);border-radius:5px;padding:3px 6px;margin-left:7px;letter-spacing:.03em;flex:none}
.idle{font:600 9px/1 var(--mono);background:rgba(255,170,60,.14);color:#ffb84d;border:1px solid rgba(255,170,60,.32);border-radius:5px;padding:3px 6px;margin-left:7px;letter-spacing:.03em;flex:none}
.idlerow{opacity:.5}
.splitrow{padding:10px 18px;font:600 10.5px/1.4 var(--mono);letter-spacing:.04em;text-transform:uppercase;color:#ffb84d;background:rgba(255,170,60,.06);border-top:1px solid rgba(255,170,60,.18);border-bottom:1px solid var(--line)}
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
@media(max-width:680px){.mark{font-size:15px}.h1{font-size:30px}.thead,.row{grid-template-columns:30px 1fr 80px 74px;gap:8px}
 .trcol,.ddcol{display:none}.pnlcol{font-size:14px}.bad{grid-template-columns:1fr}.tools{flex-direction:column;align-items:stretch}#minv{width:100%}}
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
<div class="tools">
  <input id="q" class="inp" placeholder="search agent address…"/>
  <input id="minv" class="inp" type="number" placeholder="min $"/>
  <div class="selwrap"><select id="flt" class="sel">
    <option value="all">all agents</option>
    <option value="funded">funded only</option>
    <option value="profit">in profit</option>
  </select></div>
</div>
<div class="wbar"><span class="wl">PnL window</span>
  <div class="selwrap"><select id="wins" class="sel">
    <option value="d1">Day 1 · Jun 22</option>
    <option value="d2">Day 2 · Jun 23</option>
    <option value="d3">Day 3 · Jun 24</option>
    <option value="d4">Day 4 · Jun 25</option>
    <option value="d5">Day 5 · Jun 26</option>
    <option value="d6">Day 6 · Jun 27</option>
    <option value="d7">Day 7 · Jun 28</option>
    <option value="all" selected>All</option>
  </select></div>
</div>
<div class="tbl"><div class="thead" id="thead"></div><div id="rows"></div></div>
<div class="foot">Built from on-chain data · <b>permissionless &amp; verifiable</b><br>
  PnL is deposit-invariant: return = (value − net deposits) ÷ go-live capital, so depositing or withdrawing leaves the rank unchanged — only trading moves it.<br>
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
// Drawdown shown as a plain coloured % (no bar): grey when small, gold approaching the
// 30% DQ line, red when severe. 30% is disqualification.
function dq(dd){const c=dd<10?'var(--mut)':dd<22?'var(--gold)':'var(--r)';
 return `<span class="dqv" style="color:${c}">${dd.toFixed(1)}%</span>`;}
const START=Date.UTC(2026,5,22),END=Date.UTC(2026,5,29);
function cd(){const n=Date.now();let t,l;if(n<START){t=START;l='Starts in';}else if(n<END){t=END;l='Time left';}else{$('cd').textContent='Competition ended';return;}
 const d=Math.max(0,t-n);$('cd').innerHTML=`${l} &nbsp;<b>${Math.floor(d/864e5)}d ${Math.floor(d%864e5/36e5)}h ${Math.floor(d%36e5/6e4)}m</b>`;}
cd();setInterval(cd,60000);
$('upd').textContent=new Date(D.built_ts*1000).toUTCString().replace('GMT','UTC');
const WINS={'all':'All','d1':'Day 1','d2':'Day 2','d3':'Day 3','d4':'Day 4','d5':'Day 5','d6':'Day 6','d7':'Day 7'};
const PRIZE={1:'$10k',2:'$6k',3:'$4k',4:'$2k',5:'$2k'};
let WIN='all',key='ret_pct',dir=-1;
const winv=r=>{const v=r.win?r.win[WIN]:r.ret_pct;return v==null?null:v;};
const tb=(a,b)=>a.agent<b.agent?-1:1;                       // neutral tiebreak — NOT wallet size
const STARTED=LIVE&&R.some(r=>{const v=r.win&&r.win.all;return v!=null&&Math.abs(v)>1e-9;}); // any real PnL yet?
// A wallet is RANKED (above the divider) only while it is actually competing: it traded at
// least once this UTC day AND currently holds >= $1 of in-scope assets. The rules score any
// hour that starts sub-$1 at 0% and require >=1 swap/day, so idle or sub-$1 wallets drop
// below the divider. Pre-go-live (!LIVE) everyone is listed.
const RANK_MIN_USD=1.0;
const ranked=r=>!LIVE||(r.traded&&r.value>=RANK_MIN_USD);
const rankSort=(a,b)=>((ranked(b)?1:0)-(ranked(a)?1:0))||((winv(b)??-1e9)-(winv(a)??-1e9))||tb(a,b);
function ranks(){let i=0;R.slice().sort(rankSort).forEach(r=>{r._rk=ranked(r)?(++i):null;});}
function stats(){const rv=R.map(winv).filter(v=>v!=null),av=rv.length?rv.reduce((a,b)=>a+b,0)/rv.length:null;
 $('stats').innerHTML=[['Agents',S.n],['Funded',S.funded],
  LIVE&&S.trading!=null?['Trading',S.trading+'/'+S.n]:null,['Deployed',fmt(S.deployed||0)],
  LIVE?['In profit',R.filter(r=>(winv(r)||0)>0).length]:null,
  LIVE?['Avg PnL',av==null?'—':(av>=0?'+':'')+av.toFixed(2)+'%']:null,
  LIVE?['Survivors',S.survivors+'/'+S.n]:null].filter(Boolean)
  .map(([k,v])=>`<div class="st"><div class="v">${v}</div><div class="k">${k}</div></div>`).join('');}
if(!LIVE){$('banner').className='banner';$('banner').innerHTML='⏳ <b>Competition starts Jun 22, 00:00 UTC.</b> Live ranking by total return begins then; showing registered agents + funding for now.';}
const cols=[['#','rank',1],['Agent','agent',0],['Value','value',1],['PnL','ret_pct',1,'pnlcol'],['Trades','trades',1,'trcol'],['Drawdown','dd_pct',1,'ddcol']];
$('thead').innerHTML=cols.map(c=>`<span class="${c[2]?'num':''} ${c[3]||''}" data-k="${c[1]}">${c[0]}</span>`).join('');
$('thead').querySelectorAll('span[data-k]').forEach(el=>{const k=el.dataset.k;if(k)el.onclick=()=>{dir=(key===k)?-dir:-1;key=k;render();};});
function rowHTML(r){const h=(r.holds||[]).map(x=>`<span class="chip">${x[0]} <b>$${x[1]}</b></span>`).join('')||'<span class="chip">no in-scope holdings</span>';
 const notRanked=LIVE&&!ranked(r);
 const tag=!notRanked?'':(!r.traded?'no trade today':'under $1');   // why it's below the line
 return `<div class="rw"><div class="row ${STARTED&&ranked(r)&&r._rk<=5?'r'+r._rk:''} ${notRanked?'idlerow':''}" onclick="this.nextElementSibling.classList.toggle('open')">
  <div class="n">${r._rk==null?'·':r._rk}</div>
  <div class="ag"><span class="dot" style="background:${dot(r.agent)}"></span><span class="adr">${short(r.agent)}</span>
   ${STARTED&&ranked(r)&&WIN==='all'&&PRIZE[r._rk]?`<span class="prize">${PRIZE[r._rk]}</span>`:''}
   ${tag?`<span class="idle" title="not scoring: needs >=1 swap this UTC day AND >=$1 in-scope balance">${tag}</span>`:''}
   ${r.dep>1?`<span class="dep" title="external deposits since go-live — excluded from PnL">+$${r.dep>=1000?Math.round(r.dep).toLocaleString():Math.round(r.dep)} dep</span>`:''}
   <a class="ext" href="https://bscscan.com/address/${r.agent}" target="_blank" rel="noopener" onclick="event.stopPropagation()">↗</a></div>
  <div class="vv">${fmt(r.value)}${(WIN==='all'&&r.base)?`<span style="display:block;font-size:10px;opacity:.45;font-weight:400">from ${fmt(r.base)}</span>`:''}</div><div class="vv pnlcol">${pct(winv(r))}</div>
  <div class="vv trcol ${LIVE&&!r.traded?'neg':''}">${r.trades||0}</div><div class="ddcol">${dq(r.dd_pct||0)}</div></div>
  <div class="det"><div class="dethold">${h}</div></div></div>`;}
function render(){let rs=R.slice();
 const q=$('q').value.trim().toLowerCase();if(q)rs=rs.filter(r=>r.agent.toLowerCase().includes(q));
 const mv=parseFloat($('minv').value);if(!isNaN(mv))rs=rs.filter(r=>r.value>=mv);
 const f=$('flt').value;if(f==='funded')rs=rs.filter(r=>r.value>0);else if(f==='profit')rs=rs.filter(r=>(winv(r)||0)>0);
 rs.sort((a,b)=>{const av=key==='ret_pct'?(winv(a)??-1e9):(a[key]??-1e9),bv=key==='ret_pct'?(winv(b)??-1e9):(b[key]??-1e9);return ((ranked(b)?1:0)-(ranked(a)?1:0))||((av-bv)*dir)||tb(a,b);});
 let html='',div=false;
 rs.forEach(r=>{if(LIVE&&!ranked(r)&&!div){html+='<div class="splitrow">Not scoring — needs ≥1 swap this UTC day AND ≥$1 in-scope balance</div>';div=true;}html+=rowHTML(r);});
 $('rows').innerHTML=html||'<div style="padding:22px;text-align:center;color:var(--mut)">no agents match</div>';}
$('q').oninput=render;$('minv').oninput=render;
$('flt').onchange=render;
(function(){const sel=$('wins');for(let n=1;n<=7;n++){const st=Date.UTC(2026,5,21+n),o=sel.querySelector('option[value="d'+n+'"]');if(o&&Date.now()<st){o.disabled=true;o.textContent+=' · soon';}}})();
$('wins').onchange=()=>{WIN=$('wins').value;ranks();stats();render();};
ranks();stats();render();
</script></body></html>"""

html = TEMPLATE.replace("/*DATA*/", json.dumps(D))
os.makedirs(os.path.dirname(out), exist_ok=True)
open(out, "w").write(html)
print("wrote", out, "(", len(html), "bytes,", len(D.get("rows", [])), "rows )")
