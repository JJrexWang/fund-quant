// 基金量化分析系统 v1 前端
const $ = s => document.querySelector(s);
const API = "/api";
let token = localStorage.getItem("fq_token") || "";
let me = null;
const fmt = (v, d=2) => v === null || v === undefined || v === "" ? "—" : Number(v).toFixed(d);
const pct = v => v === null || v === undefined ? "—" : (v >= 0 ? "+" : "") + Number(v).toFixed(2) + "%";
const cls = v => v === null || v === undefined ? "" : (v >= 0 ? "up" : "down");
function toast(msg){ const t=$("#toast"); t.textContent=msg; t.style.display="block"; setTimeout(()=>t.style.display="none",2600); }
async function api(path, opts={}){
  const r = await fetch(API+path, {...opts, headers:{"Content-Type":"application/json","Authorization":"Bearer "+token, ...(opts.headers||{})}});
  if(r.status===401){ logout(); throw new Error("未登录"); }
  const data = await r.json().catch(()=>({}));
  if(!r.ok) throw new Error(data.detail || ("请求失败 "+r.status));
  return data;
}
function applyMe(){
  if(!me) return;
  $("#tb-user").textContent = me.username+" ("+me.role+")";
  const nu = $("#nav-users"); if(nu) nu.style.display = me.role==="admin" ? "flex" : "none";
  const na = $("#nav-agents"); if(na) na.style.display = me.role==="admin" ? "flex" : "none";
}
function logout(){ token=""; localStorage.removeItem("fq_token"); $("#app").style.display="none"; $("#login").style.display="flex"; }
async function doLogin(){
  const u=$("#lg-user").value.trim(), p=$("#lg-pw").value;
  try{
    const r = await fetch(API+"/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:u,password:p})});
    const d = await r.json();
    if(!r.ok) throw new Error(d.detail||"登录失败");
    token=d.token; me=d; localStorage.setItem("fq_token",token);
    api("/me").then(u=>{ me=u; applyMe(); route(); }).catch(()=>{});
    $("#login").style.display="none"; $("#app").style.display="block";
    $("#tb-user").textContent = d.username+" ("+d.role+")";
    route();
  }catch(e){ $("#lg-err").textContent=e.message; }
}
$("#lg-btn").onclick = doLogin;
$("#lg-pw").addEventListener("keydown", e=>{ if(e.key==="Enter") doLogin(); });
$("#tb-out").onclick = logout;
$("#tb-pw").onclick = ()=>{
  const m = $("#modal");
  m.innerHTML = `<h3>修改密码</h3>
    <div class="f"><label>原密码</label><input id="pw-old" type="password"></div>
    <div class="f"><label>新密码(至少6位)</label><input id="pw-new" type="password"></div>
    <div style="display:flex;gap:8px;justify-content:flex-end"><button onclick="closeModal()">取消</button><button class="primary" id="pw-save">保存</button></div>`;
  $("#modal-bg").style.display="flex";
  $("#pw-save").onclick = async ()=>{
    try{
      await api("/me/password",{method:"POST",body:JSON.stringify({old_password:$("#pw-old").value,new_password:$("#pw-new").value})});
      closeModal(); toast("密码已修改, 下次登录生效"); me.using_default_password = $("#pw-new").value==="admin"; route();
    }catch(e){ toast(e.message); }
  };
};
$("#tb-q").addEventListener("keydown", e=>{
  if(e.key==="Enter"){ const q=e.target.value.trim(); if(q) location.hash="#/fund/"+encodeURIComponent(q); }
});
$("#tb-bell").onclick = async ()=>{
  const list = await api("/alerts");
  $("#alert-list").innerHTML = list.length ? list.map(a=>`
    <div class="alert-item"><b>${a.fund_code}</b> ${a.fund_name||""}<br>
    ${a.date} 触发 · 收益 <span class="up">${pct(a.ret_pct)}</span> · 净值 ${fmt(a.nav,4)}<br>
    ${a.contacted?'<span class="tag blue">已联系客户</span>':`<button onclick="markContacted(${a.id})">标记已联系客户</button>`}</div>`).join("") : '<p class="hint">暂无提醒</p>';
  $("#alert-drawer").classList.add("open");
};
async function markContacted(id){ await api(`/alerts/${id}/contacted`,{method:"POST"}); toast("已标记"); $("#tb-bell").click(); refreshBell(); }
async function refreshBell(){
  try{ const d = await api("/dashboard"); const n = d.alerts.filter(a=>!a.contacted).length;
    const el=$("#tb-bell-n"); el.style.display=n?"inline-block":"none"; el.textContent=n;
    if(d.regime && d.regime.regime) $("#tb-regime").textContent = "市场状态 · "+d.regime.regime;
  }catch(e){}
}
// ---------- 路由 ----------
function route(){
  const h = location.hash || "#/dashboard";
  const [_, page, arg] = h.split("/");
  document.querySelectorAll("#nav a").forEach(a=>a.classList.toggle("active", a.dataset.r===page));
  const c = $("#content");
  if(page==="dashboard") pageDashboard(c);
  else if(page==="watch") pageWatch(c);
  else if(page==="screening") pageScreening(c);
  else if(page==="industry") pageIndustry(c);
  else if(page==="system") pageSystem(c);
  else if(page==="users") pageUsers(c);
  else if(page==="agents") pageAgents(c);
  else if(page==="fund") pageFund(c, decodeURIComponent(arg||""));
  else pageDashboard(c);
}
window.addEventListener("hashchange", route);
// ---------- 仪表盘 ----------
async function pageDashboard(c){
  c.innerHTML = '<div class="panel">加载中…</div>';
  const d = await api("/dashboard");
  const rg = d.regime||{};
  const jobLine = Object.entries(d.last_jobs||{}).map(([k,v])=>`${k}: ${v.status} @ ${v.at||""}`).join(" · ");
  const pwWarn = (me && me.using_default_password) ? '<div class="banner warn">⚠️ <b>安全提醒</b>：当前账号正在使用默认密码「admin」，请点右上角「修改密码」尽快更换。</div>' : '';
  c.innerHTML = pwWarn + `
  <div class="cards">
    <div class="kpi"><div class="l">跟踪基金</div><div class="n">${d.watch_count}</div></div>
    <div class="kpi"><div class="l">已达目标(≥目标%)</div><div class="n" style="color:var(--red)">${d.hit_count}</div></div>
    <div class="kpi"><div class="l">回撤预警(≤-5%)</div><div class="n" style="color:var(--green)">${d.warn_down_count}</div></div>
    <div class="kpi"><div class="l">代销池基金</div><div class="n">${d.pool_count}</div></div>
  </div>
  <div class="banner"><b>市场状态：${rg.regime||"未判定"}</b> <span class="hint">${rg.basis||"等待 17:40 任务或在系统管理页手动运行"}（数据截至 ${rg.date||"—"}）</span></div>
  <div class="row">
    <div class="panel"><h3>今日达标提醒</h3>
      ${d.alerts.length? d.alerts.map(a=>`<p style="margin:6px 0">🔴 <a href="#/fund/${a.fund_code}"><b>${a.fund_code}</b> ${a.fund_name||""}</a> · ${a.date} · 收益 <span class="up">${pct(a.ret_pct)}</span> ${a.contacted?'<span class="tag blue">已联系</span>':""}</p>`).join("") : '<p class="hint">暂无达标提醒</p>'}
    </div>
    <div class="panel"><h3>申万一级行业 · 近1月涨幅 TOP5 / BOTTOM5 <span class="sub">${d.industry_updated? "更新于 "+d.industry_updated : "行业数据待更新(周六任务或手动运行)"}</span></h3>
      ${d.industry_top.length? [...d.industry_top.map(r=>[r,1]), ...d.industry_bottom.map(r=>[r,0])].map(([r])=>`<p style="margin:5px 0">${r.rank}. ${r.name} <span class="${cls(r.r1m)}" style="float:right">${pct(r.r1m)}</span></p>`).join("") : '<p class="hint">暂无行业数据</p>'}
    </div>
  </div>
  <div class="panel"><h3>数据新鲜度</h3><p class="hint">${jobLine||"尚无任务记录"} · 算法版本 ${d.algo_version}</p>
  <p class="src">来源：AkShare / 东方财富直连（免费公开数据）</p></div>`;
  refreshBell();
}
// ---------- 销售跟踪 ----------
let watchData = [];
async function pageWatch(c){
  c.innerHTML = `
  <div class="panel"><h3>销售跟踪 <span class="sub">填代码+销售日期+销售日净值，其余自动更新；收益率≥目标自动标红并产生提醒</span></h3>
    <div class="toolbar">
      <button class="primary" onclick="openWatchModal()">+ 新增记录</button>
      <button id="w-update">⟳ 立即更新净值</button>
      <select id="w-filter"><option value="">全部状态</option><option value="hit">只看达标</option><option value="warn_down">只看回撤预警</option><option value="tracking">跟踪中</option></select>
      <span class="sp"></span><span class="hint">每个交易日 21:35 自动更新；QDII 净值 T+2 属正常</span>
    </div>
    <div style="overflow:auto"><table id="w-table"></table></div>
    <p class="src">收益率=(最新单位净值−销售日单位净值)/销售日单位净值，未扣申赎费；有分红基金请注意累计净值口径</p>
  </div>`;
  $("#w-update").onclick = async e=>{ e.target.disabled=true; e.target.textContent="更新中…";
    try{ const r = await api("/watch/update",{method:"POST"}); toast(`更新完成: 成功${r.ok} 失败${r.fail.length} 新达标${r.new_alerts}`); }
    catch(err){ toast("更新失败: "+err.message); }
    renderWatch(); refreshBell(); };
  $("#w-filter").onchange = renderWatch;
  watchData = await api("/watch");
  renderWatch();
}
function renderWatch(){
  const f = $("#w-filter").value;
  const rows = watchData.filter(w=>!f||w.status===f);
  $("#w-table").innerHTML = `<tr><th>代码</th><th>基金名称</th><th>销售日期</th><th>销售日净值</th><th>最新净值日期</th><th>最新净值</th><th>日涨幅</th><th>收益率</th><th>目标</th><th>状态</th><th>理财经理</th><th>备注</th><th>操作</th></tr>` +
    rows.map(w=>`<tr class="${w.status==='hit'?'hit':''}">
      <td><a href="#/fund/${w.fund_code}"><b>${w.fund_code}</b></a></td><td>${w.fund_name||""}</td><td>${w.sale_date}</td>
      <td>${fmt(w.sale_nav,4)}</td><td>${w.latest_date||"—"}</td><td>${fmt(w.latest_nav,4)}</td>
      <td class="${cls(w.daily_pct)}">${pct(w.daily_pct)}</td>
      <td class="${cls(w.ret_pct)}"><b>${pct(w.ret_pct)}</b></td><td>${fmt(w.target_pct,1)}%</td>
      <td>${w.status==='hit'?'<span class="tag red">🔴 已达目标</span>':w.status==='warn_down'?'<span class="tag amber">回撤预警</span>':'<span class="tag">跟踪中</span>'}</td>
      <td>${w.manager||""}</td><td>${w.note||""}</td>
      <td><button onclick='openWatchModal(${JSON.stringify(w)})'>编辑</button> <button class="danger" onclick="delWatch(${w.id})">删除</button></td></tr>`).join("");
}
function openWatchModal(w){
  const m = $("#modal");
  m.innerHTML = `<h3>${w?"编辑":"新增"}跟踪记录</h3>
    <div class="f"><label>基金代码*</label><input id="m-code" value="${w?w.fund_code:""}" ${w?"disabled":""}></div>
    <div class="f"><label>销售日期*</label><input id="m-date" type="date" value="${w?w.sale_date:new Date().toISOString().slice(0,10)}"></div>
    <div class="f"><label>销售日单位净值*</label><input id="m-nav" type="number" step="0.0001" value="${w?w.sale_nav:""}"></div>
    <div class="f"><label>目标收益率% (默认5)</label><input id="m-target" type="number" step="0.5" value="${w?w.target_pct:5}"></div>
    <div class="f"><label>理财经理</label><input id="m-mgr" value="${w?w.manager||"":""}"></div>
    <div class="f"><label>备注(组合代号等, 勿填客户身份信息)</label><input id="m-note" value="${w?w.note||"":""}"></div>
    <div style="display:flex;gap:8px;justify-content:flex-end"><button onclick="closeModal()">取消</button><button class="primary" id="m-save">保存</button></div>`;
  $("#modal-bg").style.display="flex";
  $("#m-save").onclick = async ()=>{
    const body = {fund_code:$("#m-code").value.trim(), sale_date:$("#m-date").value, sale_nav:parseFloat($("#m-nav").value),
      target_pct:parseFloat($("#m-target").value)||5, manager:$("#m-mgr").value, note:$("#m-note").value};
    try{
      if(w) await api("/watch/"+w.id,{method:"PUT",body:JSON.stringify(body)});
      else await api("/watch",{method:"POST",body:JSON.stringify(body)});
      closeModal(); watchData = await api("/watch"); renderWatch(); toast("已保存");
    }catch(e){ toast(e.message); }
  };
}
function closeModal(){ $("#modal-bg").style.display="none"; }
$("#modal-bg").addEventListener("click", e=>{ if(e.target.id==="modal-bg") closeModal(); });
async function delWatch(id){ if(!confirm("删除这条跟踪记录？")) return; await api("/watch/"+id,{method:"DELETE"}); watchData = await api("/watch"); renderWatch(); }
// ---------- 代销筛选 ----------
async function pageScreening(c){
  c.innerHTML = `
  <div class="panel"><h3>代销池管理</h3>
    <div class="toolbar">
      <input id="p-codes" placeholder="粘贴基金代码, 逗号/空格分隔" style="width:340px">
      <button id="p-add">添加</button>
      <label class="hint">或导入文件 <input type="file" id="p-file" accept=".csv,.xlsx"></label>
      <span class="sp"></span><span class="hint" id="p-count"></span>
    </div>
    <div id="p-list" style="max-height:180px;overflow:auto"></div>
  </div>
  <div class="panel"><h3>运行筛选</h3>
    <div class="toolbar">
      <label>市场状态 <select id="s-regime"><option value="">自动(按仪表盘判定)</option><option>进攻</option><option>均衡</option><option>防御</option></select></label>
      <button class="primary" id="s-run">▶ 运行筛选(约数分钟)</button>
      <span class="hint">打分: 持续性30%+风险调整25%+回撤20%+动量15%+长期10%(随市场状态自动调整权重); 分位在全市场同类型全集内计算</span>
    </div>
    <div id="s-runs"></div>
    <div id="s-results"></div>
  </div>`;
  const renderPool = async ()=>{
    const pool = await api("/pool");
    $("#p-count").textContent = "共 "+pool.length+" 只";
    $("#p-list").innerHTML = pool.map(p=>`<span class="tag" style="margin:2px">${p.fund_code} ${p.fund_name||""} <a href="javascript:void 0" onclick="delPool(${p.id})" style="color:var(--red)">×</a></span>`).join("") || '<span class="hint">代销池为空</span>';
  };
  window.delPool = async id=>{ await api("/pool/"+id,{method:"DELETE"}); renderPool(); };
  $("#p-add").onclick = async ()=>{
    const codes = $("#p-codes").value.split(/[\s,，]+/).filter(Boolean);
    if(!codes.length) return;
    const r = await api("/pool/add",{method:"POST",body:JSON.stringify({codes})});
    toast(`新增 ${r.added} 只, 共 ${r.total} 只`); $("#p-codes").value=""; renderPool();
  };
  $("#p-file").onchange = async e=>{
    const f = e.target.files[0]; if(!f) return;
    const fd = new FormData(); fd.append("file", f);
    const r = await fetch(API+"/pool/import",{method:"POST",headers:{"Authorization":"Bearer "+token},body:fd});
    const d = await r.json(); toast(`识别代码 ${d.found_codes} 个, 新增 ${d.added}`); renderPool();
  };
  $("#s-run").onclick = async ()=>{
    const regime = $("#s-regime").value || null;
    await api("/screening/run",{method:"POST",body:JSON.stringify({regime})});
    toast("筛选已开始, 完成后刷新下方列表"); pollRuns();
  };
  renderPool(); renderRuns();
  async function pollRuns(){ for(let i=0;i<40;i++){ await new Promise(r=>setTimeout(r,8000)); const runs = await renderRuns(); const latest = runs[0]; if(latest && latest.status!=="running"){ showResults(latest.id); break; } } }
  async function renderRuns(){
    const runs = await api("/screening/runs");
    $("#s-runs").innerHTML = runs.length? `<table><tr><th>期次</th><th>时间</th><th>市场状态</th><th>状态</th><th>全集/代销池</th><th>备注</th><th></th></tr>`+
      runs.map(r=>`<tr><td>#${r.id}</td><td>${r.created_at}</td><td>${r.regime}</td><td>${r.status}</td><td>${r.universe}/${r.pool}</td><td>${r.note||""}</td>
      <td>${r.status==="done"?`<button onclick="showResults(${r.id})">查看结果</button> <button onclick="publishRun(${r.id})">确认发布</button>`:""}</td></tr>`).join("")+"</table>" : '<p class="hint">尚无筛选记录</p>';
    return runs;
  }
  window._renderRuns = renderRuns;
}
async function showResults(rid){
  const rows = await api(`/screening/runs/${rid}/results`);
  $("#s-results").innerHTML = `<h3 style="margin:14px 0 8px">期次 #${rid} 建议名单 (Top ${rows.length})</h3>
  <div style="overflow:auto"><table><tr><th>#</th><th>代码</th><th>名称</th><th>类型</th><th>综合分</th><th>五维分(持续/风险调整/回撤/动量/长期)</th><th>近1月</th><th>近3月</th><th>近1年</th><th>近3年</th><th>最大回撤</th><th>夏普</th><th>卡玛</th><th>风险标签</th><th>入选理由</th></tr>
  ${rows.map((r,i)=>`<tr><td>${i+1}</td><td><a href="#/fund/${r.fund_code}"><b>${r.fund_code}</b></a></td><td>${r.fund_name}</td><td>${r.fund_type}</td>
    <td><b>${fmt(r.score,1)}</b> <span class="scorebar"><i style="width:${r.score}%"></i></span></td>
    <td class="hint">${fmt(r.persist,0)} / ${fmt(r.risk_adj,0)} / ${fmt(r.dd_score,0)} / ${fmt(r.momentum,0)} / ${fmt(r.long_score,0)}</td>
    <td class="${cls(r.r1m)}">${pct(r.r1m)}</td><td class="${cls(r.r3m)}">${pct(r.r3m)}</td><td class="${cls(r.r1y)}">${pct(r.r1y)}</td><td class="${cls(r.r3y)}">${pct(r.r3y)}</td>
    <td class="down">${fmt(r.max_dd,1)}%</td><td>${fmt(r.sharpe,2)}</td><td>${fmt(r.calmar,2)}</td>
    <td>${r.risk_tag && r.risk_tag!=="正常" ? '<span class="tag amber">'+r.risk_tag+'</span>' : '<span class="tag">正常</span>'}</td>
    <td style="white-space:normal;min-width:260px" class="hint">${r.reason}</td></tr>`).join("")}</table></div>
  <p class="src">内部研究辅助, 不构成收益承诺; 对外销售须走行内准入与客户风险匹配</p>`;
}
async function publishRun(rid){ try{ await api(`/screening/publish/${rid}`,{method:"POST"}); toast("已发布"); }catch(e){ toast(e.message); } }
// ---------- 基金详情 ----------
async function pageFund(c, q){
  c.innerHTML = '<div class="panel">加载基金数据中…(首次打开需拉取历史净值, 请稍候)</div>';
  let code = q.trim();
  try{
    const d = await api("/funds/"+encodeURIComponent(code));
    c.innerHTML = `
    <div class="panel"><h3>${d.code} ${d.name} <span class="sub">最新净值 ${fmt(d.latest_nav,4)} · ${d.latest_date||""} · 来源 东方财富</span></h3>
      <div class="cards" style="grid-template-columns:repeat(5,1fr)">
        <div class="kpi"><div class="l">近1月</div><div class="n ${cls(d.returns.r1m)}" style="font-size:20px">${pct(d.returns.r1m)}</div></div>
        <div class="kpi"><div class="l">近3月</div><div class="n ${cls(d.returns.r3m)}" style="font-size:20px">${pct(d.returns.r3m)}</div></div>
        <div class="kpi"><div class="l">近1年</div><div class="n ${cls(d.returns.r1y)}" style="font-size:20px">${pct(d.returns.r1y)}</div></div>
        <div class="kpi"><div class="l">近3年最大回撤</div><div class="n down" style="font-size:20px">${d.metrics.max_dd!==undefined?fmt(d.metrics.max_dd,1)+"%":"—"}</div></div>
        <div class="kpi"><div class="l">夏普 / 卡玛(近3年)</div><div class="n" style="font-size:20px">${fmt(d.metrics.sharpe,2)} / ${fmt(d.metrics.calmar,2)}</div></div>
      </div>
      <div id="chart-nav" style="height:340px"></div>
      <div id="chart-dd" style="height:180px;margin-top:10px"></div>
      <p class="src">净值口径: 单位净值(未复权); 指标由系统按近3年日净值计算, 无风险利率取1.5%</p>
    </div>`;
    const dates = d.series.map(s=>s.date), navs = d.series.map(s=>s.nav);
    let peak=-1e9; const dd = navs.map(n=>{ peak=Math.max(peak,n); return +(((n/peak)-1)*100).toFixed(2); });
    echarts.init($("#chart-nav")).setOption({title:{text:"单位净值走势(近3年)",textStyle:{color:"rgba(255,255,255,.85)",fontSize:13}},tooltip:{trigger:"axis",backgroundColor:"#3a3a3c",borderColor:"rgba(255,255,255,.12)",textStyle:{color:"#fff"}},xAxis:{type:"category",data:dates,axisLabel:{color:"rgba(255,255,255,.55)"},axisLine:{lineStyle:{color:"rgba(255,255,255,.12)"}}},yAxis:{type:"value",scale:true,axisLabel:{color:"rgba(255,255,255,.55)"},splitLine:{lineStyle:{color:"rgba(255,255,255,.06)"}}},series:[{type:"line",data:navs,smooth:true,areaStyle:{opacity:.12},color:"#0a84ff"}],dataZoom:[{type:"inside"}]});
    echarts.init($("#chart-dd")).setOption({title:{text:"回撤(水下图 %)",textStyle:{color:"rgba(255,255,255,.85)",fontSize:13}},tooltip:{trigger:"axis",backgroundColor:"#3a3a3c",borderColor:"rgba(255,255,255,.12)",textStyle:{color:"#fff"}},xAxis:{type:"category",data:dates,axisLabel:{color:"rgba(255,255,255,.55)"},axisLine:{lineStyle:{color:"rgba(255,255,255,.12)"}}},yAxis:{type:"value",axisLabel:{color:"rgba(255,255,255,.55)"},splitLine:{lineStyle:{color:"rgba(255,255,255,.06)"}}},series:[{type:"line",data:dd,areaStyle:{color:"rgba(255,159,10,.18)"},color:"#ff9f0a"}],dataZoom:[{type:"inside"}]});
  }catch(e){
    c.innerHTML = `<div class="panel">加载失败: ${e.message}<br><span class="hint">请确认基金代码正确(6位), 或稍后重试(免费数据源限流时可能失败)</span></div>`;
  }
}
// ---------- 行业 ----------
async function pageIndustry(c){
  const d = await api("/industry");
  const rows = d.rows||[];
  c.innerHTML = `<div class="panel"><h3>申万一级行业走势 <span class="sub">${d.updated? "更新于 "+d.updated+" · 来源 "+(d.source||"") : "暂无数据 — 行业任务每周六运行, 也可在系统管理页手动触发(需申万源可达)"}</span></h3>
  ${rows.length? `<div id="ind-chart" style="height:420px"></div>
  <table><tr><th>排名</th><th>行业</th><th>近1周</th><th>近1月</th><th>近3月</th><th>建议</th></tr>
  ${rows.map(r=>`<tr><td>${r.rank}</td><td>${r.name}</td><td class="${cls(r.r1w)}">${pct(r.r1w)}</td><td class="${cls(r.r1m)}">${pct(r.r1m)}</td><td class="${cls(r.r3m)}">${pct(r.r3m)}</td><td>${r.stance==="超配"?'<span class="tag red">超配</span>':r.stance==="低配"?'<span class="tag">低配</span>':'<span class="tag blue">标配</span>'}</td></tr>`).join("")}</table>`
  : '<p class="hint">暂无行业数据</p>'}</div>`;
  if(rows.length){
    echarts.init($("#ind-chart")).setOption({title:{text:"近1月涨跌幅 %",textStyle:{color:"rgba(255,255,255,.85)",fontSize:13}},tooltip:{backgroundColor:"#3a3a3c",borderColor:"rgba(255,255,255,.12)",textStyle:{color:"#fff"}},xAxis:{type:"value",axisLabel:{color:"rgba(255,255,255,.55)"},splitLine:{lineStyle:{color:"rgba(255,255,255,.06)"}}},yAxis:{type:"category",inverse:true,data:rows.map(r=>r.name),axisLabel:{color:"rgba(255,255,255,.75)"},axisLine:{lineStyle:{color:"rgba(255,255,255,.12)"}}},series:[{type:"bar",data:rows.map(r=>({value:+fmt(r.r1m),itemStyle:{color:r.r1m>=0?"#ff453a":"#30d158"}}))}]});
  }
}
// ---------- 系统 ----------
async function pageSystem(c){
  const d = await api("/system/status");
  c.innerHTML = `
  <div class="panel"><h3>数据源状态(免费方案)</h3>
    <div class="grid2">${d.sources.map(s=>`<div class="kpi"><div class="l">${s.name}</div><div style="margin-top:6px">${s.role}</div><div class="hint">${s.note}</div></div>`).join("")}</div>
    <p class="src">算法版本 ${d.algo_version}</p></div>
  <div class="panel"><h3>手动任务</h3>
    <div class="toolbar">
      <button onclick="runJob('watch_update')">更新跟踪净值</button>
      <button onclick="runJob('market_regime')">判定市场状态</button>
      <button onclick="runJob('industry_sw')">更新申万行业</button>
      <span class="hint">定时: 工作日17:40 市场状态 · 21:35 净值更新 · 周六09:30 行业 · 周一08:30 自动筛选</span>
    </div></div>
  <div class="panel"><h3>任务日志</h3><table><tr><th>任务</th><th>状态</th><th>开始</th><th>结束</th><th>详情</th></tr>
    ${d.jobs.map(j=>`<tr><td>${j.job}</td><td>${j.status==="done"?'<span class="tag blue">done</span>':j.status==="failed"?'<span class="tag red">failed</span>':j.status}</td><td>${j.started}</td><td>${j.finished||""}</td><td style="white-space:normal;min-width:280px" class="hint">${(j.detail||"").slice(0,300)}</td></tr>`).join("")}</table></div>`;
}
async function runJob(job){ await api("/system/run-job",{method:"POST",body:JSON.stringify({job})}); toast("任务已启动, 稍后刷新查看日志"); }
// ---------- 启动 ----------
if(token){ $("#login").style.display="none"; $("#app").style.display="block"; api("/me").then(u=>{ me=u; applyMe(); route(); }).catch(()=>{}); route(); refreshBell(); }
$("#tb-date").textContent = new Date().toLocaleDateString("zh-CN",{year:"numeric",month:"long",day:"numeric",weekday:"long"});


// ---------- Agent 接入管理 ----------
async function pageAgents(c){
  if(!me || me.role!=="admin"){ c.innerHTML = '<div class="panel">仅管理员可管理 Agent 接入。</div>'; return; }
  const base = location.origin;
  c.innerHTML = `
  <div class="panel"><h3>Agent 接入 <span class="sub">给 Muse / WorkBuddy 等外部 Agent 发放 API Key，通过配套 CLI(fundq)调用本系统的分析与数据</span></h3>
    <p class="hint">服务地址 <code>${base}</code> · 鉴权方式：请求头 <code>X-API-Key: fqk_...</code>（或 Authorization: Bearer fqk_...）<br>
    权限分两档：<b>read</b> 只读查询（跟踪/提醒/筛选结果/基金详情/行业/市场状态）；<b>write</b> 含写操作（增删跟踪、刷新净值、导入代销池、发起筛选、标记已联系）。发布名单、账号与密钥管理仍只限网页 admin。<br>
    密钥明文<b>只在创建时显示一次</b>，库里只存哈希；丢了就吊销重建。每次调用都会记审计日志。</p>
  </div>
  <div class="panel"><h3>新建密钥</h3>
    <div class="toolbar">
      <input id="ak-name" placeholder="接入方名称, 如 Muse-办公本 / WorkBuddy" style="min-width:260px">
      <label><input type="checkbox" id="ak-read" checked disabled> read 只读</label>
      <label><input type="checkbox" id="ak-write"> write 可写</label>
      <button class="primary" onclick="createAgentKey()">生成密钥</button>
    </div>
    <div id="ak-new"></div>
  </div>
  <div class="panel"><h3>密钥列表</h3><div id="ak-list">加载中…</div></div>
  <div class="panel"><h3>CLI 快速上手</h3>
    <p class="hint">配套工具在代码仓库 <code>tools/fundq.py</code>（单文件、零依赖），配套技能在 <code>skills/fund-quant-cli/</code>，把这两样交给目标 Agent 即可。手动调用示例：</p>
    <pre class="code">export FUNDQ_URL=${base}
export FUNDQ_API_KEY=fqk_...        # 上面生成的密钥
python3 fundq.py dashboard          # 仪表盘汇总(JSON)
python3 fundq.py watch list         # 销售跟踪
python3 fundq.py fund 000001        # 基金详情与指标
python3 fundq.py screen results 3   # 某轮筛选结果
python3 fundq.py watch refresh      # (write)刷新净值并触发达标判定</pre>
  </div>
  <div class="panel"><h3>调用审计 <span class="sub">最近 100 条</span></h3><div id="ak-logs">加载中…</div></div>`;
  renderAgentKeys();
}
async function renderAgentKeys(){
  const keys = await api("/agent-keys");
  $("#ak-list").innerHTML = keys.length ? `<table><tr><th>名称</th><th>密钥前缀</th><th>权限</th><th>创建</th><th>最近使用</th><th>状态</th><th>操作</th></tr>
    ${keys.map(k=>`<tr><td><b>${k.name}</b></td><td><code>${k.prefix}…</code></td><td>${k.scopes.map(s=>`<span class="tag ${s==='write'?'blue':''}">${s}</span>`).join(" ")}</td>
    <td>${(k.created_at||"").slice(0,16)}</td><td>${k.last_used_at? k.last_used_at.slice(0,16) : "从未"}</td>
    <td>${k.revoked? '<span class="tag">已吊销</span>' : '<span class="tag blue">有效</span>'}</td>
    <td>${k.revoked? `<button onclick="delAgentKey(${k.id})">删除</button>` : `<button onclick="revokeAgentKey(${k.id})">吊销</button>`}</td></tr>`).join("")}</table>`
    : '<p class="hint">还没有密钥，上面建一个。</p>';
  const logs = await api("/agent-keys/logs");
  $("#ak-logs").innerHTML = logs.length ? `<table><tr><th>时间</th><th>密钥</th><th>方法</th><th>路径</th><th>状态</th></tr>
    ${logs.map(l=>`<tr><td>${(l.at||"").slice(0,19)}</td><td>${l.key_name}</td><td>${l.method}</td><td><code>${l.path}</code></td><td>${l.status}</td></tr>`).join("")}</table>`
    : '<p class="hint">暂无调用记录</p>';
}
async function createAgentKey(){
  const name = $("#ak-name").value.trim();
  if(!name){ toast("先填接入方名称"); return; }
  const scopes = ["read"]; if($("#ak-write").checked) scopes.push("write");
  try{
    const r = await api("/agent-keys", {method:"POST", body: JSON.stringify({name, scopes})});
    $("#ak-new").innerHTML = `<div class="banner warn">🔑 新密钥（<b>只显示这一次</b>，请立即复制保存）：<br><code style="font-size:14px;word-break:break-all">${r.api_key}</code><br>
      <button onclick="navigator.clipboard&&navigator.clipboard.writeText('${r.api_key}');toast('已复制')">复制密钥</button>
      <span class="hint">配置：export FUNDQ_API_KEY=${r.api_key}</span></div>`;
    $("#ak-name").value = ""; renderAgentKeys();
  }catch(e){ toast(e.message); }
}
async function revokeAgentKey(id){ if(!confirm("吊销后该密钥立即失效，确定？")) return;
  try{ await api(`/agent-keys/${id}/revoke`, {method:"POST"}); toast("已吊销"); renderAgentKeys(); }catch(e){ toast(e.message); } }
async function delAgentKey(id){ if(!confirm("删除该密钥记录，确定？")) return;
  try{ await api("/agent-keys/"+id, {method:"DELETE"}); toast("已删除"); renderAgentKeys(); }catch(e){ toast(e.message); } }

// ---------- 账号管理 ----------
async function pageUsers(c){
  if(!me || me.role!=="admin"){ c.innerHTML = '<div class="panel">仅管理员可访问账号管理。</div>'; return; }
  c.innerHTML = `
  <div class="page-title">账号管理</div>
  <div class="page-desc">管理员可新建账号、重置密码、删除账号。角色：admin 主管(全部权限) · manager 理财经理 · viewer 只读查看。管理员 admin 的密码由部署环境(.env 的 ADMIN_PASSWORD)统一管理，改那里重启即生效。</div>
  <div class="panel"><h3>新建账号</h3>
    <div class="toolbar">
      <input id="u-name" placeholder="用户名" style="width:170px">
      <input id="u-pw" placeholder="初始密码(至少6位)" style="width:190px">
      <select id="u-role"><option value="manager">manager 理财经理</option><option value="viewer">viewer 只读</option><option value="admin">admin 主管</option></select>
      <button class="primary" id="u-add">新建</button>
    </div>
    <div id="u-list"></div>
  </div>`;
  const render = async ()=>{
    const users = await api("/users");
    $("#u-list").innerHTML = `<table><tr><th>ID</th><th>用户名</th><th>角色</th><th>创建时间</th><th>操作</th></tr>` +
      users.map(u=>`<tr><td>${u.id}</td><td><b>${u.username}</b>${u.username===me.username?' (我)':''}</td><td><span class="tag ${u.role==='admin'?'blue':''}">${u.role}</span></td><td>${u.created_at||''}</td>
      <td><button onclick="resetUserPw(${u.id},'${u.username}')">重置密码</button> ${u.username!==me.username?`<button class="danger" onclick="delUser(${u.id},'${u.username}')">删除</button>`:''}</td></tr>`).join("") + `</table>`;
  };
  window.resetUserPw = async (id,name)=>{
    const pw = prompt(`给账号 ${name} 设置新密码(至少6位):`);
    if(!pw) return;
    try{ await api(`/users/${id}/password`,{method:"POST",body:JSON.stringify({password:pw})}); toast("已重置 "+name+" 的密码"); }catch(e){ toast(e.message); }
  };
  window.delUser = async (id,name)=>{
    if(!confirm(`删除账号 ${name}？`)) return;
    try{ await api("/users/"+id,{method:"DELETE"}); toast("已删除"); render(); }catch(e){ toast(e.message); }
  };
  $("#u-add").onclick = async ()=>{
    const username=$("#u-name").value.trim(), password=$("#u-pw").value, role=$("#u-role").value;
    if(!username || password.length<6){ toast("用户名必填, 密码至少6位"); return; }
    try{ await api("/users",{method:"POST",body:JSON.stringify({username,password,role})}); toast("账号已创建"); $("#u-name").value=""; $("#u-pw").value=""; render(); }catch(e){ toast(e.message); }
  };
  render();
}

/* 侧边栏: 桌面收起/展开, 移动端抽屉 */
(function(){
  var t = document.getElementById("sb-toggle");
  if (t) t.addEventListener("click", function(){
    if (window.innerWidth < 1024) document.body.classList.toggle("sb-open");
    else document.body.classList.toggle("sb-collapsed");
  });
  var ov = document.getElementById("sb-overlay");
  if (ov) ov.addEventListener("click", function(){ document.body.classList.remove("sb-open"); });
  document.querySelectorAll("#nav a").forEach(function(a){
    a.addEventListener("click", function(){ document.body.classList.remove("sb-open"); });
  });
})();
