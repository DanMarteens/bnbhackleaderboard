#!/usr/bin/env python3
"""Render leaderboard.json into a BNB-Hack-styled static page (Cloudflare-hosted).
  python scripts/build_leaderboard.py <leaderboard.json> <out.html>
"""
import json, sys, time

src = sys.argv[1] if len(sys.argv) > 1 else "dashboard/leaderboard.json"
out = sys.argv[2] if len(sys.argv) > 2 else "leaderboard-site/public/index.html"
D = json.load(open(src))
D["built_ts"] = int(time.time())
# public, neutral leaderboard: never reveal which agent is ours
for r in D.get("rows", []):
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
font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;min-height:100vh;padding:28px 16px 60px}
.wrap{max-width:760px;margin:0 auto}
.hero{text-align:center;margin:8px 0 24px}
.kick{font:700 12px/1 ui-monospace,monospace;letter-spacing:.32em;color:var(--gold);text-transform:uppercase}
.h1{font:800 34px/1.05 -apple-system,sans-serif;margin:10px 0 6px;letter-spacing:-.5px}
.h1 b{color:var(--gold)}
.sub{color:var(--mut);font-size:13px}
.banner{background:linear-gradient(90deg,rgba(240,185,11,.12),rgba(240,185,11,.02));border:1px solid rgba(240,185,11,.25);
border-radius:12px;padding:11px 14px;margin:18px 0;font-size:13px;color:var(--gold2);text-align:center}
.me{display:flex;align-items:center;gap:14px;background:linear-gradient(90deg,rgba(240,185,11,.16),rgba(240,185,11,.03));
border:1px solid rgba(240,185,11,.4);border-radius:16px;padding:16px 18px;margin:14px 0 22px}
.me .rk{font:800 30px/1 ui-monospace,monospace;color:var(--gold)}
.me .lab{color:var(--gold2);font-size:11px;letter-spacing:.2em;text-transform:uppercase}
.me .val{margin-left:auto;text-align:right}
.me .val b{font:800 22px/1 ui-monospace,monospace}
.pod{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin:0 0 22px}
.p{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px 12px;text-align:center}
.p.first{border-color:rgba(240,185,11,.5);transform:translateY(-6px)}
.p .md{font-size:22px}.p .a{font:600 12px/1 ui-monospace,monospace;color:var(--mut);margin:6px 0}
.p .v{font:800 18px/1 ui-monospace,monospace}.p .rt{font:700 13px/1;margin-top:5px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;overflow:hidden}
.ph{display:flex;justify-content:space-between;align-items:center;padding:14px 18px;border-bottom:1px solid var(--line);
font:700 12px/1 ui-monospace,monospace;letter-spacing:.18em;text-transform:uppercase;color:var(--mut)}
.row{display:flex;align-items:center;gap:12px;padding:12px 18px;border-bottom:1px solid var(--line)}
.row:last-child{border:0}
.row.mine{background:rgba(240,185,11,.08)}
.row .n{width:30px;font:700 14px/1 ui-monospace,monospace;color:var(--mut);text-align:center;flex:none}
.row .dot{width:22px;height:22px;border-radius:50%;flex:none}
.row .ad{font:500 13px/1 ui-monospace,monospace;flex:1}
.row .you{font:700 9px/1;background:var(--gold);color:#000;border-radius:5px;padding:3px 6px;letter-spacing:.1em;margin-left:8px}
.row .vv{font:700 14px/1 ui-monospace,monospace;width:90px;text-align:right}
.row .rr{font:700 13px/1 ui-monospace,monospace;width:78px;text-align:right}
.pos{color:var(--g)}.neg{color:var(--r)}.zero{color:var(--mut)}
.foot{text-align:center;color:var(--mut);font-size:12px;margin-top:24px;line-height:1.7}
.foot b{color:var(--tx)}
</style></head><body><div class="wrap">
<div class="hero">
  <div class="kick">BNB Hack · AI Trading Agent Edition</div>
  <div class="h1">Track 1 · <b>Live Leaderboard</b></div>
  <div class="sub" id="sub"></div>
</div>
<div id="banner"></div>
<div class="pod" id="pod"></div>
<div class="card"><div class="ph"><span>Rank</span><span>Portfolio · PnL</span></div><div id="rows"></div></div>
<div class="foot">
  Scored by total return with a ~30% max-drawdown cap · CoinMarketCap × Trust Wallet × BNB Chain<br>
  Built from on-chain data (competition contract + Multicall3). <b>Permissionless & verifiable.</b>
</div>
</div>
<script>
const D=/*DATA*/;
const $=id=>document.getElementById(id);
const short=a=>a.slice(0,6)+"…"+a.slice(-4);
const dot=a=>{let h=0;for(let i=2;i<10;i++)h=(h*31+a.charCodeAt(i))>>>0;return `hsl(${h%360} 70% 55%)`;};
const fmt=v=>"$"+(v>=1000?v.toLocaleString(undefined,{maximumFractionDigits:0}):v.toFixed(2));
const ret=r=>r==null?'<span class="zero">—</span>':`<span class="${r>0?'pos':r<0?'neg':'zero'}">${r>0?'+':''}${r.toFixed(2)}%</span>`;
const rows=D.rows||[];
const upd=new Date(D.built_ts*1000).toUTCString().replace('GMT','UTC');
if(!D.has_baseline){
  // PRE-COMPETITION: ranking is by total return, which only starts at go-live.
  // Show a neutral roster of registered agents — no podium, no standings, no $.
  $('sub').textContent=`updated ${upd}`;
  $('banner').className='banner';
  $('banner').innerHTML='⏳ <b>Competition starts Jun 22, 00:00 UTC.</b> Live ranking by total return begins then.';
  $('pod').style.display='none';
  document.querySelector('.ph').innerHTML='<span>Registered agents</span><span>funding (public)</span>';
  $('rows').innerHTML=rows.slice().sort((a,b)=>b.value-a.value).map(r=>
    `<div class="row"><div class="dot" style="background:${dot(r.agent)}"></div>
     <div class="ad">${short(r.agent)}</div>
     <div class="vv">${fmt(r.value)}</div></div>`).join('');
}else{
  // LIVE: rank by total return (%).
  $('sub').textContent=`${D.n} autonomous agents · ranked by total return · updated ${upd}`;
  const md=['🥇','🥈','🥉'];
  $('pod').innerHTML=rows.slice(0,3).map((r,i)=>
    `<div class="p ${i==0?'first':''}"><div class="md">${md[i]}</div><div class="a">${short(r.agent)}</div>
     <div class="v">${fmt(r.value)}</div><div class="rt">${ret(r.ret_pct)}</div></div>`).join('');
  $('rows').innerHTML=rows.map(r=>
    `<div class="row"><div class="n">${r.rank}</div>
     <div class="dot" style="background:${dot(r.agent)}"></div>
     <div class="ad">${short(r.agent)}</div>
     <div class="vv">${fmt(r.value)}</div><div class="rr">${ret(r.ret_pct)}</div></div>`).join('');
}
</script></body></html>"""

html = TEMPLATE.replace("/*DATA*/", json.dumps(D))
import os
os.makedirs(os.path.dirname(out), exist_ok=True)
open(out, "w").write(html)
print("wrote", out, "(", len(html), "bytes,", len(D["rows"]), "rows )")
