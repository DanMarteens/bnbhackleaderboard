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
 radial-gradient(820px 480px at 9% -8%,rgba(240,185,11,.11),transparent 56%),
 radial-gradient(720px 560px at 48% -2%,rgba(155,107,255,.09),transparent 55%),
 radial-gradient(840px 620px at 93% 3%,rgba(56,97,251,.12),transparent 55%),
 radial-gradient(760px 760px at 50% 120%,rgba(63,208,224,.07),transparent 60%),
 var(--bg);background-attachment:fixed;padding:30px 16px 64px}
.wrap{max-width:980px;margin:0 auto}
.glass{background:var(--glass);backdrop-filter:blur(24px) saturate(155%);-webkit-backdrop-filter:blur(24px) saturate(155%);
 border:1px solid var(--line);border-radius:20px;box-shadow:var(--shadow),inset 0 1px 0 rgba(255,255,255,.06)}
.hero{margin:0 0 22px}
.herohead{display:flex;align-items:flex-end;justify-content:space-between;gap:18px}
.mark{font:800 12px/1 "Inter";letter-spacing:.16em;text-transform:uppercase;color:var(--gold2)}
.ed{margin-top:8px;font:700 9.5px/1 var(--mono);letter-spacing:.22em;text-transform:uppercase;color:var(--mut)}
.h1{font:850 36px/1.02 "Inter";letter-spacing:-1.35px;margin:12px 0 7px;
 background:linear-gradient(180deg,#fff,#c4c9d2);-webkit-background-clip:text;background-clip:text;color:transparent}
.h1 b{background:linear-gradient(135deg,var(--gold2),var(--gold));-webkit-background-clip:text;background-clip:text;color:transparent}
.spon{color:var(--mut);font-size:13px}
.cd{display:inline-flex;gap:9px;align-items:center;padding:10px 14px;border-radius:999px;white-space:nowrap;
 font:600 13px/1 var(--mono);color:var(--gold2);background:var(--glass);border:1px solid var(--line);
 backdrop-filter:blur(12px);box-shadow:inset 0 1px 0 rgba(255,255,255,.05)}
.cd::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--g);box-shadow:0 0 10px var(--g);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}.cd b{color:#fff}
.stats{display:flex;gap:8px;margin:18px 0 16px;flex-wrap:wrap}
.st{display:flex;align-items:baseline;gap:8px;padding:9px 12px;background:rgba(255,255,255,.035);border:1px solid var(--line);border-radius:999px;
 backdrop-filter:blur(20px);box-shadow:inset 0 1px 0 rgba(255,255,255,.05)}
.st .v{font:800 15px/1 "Inter";letter-spacing:-.25px;color:#fff}
.st .k{color:var(--mut);font-size:9px;letter-spacing:.12em;text-transform:uppercase;order:-1}
.banner{padding:13px 16px;margin:0 0 18px;font-size:13px;color:var(--gold2);text-align:left;border-radius:16px;
 background:linear-gradient(90deg,rgba(240,185,11,.1),rgba(240,185,11,.02));border:1px solid rgba(240,185,11,.25)}
.bad{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:0 0 22px}
.b{padding:16px;background:var(--glass);border:1px solid var(--line);border-radius:18px;backdrop-filter:blur(20px);
 box-shadow:inset 0 1px 0 rgba(255,255,255,.05);transition:transform .2s}.b:hover{transform:translateY(-3px)}
.b .bl{font:600 10px/1 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--mut)}
.b .bn{font:600 13px/1 var(--mono);margin:10px 0 6px;display:flex;align-items:center;gap:7px}
.b .bv{font:800 18px/1 "Inter"}
.tools{display:flex;gap:8px;align-items:center;margin:18px 0 12px;flex-wrap:wrap;padding:8px;background:rgba(255,255,255,.028);border:1px solid var(--line);border-radius:20px;backdrop-filter:blur(18px)}
.wbar{display:flex;align-items:center;gap:12px;margin:0 0 14px;flex-wrap:wrap}
.wl{font:600 10.5px/1 var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--mut)}
.inp{background:rgba(255,255,255,.035);border:1px solid rgba(140,160,255,.1);border-radius:14px;color:var(--txt);padding:11px 14px;
 font:14px "Inter";backdrop-filter:blur(14px);outline:none;transition:.2s;box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}
.inp::placeholder{color:var(--mut)}.inp:focus{border-color:rgba(240,185,11,.6);box-shadow:0 0 0 3px rgba(240,185,11,.13)}
#q{flex:1;min-width:170px}#minv{width:118px}#minv::-webkit-outer-spin-button,#minv::-webkit-inner-spin-button{-webkit-appearance:none}
.seg{display:inline-flex;background:var(--glass);border:1px solid var(--line);border-radius:14px;padding:4px;gap:3px;backdrop-filter:blur(14px)}
.seg button{border:0;background:transparent;color:var(--mut);font:600 13px "Inter";padding:9px 15px;border-radius:11px;cursor:pointer;transition:.18s}
.seg button:hover{color:var(--txt)}
.seg button.on{background:linear-gradient(135deg,var(--gold2),var(--gold));color:#0a0a0a;box-shadow:0 4px 16px rgba(240,185,11,.35)}
.selwrap{position:relative;display:inline-block}
.selwrap::after{content:"▾";position:absolute;right:14px;top:50%;transform:translateY(-50%);color:var(--mut);pointer-events:none;font-size:11px}
.sel{appearance:none;-webkit-appearance:none;background:rgba(255,255,255,.035);border:1px solid rgba(140,160,255,.1);border-radius:14px;color:var(--txt);padding:11px 36px 11px 14px;font:14px "Inter";backdrop-filter:blur(14px);cursor:pointer;outline:none;transition:.2s}
.sel:focus{border-color:rgba(56,97,251,.6);box-shadow:0 0 0 3px rgba(56,97,251,.13)}
.sel option{background:#0d1430;color:var(--txt)}
.tbl{overflow:hidden;background:rgba(255,255,255,.035);border:1px solid var(--line);border-radius:22px;backdrop-filter:blur(24px);box-shadow:0 18px 60px rgba(0,0,0,.42),inset 0 1px 0 rgba(255,255,255,.06)}
.thead,.row{display:grid;grid-template-columns:46px 1.55fr 112px 116px 128px 130px;align-items:center;gap:11px;padding:14px 18px}
.pnlcol{font-weight:800;font-size:15.5px}.thead .pnlcol{font-weight:700;font-size:10.5px}
.thead{border-bottom:1px solid var(--line);font:600 10.5px/1 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--mut)}
.thead span{cursor:pointer;transition:.15s}.thead span:hover{color:var(--gold2)}
.thead .num,.row .num{text-align:right}
.rw{border-bottom:1px solid rgba(255,255,255,.05)}.rw:last-child{border:0}
.row{position:relative;cursor:pointer;transition:background .15s,box-shadow .15s,transform .15s}.row:hover{background:rgba(255,255,255,.035)}
.row.r1,.row.r2,.row.r3,.row.r4,.row.r5{background:linear-gradient(90deg,rgba(240,185,11,.075),rgba(240,185,11,.018) 42%,transparent 78%);
 box-shadow:inset 3px 0 0 rgba(240,185,11,.72),inset 0 1px 0 rgba(255,255,255,.035)}
.row.r1{padding-top:20px;padding-bottom:20px;background:
 radial-gradient(260px 80px at 14% 0%,rgba(252,213,53,.16),transparent 72%),
 linear-gradient(90deg,rgba(240,185,11,.13),rgba(240,185,11,.03) 45%,transparent 80%);
 box-shadow:inset 4px 0 0 var(--gold),inset 0 1px 0 rgba(255,255,255,.07)}
.row.r1:hover,.row.r2:hover,.row.r3:hover,.row.r4:hover,.row.r5:hover{background-color:rgba(240,185,11,.025)}
.row.r1 .dot{width:28px;height:28px}.row.r1 .adr{font-weight:700;font-size:13.5px}.row.r1 .vv{font-size:14px}
.podtag{font:700 8px/1 var(--mono);letter-spacing:.12em;text-transform:uppercase;color:var(--gold2);
 border:1px solid rgba(240,185,11,.32);background:rgba(240,185,11,.09);border-radius:999px;padding:4px 7px;margin-left:7px;white-space:nowrap}
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
.tradebox{display:flex;align-items:baseline;justify-content:flex-end;gap:7px}
.tradebox .tot{font:800 13px/1 var(--mono)}
.days{font:700 10px/1 var(--mono);color:var(--mut);white-space:nowrap}
.days .miss{color:var(--r)}
.det{max-height:0;overflow:hidden;transition:max-height .3s ease}.det.open{max-height:200px}
.dethold{display:flex;flex-wrap:wrap;gap:7px;padding:2px 18px 15px}
.chip{background:var(--glass2);border:1px solid var(--line);border-radius:10px;padding:5px 11px;font:600 11px/1 var(--mono);color:var(--mut)}
.chip b{color:var(--gold2)}
.foot{color:var(--mut);font-size:12px;margin-top:18px;line-height:1.8;border:1px solid var(--line);border-radius:18px;background:rgba(255,255,255,.026);padding:0 14px}
.foot summary{cursor:pointer;list-style:none;padding:13px 0;color:var(--txt);font-weight:700}.foot summary::-webkit-details-marker{display:none}
.foot summary::after{content:"▾";float:right;color:var(--mut);transition:.15s}.foot[open] summary::after{transform:rotate(180deg)}
.foot .fbody{border-top:1px solid rgba(255,255,255,.06);padding:12px 0 14px;text-align:left}.foot b{color:var(--txt)}
.foot .fline{margin:7px 0}.foot .by{margin-top:12px}
.foot a{color:var(--gold2);text-decoration:none}.foot a:hover{text-decoration:underline}
.by{margin-top:6px;font-size:12.5px}
@media(max-width:680px){body{padding:22px 10px 52px}.herohead{display:block}.cd{margin-top:14px}.mark{font-size:11px}.h1{font-size:30px}.stats{gap:7px}.st{padding:8px 10px}.bad{grid-template-columns:1fr}
 .tools{flex-direction:column;align-items:stretch}.selwrap,.sel{width:100%}#minv{width:100%}.thead{display:none}
 .tbl{border-radius:18px}.row{grid-template-columns:28px minmax(0,1fr) auto;grid-template-areas:"rank agent value" "rank pnl pnl" "rank trades dd";
  gap:8px 10px;padding:13px 12px;align-items:center}.row .n{grid-area:rank;align-self:start;padding-top:3px}.row .ag{grid-area:agent}
 .valcol{grid-area:value;white-space:nowrap}.pnlcol{grid-area:pnl}.trcol{grid-area:trades}.ddcol{grid-area:dd}
 .pnlcol,.trcol,.ddcol{display:inline-flex!important;align-items:center;gap:7px;justify-content:flex-start;text-align:left;font-size:12px;color:var(--txt)}
 .pnlcol::before{content:"PNL";color:var(--mut);font:700 9px/1 var(--mono);letter-spacing:.1em}.trcol::before{content:"TRADES";color:var(--mut);font:700 9px/1 var(--mono);letter-spacing:.1em}
 .ddcol::before{content:"DD";color:var(--mut);font:700 9px/1 var(--mono);letter-spacing:.1em}.dqv{text-align:left;width:auto}.det.open{max-height:260px}
 .tradebox{justify-content:flex-start}.days{font-size:9.5px}
 .dethold{padding:0 12px 13px 50px}.chip{font-size:10px;padding:5px 9px}}
</style></head><body><div class="wrap">
<div class="hero">
  <div class="herohead">
    <div>
      <div class="mark">BNB Hack</div>
      <div class="ed">AI Trading Agent Edition</div>
      <div class="h1">Track 1 · <b>Live Leaderboard</b></div>
      <div class="spon">CoinMarketCap × Trust Wallet × BNB Chain · $24,000 · top 5 win</div>
    </div>
    <div class="cd" id="cd"></div>
  </div>
</div>
<div class="stats" id="stats"></div>
<div id="banner"></div>
<div class="tools">
  <input id="q" class="inp" placeholder="search agent address…"/>
  <input id="minv" class="inp" type="number" placeholder="min $"/>
  <div class="selwrap"><select id="flt" class="sel">
    <option value="all">all agents</option>
    <option value="top5">prize zone</option>
    <option value="scoring">scoring only</option>
    <option value="funded">funded only</option>
    <option value="profit">in profit</option>
    <option value="risk_ok">drawdown ok</option>
    <option value="risk_dq">drawdown DQ</option>
    <option value="not_scoring">not scoring</option>
  </select></div>
</div>
<div class="tbl"><div class="thead" id="thead"></div><div id="rows"></div></div>
<details class="foot"><summary>Scoring methodology · updated <span id="upd"></span></summary>
  <div class="fbody">
    <div class="fline">Built from on-chain data · <b>permissionless &amp; verifiable</b>.</div>
    <div class="fline">Strict trade = eligible token in + eligible token out in the same transaction. Deposits, withdrawals and BNB conversions never count as trades.</div>
    <div class="fline">PnL uses transaction-time capital cost basis and a liquid BSC DEX guard for divergent CMC marks. ⚖ marks a guarded token.</div>
    <div class="fline">Execution price, DEX fees and slippage are already reflected on-chain. Additional organizer simulated-cost rate is shown as 0 until an official rate is published.</div>
    <div class="fline">Drawdown is observed max peak-to-trough on the eligible portfolio curve, rebased on external capital flows. Click any row to expand token holdings.</div>
    <div class="fline">Refreshes every ~30 min · not affiliated with organizers.</div>
    <div class="by">built by <b><a href="https://x.com/itsabigdill" target="_blank" rel="noopener">@itsabigdill</a></b>
     · <a href="https://github.com/DanMarteens" target="_blank" rel="noopener">github</a>
     · <a href="https://cto.monster" target="_blank" rel="noopener">cto.monster</a></div>
  </div>
</details>
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
function tradeDays(r){const ds=(r.daily_trades||[]).slice(0,7);
 if(!LIVE||!ds.length)return `<div class="tradebox"><span class="tot">${r.trades||0}</span></div>`;
 const seq=ds.map(n=>n>0?String(n):'<span class="miss">0</span>').join('/');
 return `<div class="tradebox" title="Strict eligible-token swaps by UTC day: ${ds.map((n,i)=>'D'+(i+1)+'='+n).join(', ')}"><span class="tot">${r.trades||0}</span><span class="days">${seq}</span></div>`;}
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
// A wallet is ranked only after a strict eligible-token swap on every required UTC day
// since its capital entered the competition, and while it holds >$1 in-scope.
const RANK_MIN_USD=1.0;
const ranked=r=>!LIVE||(r.eligible!==false&&r.traded&&r.value>RANK_MIN_USD&&(r.dd_pct||0)<(S.dq_pct||30));
const rankSort=(a,b)=>((ranked(b)?1:0)-(ranked(a)?1:0))||((winv(b)??-1e9)-(winv(a)??-1e9))||tb(a,b);
function ranks(){let i=0;R.slice().sort(rankSort).forEach(r=>{r._rk=ranked(r)?(++i):null;});}
function stats(){const rankedNow=R.filter(r=>ranked(r)).length;
 $('stats').innerHTML=[LIVE?['Ranked',rankedNow+'/'+S.n]:['Agents',S.n],
  LIVE&&S.trading!=null?['Daily-qualified',S.trading+'/'+S.n]:null,
  ['Capital',fmt(S.deployed||0)],
  LIVE?['In profit',R.filter(r=>(winv(r)||0)>0).length]:null,
  LIVE?['DQ line',(S.dq_pct||30)+'%']:null].filter(Boolean)
  .map(([k,v])=>`<div class="st"><div class="v">${v}</div><div class="k">${k}</div></div>`).join('');}
if(!LIVE){$('banner').className='banner';$('banner').innerHTML='⏳ <b>Competition starts Jun 22, 00:00 UTC.</b> Live ranking by total return begins then; showing registered agents + funding for now.';}
const cols=[['#','rank',1],['Agent','agent',0],['Value','value',1],['PnL','ret_pct',1,'pnlcol'],['Trades','trades',1,'trcol'],['Drawdown','dd_pct',1,'ddcol']];
$('thead').innerHTML=cols.map(c=>`<span class="${c[2]?'num':''} ${c[3]||''}" data-k="${c[1]}">${c[0]}</span>`).join('');
$('thead').querySelectorAll('span[data-k]').forEach(el=>{const k=el.dataset.k;if(k)el.onclick=()=>{dir=(key===k)?-dir:-1;key=k;render();};});
function rowHTML(r){const pf=new Set(r.price_flags||[]);
 const h=(r.holds||[]).map(x=>`<span class="chip">${x[0]}${pf.has(x[0])?' ⚖':''} <b>$${x[1]}</b></span>`).join('')||'<span class="chip">no in-scope holdings</span>';
 const notRanked=LIVE&&!ranked(r);
 const noTrade=!(r.trades||0);
 const missing=(r.missing_days||[]);
 const tag=!notRanked?'':(r.eligible===false?'no capital':((r.dd_pct||0)>=(S.dq_pct||30)?'drawdown DQ':(!r.traded?(noTrade?'no eligible swaps':`missing day ${missing.join(',')}`):'under $1')));
 return `<div class="rw"><div class="row ${STARTED&&ranked(r)&&r._rk<=5?'r'+r._rk:''} ${notRanked?'idlerow':''}" onclick="this.nextElementSibling.classList.toggle('open')">
  <div class="n">${r._rk==null?'·':r._rk}</div>
  <div class="ag"><span class="dot" style="background:${dot(r.agent)}"></span><span class="adr">${short(r.agent)}</span>
   ${STARTED&&ranked(r)&&WIN==='all'&&r._rk===1?`<span class="podtag">leader</span>`:''}
   ${STARTED&&ranked(r)&&WIN==='all'&&PRIZE[r._rk]?`<span class="prize">${PRIZE[r._rk]}</span>`:''}
   ${tag?`<span class="idle" title="${r.eligible===false?'not funded with eligible capital':'not scoring: requires a strict eligible-token swap on every active UTC day and >=$1 in-scope'}">${tag}</span>`:''}
   <a class="ext" href="https://bscscan.com/address/${r.agent}" target="_blank" rel="noopener" onclick="event.stopPropagation()">↗</a></div>
  <div class="vv valcol">${fmt(r.value)}</div><div class="vv pnlcol">${pct(winv(r))}</div>
  <div class="vv trcol ${LIVE&&!r.traded?'neg':''}">${tradeDays(r)}</div><div class="vv ddcol" title="observed max peak-to-trough drawdown">${dq(r.dd_pct||0)}</div></div>
  <div class="det"><div class="dethold">${h}</div></div></div>`;}
function render(){let rs=R.slice();
 const q=$('q').value.trim().toLowerCase();if(q)rs=rs.filter(r=>r.agent.toLowerCase().includes(q));
 const mv=parseFloat($('minv').value);if(!isNaN(mv))rs=rs.filter(r=>r.value>=mv);
 const f=$('flt').value;
 if(f==='top5')rs=rs.filter(r=>ranked(r)&&r._rk<=5);
 else if(f==='scoring')rs=rs.filter(r=>ranked(r));
 else if(f==='funded')rs=rs.filter(r=>r.value>0);
 else if(f==='profit')rs=rs.filter(r=>(winv(r)||0)>0);
 else if(f==='risk_ok')rs=rs.filter(r=>(r.dd_pct||0)<(S.dq_pct||30));
 else if(f==='risk_dq')rs=rs.filter(r=>(r.dd_pct||0)>=(S.dq_pct||30));
 else if(f==='not_scoring')rs=rs.filter(r=>LIVE&&!ranked(r));
 rs.sort((a,b)=>{const av=key==='ret_pct'?(winv(a)??-1e9):(a[key]??-1e9),bv=key==='ret_pct'?(winv(b)??-1e9):(b[key]??-1e9);return ((ranked(b)?1:0)-(ranked(a)?1:0))||((av-bv)*dir)||tb(a,b);});
 let html='',div=false;
 rs.forEach(r=>{if(LIVE&&!ranked(r)&&!div){html+='<div class="splitrow">Not scoring — daily swap, capital, $1 minimum, or drawdown gate not satisfied</div>';div=true;}html+=rowHTML(r);});
 $('rows').innerHTML=html||'<div style="padding:22px;text-align:center;color:var(--mut)">no agents match</div>';}
$('q').oninput=render;$('minv').oninput=render;
$('flt').onchange=render;
ranks();stats();render();
</script></body></html>"""

html = TEMPLATE.replace("/*DATA*/", json.dumps(D))
os.makedirs(os.path.dirname(out), exist_ok=True)
open(out, "w").write(html)
print("wrote", out, "(", len(html), "bytes,", len(D.get("rows", [])), "rows )")
