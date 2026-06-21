#!/usr/bin/env python3
"""Render leaderboard.json into a BNB-Hack-styled static page (Cloudflare/GitHub Pages).
  python scripts/build_leaderboard.py <leaderboard.json> <out.html>
"""
import json, sys, time

src = sys.argv[1] if len(sys.argv) > 1 else "dashboard/leaderboard.json"
out = sys.argv[2] if len(sys.argv) > 2 else "leaderboard-site/public/index.html"
D = json.load(open(src))
D["built_ts"] = int(time.time())
for r in D.get("rows", []):       # public, neutral: never reveal which agent is ours
    r.pop("ours", None)

TEMPLATE = r"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta http-equiv="refresh" content="120"/>
<title>BNB Hack · Track 1 Live Leaderboard</title>
<style>
:root{--bg:#0b0e11;--card:#161a1e;--line:rgba(255,255,255,.06);--gold:#F0B90B;--gold2:#FCD535;
--g:#16c784;--r:#ea3943;--tx:#eaecef;--mut:#848e9c}
*{box-sizing:border-box;margin:0;padding:0}
body{background:radial-gradient(1200px 600px at 50% -10%,#1a1d22 0%,var(--bg) 55%);color:var(--tx);
font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;min-height:100vh;padding:26px 14px 60px}
.wrap{max-width:880px;margin:0 auto}
.hero{text-align:center;margin:6px 0 18px}
.kick{font:700 12px/1 ui-monospace,monospace;letter-spacing:.3em;color:var(--gold);text-transform:uppercase}
.h1{font:800 32px/1.05 sans-serif;margin:9px 0 6px;letter-spacing:-.5px}.h1 b{color:var(--gold)}
.spon{color:var(--mut);font-size:12.5px}
.cd{margin:12px auto 0;display:inline-block;background:var(--card);border:1px solid var(--line);
border-radius:999px;padding:7px 16px;font:600 13px/1 ui-monospace,monospace;color:var(--gold2)}
.cd b{color:var(--tx)}
.stats{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;margin:18px 0}
.st{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:11px 18px;text-align:center;min-width:96px}
.st .stv{font:800 19px/1 ui-monospace,monospace}.st .stk{color:var(--mut);font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;margin-top:5px}
.banner{background:linear-gradient(90deg,rgba(240,185,11,.12),rgba(240,185,11,.02));border:1px solid rgba(240,185,11,.25);
border-radius:12px;padding:11px 14px;margin:6px 0 16px;font-size:13px;color:var(--gold2);text-align:center}
.bad{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:0 0 18px}
.b{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:13px 14px}
.b .bl{font:700 10px/1 ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--mut)}
.b .bn{font:600 13px/1 ui-monospace,monospace;margin:7px 0 4px}.b .bv{font:800 15px/1 ui-monospace,monospace}
.tools{display:flex;gap:10px;align-items:center;margin:0 0 10px}
#q{flex:1;background:var(--card);border:1px solid var(--line);border-radius:10px;color:var(--tx);padding:9px 13px;font:14px ui-monospace,monospace}
#q::placeholder{color:var(--mut)}
#minv,#flt{background:var(--card);border:1px solid var(--line);border-radius:10px;color:var(--tx);padding:9px 11px;font:13px ui-monospace,monospace}
#minv{width:84px}
.ext{color:var(--mut);text-decoration:none;font-size:12px;flex:none;margin-left:auto}.ext:hover{color:var(--gold)}
.det{max-height:0;overflow:hidden;transition:max-height .25s ease;background:rgba(255,255,255,.02)}
.det.open{max-height:160px;border-bottom:1px solid var(--line)}
.dethold{display:flex;flex-wrap:wrap;gap:6px;padding:11px 16px}
.chip{background:rgba(255,255,255,.05);border:1px solid var(--line);border-radius:8px;padding:4px 9px;font:600 11px/1 ui-monospace,monospace;color:var(--mut)}
.chip b{color:var(--tx)}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;overflow:hidden}
.row{cursor:pointer}
.thead,.row{display:grid;grid-template-columns:38px 1.4fr 78px 86px 74px 66px 120px;align-items:center;gap:8px;padding:11px 16px}
.thead{border-bottom:1px solid var(--line);font:700 10.5px/1 ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--mut)}
.thead span{cursor:pointer;user-select:none}.thead span:hover{color:var(--tx)}
.thead .num,.row .num{text-align:right}
.row{border-bottom:1px solid var(--line);font-size:13px}.row:last-child{border:0}
.row .n{font:700 13px/1 ui-monospace,monospace;color:var(--mut);text-align:center}
.row .top1 .n,.row.r1 .n{color:var(--gold)}
.ag{display:flex;align-items:center;gap:9px;min-width:0}
.dot{width:20px;height:20px;border-radius:50%;flex:none}.adr{font:500 12.5px/1 ui-monospace,monospace;overflow:hidden;text-overflow:ellipsis}
.vv{font:700 13px/1 ui-monospace,monospace;text-align:right}
.pos{color:var(--g)}.neg{color:var(--r)}.zero{color:var(--mut)}
.dqwrap{height:6px;background:rgba(255,255,255,.07);border-radius:4px;overflow:hidden;flex:1}
.dqcell{display:flex;align-items:center;gap:7px}.dqv{font:600 11px/1 ui-monospace,monospace;color:var(--mut);width:40px;text-align:right}
.foot{text-align:center;color:var(--mut);font-size:12px;margin-top:22px;line-height:1.7}.foot b{color:var(--tx)}
@media(max-width:680px){.thead,.row{grid-template-columns:30px 1fr 70px 60px;}.spk,.c24,.dqcol{display:none}}
</style></head><body><div class="wrap">
<div class="hero">
  <div class="kick">BNB Hack · AI Trading Agent Edition</div>
  <div class="h1">Track 1 · <b>Live Leaderboard</b></div>
  <div class="spon">CoinMarketCap × Trust Wallet × BNB Chain · $24,000 · top 5 win</div>
  <div class="cd" id="cd"></div>
</div>
<div class="stats" id="stats"></div>
<div id="banner"></div>
<div class="bad" id="badges"></div>
<div class="tools">
  <input id="q" placeholder="search agent address…"/>
  <input id="minv" type="number" placeholder="min $"/>
  <select id="flt"><option value="all">All</option><option value="funded">Funded</option><option value="profit">In profit</option></select>
</div>
<div class="card">
  <div class="thead" id="thead"></div>
  <div id="rows"></div>
</div>
<div class="foot">
  Ranked by total return with a ~30% max-drawdown cap · built from on-chain data
  (competition contract + Multicall3 + CoinGecko). <b>Permissionless &amp; verifiable.</b><br>
  Updated <span id="upd"></span> · refreshes every ~30 min · community-built, not affiliated with organizers.
</div></div>
<script>
const D=/*DATA*/, R=D.rows||[], S=D.stats||{}, LIVE=D.has_baseline;
const $=id=>document.getElementById(id);
const short=a=>a.slice(0,6)+"…"+a.slice(-4);
const dot=a=>{let h=0;for(let i=2;i<10;i++)h=(h*31+a.charCodeAt(i))>>>0;return `hsl(${h%360} 70% 55%)`;};
const fmt=v=>"$"+(v>=1000?Math.round(v).toLocaleString():v.toFixed(2));
const pct=v=>v==null?'<span class="zero">—</span>':`<span class="${v>0?'pos':v<0?'neg':'zero'}">${v>0?'+':''}${v.toFixed(2)}%</span>`;
function spark(a){if(!a||a.length<2)return '';const w=72,h=20,mn=Math.min(...a),mx=Math.max(...a),rg=(mx-mn)||1;
 const p=a.map((v,i)=>`${(i/(a.length-1)*w).toFixed(1)},${(h-(v-mn)/rg*h).toFixed(1)}`).join(' ');
 return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><polyline points="${p}" fill="none" stroke="${a[a.length-1]>=a[0]?'var(--g)':'var(--r)'}" stroke-width="1.5"/></svg>`;}
function dq(dd){const p=Math.min(100,dd/30*100),c=p<40?'var(--g)':p<70?'var(--gold)':'var(--r)';
 return `<div class="dqcell"><div class="dqwrap"><div style="height:100%;width:${p}%;background:${c}"></div></div><span class="dqv">${dd.toFixed(0)}%</span></div>`;}

// countdown
const START=Date.UTC(2026,5,22),END=Date.UTC(2026,5,29);
function cd(){const n=Date.now();let t,l;if(n<START){t=START;l='Starts in';}else if(n<END){t=END;l='Time left';}else{$('cd').textContent='Competition ended';return;}
 const d=Math.max(0,t-n);$('cd').innerHTML=`${l}: <b>${Math.floor(d/864e5)}d ${Math.floor(d%864e5/36e5)}h ${Math.floor(d%36e5/6e4)}m</b>`;}
cd();setInterval(cd,60000);
$('upd').textContent=new Date(D.built_ts*1000).toUTCString().replace('GMT','UTC');

// field stats
$('stats').innerHTML=[['Agents',S.n],['Funded',S.funded],['Deployed',fmt(S.deployed||0)],
 LIVE?['In profit',S.in_profit]:null,LIVE?['Avg PnL',(S.avg_ret>=0?'+':'')+S.avg_ret+'%']:null,
 LIVE?['Survivors',S.survivors+'/'+S.n]:null].filter(Boolean)
 .map(([k,v])=>`<div class="st"><div class="stv">${v}</div><div class="stk">${k}</div></div>`).join('');

if(!LIVE){$('banner').className='banner';$('banner').innerHTML='⏳ <b>Competition starts Jun 22, 00:00 UTC.</b> Live ranking by total return begins then; showing registered agents + funding for now.';}

// badges (need movement data)
const funded=R.filter(r=>r.value>0);
function pick(arr,key,dir){return arr.slice().sort((a,b)=>((b[key]??-1e9)-(a[key]??-1e9))*dir)[0];}
if(funded.length){
 const topR=pick(funded,'ret_pct',1),topM=pick(funded,'chg24h',1),safe=funded.slice().sort((a,b)=>a.dd_pct-b.dd_pct)[0];
 const card=(l,r,v)=>`<div class="b"><div class="bl">${l}</div><div class="bn"><span class="dot" style="display:inline-block;background:${dot(r.agent)};vertical-align:middle"></span> ${short(r.agent)}</div><div class="bv">${v}</div></div>`;
 const cards=[];
 if(LIVE&&topR&&topR.ret_pct!=null)cards.push(card('🥇 Top return',topR,pct(topR.ret_pct)));
 if(topM&&topM.chg24h!=null)cards.push(card('🔥 Top mover 24h',topM,pct(topM.chg24h)));
 if(LIVE&&safe)cards.push(card('🛡️ Lowest drawdown',safe,safe.dd_pct.toFixed(1)+'%'));
 $('badges').innerHTML=cards.join('');
}

// table
let key=LIVE?'ret_pct':'value',dir=-1;
const cols=[['#','rank',1],['Agent','agent',0],['Chart','',0,'spk'],['Value','value',1],['PnL','ret_pct',1],['24h','chg24h',1,'c24'],['DQ risk','dd_pct',1,'dqcol']];
$('thead').innerHTML=cols.map(c=>`<span class="${c[2]?'num':''} ${c[3]||''}" data-k="${c[1]}">${c[0]}</span>`).join('');
$('thead').querySelectorAll('span[data-k]').forEach(el=>{const k=el.dataset.k;if(k)el.onclick=()=>{dir=(key===k)?-dir:-1;key=k;render();};});
function rowHTML(r){
 const h=(r.holds||[]).map(x=>`<span class="chip">${x[0]} <b>$${x[1]}</b></span>`).join('')||'<span class="chip">no in-scope holdings</span>';
 return `<div class="rw"><div class="row ${r.rank<=3?'r'+r.rank:''}" onclick="this.nextElementSibling.classList.toggle('open')">
  <div class="n">${r.rank}</div>
  <div class="ag"><span class="dot" style="background:${dot(r.agent)}"></span><span class="adr">${short(r.agent)}</span>
   <a class="ext" href="https://bscscan.com/address/${r.agent}" target="_blank" rel="noopener" onclick="event.stopPropagation()">↗</a></div>
  <div class="spk">${spark(r.spark)}</div>
  <div class="vv">${fmt(r.value)}</div>
  <div class="vv">${pct(r.ret_pct)}</div>
  <div class="vv c24">${pct(r.chg24h)}</div>
  <div class="dqcol">${dq(r.dd_pct||0)}</div></div>
  <div class="det"><div class="dethold">${h}</div></div></div>`;}
function render(){let rs=R.slice();
 const q=$('q').value.trim().toLowerCase();if(q)rs=rs.filter(r=>r.agent.toLowerCase().includes(q));
 const mv=parseFloat($('minv').value);if(!isNaN(mv))rs=rs.filter(r=>r.value>=mv);
 const f=$('flt').value;if(f==='funded')rs=rs.filter(r=>r.value>0);else if(f==='profit')rs=rs.filter(r=>(r.ret_pct||0)>0);
 rs.sort((a,b)=>((a[key]??-1e9)-(b[key]??-1e9))*dir);
 $('rows').innerHTML=rs.map(rowHTML).join('')||'<div style="padding:18px;text-align:center;color:var(--mut)">no agents match</div>';}
$('q').oninput=render;$('minv').oninput=render;$('flt').onchange=render;render();
</script></body></html>"""

html = TEMPLATE.replace("/*DATA*/", json.dumps(D))
import os
os.makedirs(os.path.dirname(out), exist_ok=True)
open(out, "w").write(html)
print("wrote", out, "(", len(html), "bytes,", len(D.get("rows", [])), "rows )")
