const els = {
  notice: document.querySelector('#notice'), operational: document.querySelector('#operationalCount'),
  lastRequest: document.querySelector('#lastRequest'), source: document.querySelector('#sourceSelect'),
  routePath: document.querySelector('#routePath'), routeCost: document.querySelector('#routeCost'),
  send: document.querySelector('#sendButton'), reset: document.querySelector('#resetButton'),
  result: document.querySelector('#requestResult'), detail: document.querySelector('#detailPanel'),
  tabs: document.querySelector('.tabs'), tabContent: document.querySelector('#tabContent'),
  eventCount: document.querySelector('#eventCount'), packetLayer: document.querySelector('#packetLayer')
};

const positions = {
  'PC-CHECKIN-1':[95,465], 'PC-CHECKIN-2':[215,465], 'SW-CHECKIN':[155,405], 'R-CHECKIN':[155,247],
  'R-SERVICES':[460,135], 'SW-SERVICES':[460,405], 'HTTP-SERVER':[460,465],
  'R-CARGO':[765,247], 'SW-CARGO':[765,405], 'PC-CARGO-1':[705,465], 'PC-CARGO-2':[825,465]
};

let state = null;
let activeTab = 'addressing';
let selectedRouter = 'R-CHECKIN';
let selectedInspector = null;
let animationToken = 0;
let playing = false;

async function api(path, options = {}) {
  const response = await fetch(path, {headers:{'Content-Type':'application/json'}, ...options});
  const data = await response.json().catch(() => ({ok:false,error:{message:'Invalid server response'}}));
  if (!response.ok || !data.ok) throw new Error(data.error?.message || `Request failed (${response.status})`);
  return data;
}

function showNotice(message) {
  els.notice.textContent = message;
  els.notice.hidden = false;
  window.clearTimeout(showNotice.timer);
  showNotice.timer = window.setTimeout(() => { els.notice.hidden = true; }, 5000);
}

function esc(value) {
  return String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
}

function linkBetween(a, b) {
  return Object.values(state.links).find(link => new Set([link.a, link.b]).has(a) && new Set([link.a, link.b]).has(b));
}

function render(nextState) {
  state = nextState;
  els.operational.textContent = `${state.operational_links} / 3`;
  els.lastRequest.textContent = state.last_request ? (state.last_request.reachable ? 'Delivered' : 'Unreachable') : 'No request yet';
  els.eventCount.textContent = state.events.length;
  if (!els.source.options.length) {
    state.sources.forEach(id => els.source.add(new Option(`${state.devices[id].name} · ${state.devices[id].ip}`, id)));
  }
  els.source.value = state.selected_pc;
  els.routePath.textContent = state.route.reachable ? state.route.router_path.join(' → ') : 'Destination unreachable';
  els.routeCost.textContent = state.route.reachable ? `Inter-router path cost: ${state.route.cost}` : 'No operational path to Airport Services';
  document.querySelectorAll('.wan-link').forEach(node => {
    const link = state.links[node.dataset.link];
    node.classList.toggle('down', !link.operational);
    node.classList.remove('route');
    document.querySelector(`#cost-${link.id}`).textContent = link.cost;
  });
  if (state.route.reachable) {
    state.route.router_path.slice(0,-1).forEach((router, index) => {
      const link = linkBetween(router, state.route.router_path[index + 1]);
      document.querySelector(`#svg-link-${link.id}`)?.classList.add('route');
    });
  }
  renderTab();
  if (selectedInspector?.type === 'link') inspectLink(selectedInspector.id);
  if (selectedInspector?.type === 'device') inspectDevice(selectedInspector.id);
}

function inspectDevice(id) {
  const device = state.devices[id];
  if (!device) return;
  selectedInspector = {type:'device', id};
  els.detail.innerHTML = `<p class="eyebrow">DEVICE INSPECTOR</p><h3>${esc(device.name)}</h3>
    <div class="detail-grid"><div><small>Device ID</small><strong>${esc(id)}</strong></div><div><small>Type</small><strong>${esc(device.type)}</strong></div>
    <div><small>Zone</small><strong>${esc(device.zone)}</strong></div>${device.area !== undefined ? `<div><small>OSPF area</small><strong>Area ${device.area}</strong></div>` : ''}
    ${device.ip ? `<div><small>Address</small><strong>${esc(device.ip)}</strong></div>` : ''}${device.lan_ip ? `<div><small>LAN gateway</small><strong>${esc(device.lan_ip)}</strong></div>` : ''}
    ${device.gateway ? `<div><small>Gateway</small><strong>${esc(device.gateway)}</strong></div>` : ''}</div>`;
}

function inspectLink(id) {
  const link = state.links[id];
  if (!link) return;
  selectedInspector = {type:'link', id};
  els.detail.innerHTML = `<p class="eyebrow">SERIAL LINK INSPECTOR</p><h3>${esc(link.name)}</h3>
    <div class="link-status ${link.operational?'up':'down'}">${link.operational?'●':'×'} ${esc(link.status_reason)}</div>
    <div class="toggle-row"><span>Administrative state</span><label class="toggle"><input id="adminToggle" type="checkbox" ${link.admin_up?'checked':''}><span></span></label></div>
    <div class="field"><label for="costInput">Educational OSPF cost (1–10000)</label><input id="costInput" type="number" min="1" max="10000" step="1" value="${link.cost}"></div>
    <div class="field-row">${[link.a,link.b].map(router => `<div class="field"><label>${esc(router)} · ${esc(link.interfaces[router])}<br>${esc(link.addresses[router])}</label><select class="encapsulation" data-router="${esc(router)}"><option ${link.encapsulation[router]==='PPP'?'selected':''}>PPP</option><option ${link.encapsulation[router]==='HDLC'?'selected':''}>HDLC</option></select></div>`).join('')}</div>`;
  els.detail.querySelector('#adminToggle').addEventListener('change', e => updateLink(id,{admin_up:e.target.checked}));
  els.detail.querySelector('#costInput').addEventListener('change', e => updateLink(id,{cost:e.target.valueAsNumber}));
  els.detail.querySelectorAll('.encapsulation').forEach(select => select.addEventListener('change', e => updateLink(id,{encapsulation:{[e.target.dataset.router]:e.target.value}})));
}

async function updateLink(id, changes) {
  if (playing) return;
  try {
    const data = await api(`/api/links/${id}`, {method:'PATCH', body:JSON.stringify(changes)});
    render(data.state);
  } catch (error) { showNotice(error.message); inspectLink(id); }
}

function renderTab() {
  if (!state) return;
  const renderers = {addressing:renderAddressing, routing:renderRouting, ppp:renderPPP, events:renderEvents};
  els.tabContent.innerHTML = renderers[activeTab]();
  if (activeTab === 'routing') {
    els.tabContent.querySelectorAll('[data-router-table]').forEach(button => button.addEventListener('click', () => { selectedRouter=button.dataset.routerTable; renderTab(); }));
  }
  if (activeTab === 'ppp') {
    els.tabContent.querySelectorAll('[data-inspect-link]').forEach(button => button.addEventListener('click', () => { inspectLink(button.dataset.inspectLink); els.detail.scrollIntoView({behavior:'smooth',block:'nearest'}); }));
  }
}

function renderAddressing() {
  return `<div class="section-intro"><div><h3>VLSM allocation plan</h3><p>Network details are calculated with Python’s <code>ipaddress</code> module. The comparison covers the three LANs only; allocated addresses include network and broadcast addresses, while usable capacity counts host addresses.</p></div><div class="comparison"><div class="metric"><small>VLSM allocated</small><strong>112</strong></div><div class="metric"><small>FLSM baseline</small><strong>192</strong></div><div class="metric"><small>Reduction</small><strong>41.7%</strong></div></div></div>
  <div class="table-wrap"><table><thead><tr><th>Zone / link</th><th>Need</th><th>Subnet</th><th>Mask</th><th>Usable range</th><th>Broadcast</th><th>Capacity</th></tr></thead><tbody>${state.addressing.map(row => `<tr><td><strong>${esc(row.name)}</strong></td><td>${row.required}</td><td>${esc(row.subnet)}</td><td>${esc(row.mask)}</td><td>${esc(row.usable_range)}</td><td>${esc(row.broadcast)}</td><td>${row.usable_capacity}</td></tr>`).join('')}</tbody></table></div>`;
}

function renderRouting() {
  const rows = state.routing_tables[selectedRouter];
  return `<div class="section-intro"><div><h3>OSPF-inspired route selection</h3><p>Dijkstra’s shortest-path algorithm uses operational serial links and deterministic tie-breaking. Totals are <strong>inter-router path cost</strong>; LAN interface costs are omitted. This model does not implement neighbor exchanges, LSAs, timers, or full OSPF.</p></div></div>
  <div class="routing-selector">${Object.keys(state.routing_tables).map(router => `<button data-router-table="${router}" class="${router===selectedRouter?'active':''}">${router}</button>`).join('')}</div>
  <div class="table-wrap"><table><thead><tr><th>Remote LAN</th><th>Destination router</th><th>Next-hop router</th><th>Next-hop address</th><th>Cost</th><th>Reachability</th></tr></thead><tbody>${rows.map(row => `<tr><td>${esc(row.subnet)}</td><td>${esc(row.destination_router)}</td><td>${esc(row.next_hop_router || '—')}</td><td>${esc(row.next_hop_address || '—')}</td><td>${row.cost ?? '—'}</td><td><i class="status-dot ${row.reachable?'':'down'}"></i>${row.reachable?'Reachable':'Unreachable'}</td></tr>`).join('')}</tbody></table></div>`;
}

function renderPPP() {
  return `<div class="section-intro"><div><h3>Point-to-Point serial links</h3><p>Change one endpoint to HDLC to demonstrate a configuration mismatch, then match both ends or restore PPP. This models compatibility only—not negotiation, frame transmission, CHAP, or PAP.</p></div></div>
  <div class="table-wrap"><table><thead><tr><th>Link / subnet</th><th>Endpoint A</th><th>Encapsulation</th><th>Endpoint B</th><th>Encapsulation</th><th>Status</th><th></th></tr></thead><tbody>${Object.values(state.links).map(link => `<tr><td><strong>${esc(link.name)}</strong><br>${esc(link.subnet)}</td><td>${esc(link.a)} · ${esc(link.interfaces[link.a])}<br>${esc(link.addresses[link.a])}</td><td>${link.encapsulation[link.a]}</td><td>${esc(link.b)} · ${esc(link.interfaces[link.b])}<br>${esc(link.addresses[link.b])}</td><td>${link.encapsulation[link.b]}</td><td><i class="status-dot ${link.operational?'':'down'}"></i>${esc(link.status_reason)}</td><td><button class="button ghost" data-inspect-link="${link.id}">Configure</button></td></tr>`).join('')}</tbody></table></div>`;
}

function renderEvents() {
  if (!state.events.length) return '<div class="empty">No events yet.</div>';
  return `<div class="section-intro"><div><h3>Simulation event log</h3><p>Newest first. State and this bounded log are held in server memory and shared by every tab connected to this local Flask instance.</p></div></div><div class="event-list">${state.events.map(event => `<div class="event"><time>${new Date(event.timestamp).toLocaleTimeString()}</time><span class="event-type">${esc(event.type)}</span><span>${esc(event.message)}</span></div>`).join('')}</div>`;
}

function setPlaying(value) {
  playing = value;
  els.send.disabled = value;
  els.reset.disabled = value;
  els.source.disabled = value;
  document.querySelectorAll('#detailPanel input,#detailPanel select').forEach(node => node.disabled = value);
}

async function animatePath(path, token) {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches || path.length < 2) return;
  const svgNS = 'http://www.w3.org/2000/svg';
  const packet = document.createElementNS(svgNS,'circle');
  packet.setAttribute('r','8'); packet.setAttribute('class','packet');
  els.packetLayer.append(packet);
  for (let i=0;i<path.length-1;i++) {
    if (token !== animationToken) break;
    const [x1,y1]=positions[path[i]], [x2,y2]=positions[path[i+1]];
    packet.setAttribute('cx',x1); packet.setAttribute('cy',y1);
    const animation = packet.animate([{cx:x1,cy:y1},{cx:x2,cy:y2}],{duration:520,easing:'ease-in-out',fill:'forwards'});
    await animation.finished.catch(()=>{});
    packet.setAttribute('cx',x2); packet.setAttribute('cy',y2);
  }
  packet.remove();
}

els.send.addEventListener('click', async () => {
  if (playing) return;
  setPlaying(true);
  const token = ++animationToken;
  els.result.hidden = true;
  try {
    const data = await api('/api/request',{method:'POST',body:JSON.stringify({source_pc:els.source.value})});
    render(data.state);
    setPlaying(true);
    const result=data.result;
    await animatePath(result.animation_path,token);
    if (token !== animationToken) return;
    els.result.classList.toggle('error',!result.reachable);
    els.result.innerHTML = result.reachable ? `<strong>200 OK · Delivered</strong><br>${esc(result.router_path.join(' → '))} · cost ${result.cost}<div class="mini-flights">${result.flights.slice(0,3).map(flight=>`<span><b>${esc(flight.flight)}</b> ${esc(flight.destination)} · ${esc(flight.time)} · ${esc(flight.status)}</span>`).join('')}</div>` : `<strong>Request unreachable</strong><br>${esc(result.message)}`;
    els.result.hidden=false;
  } catch(error) { showNotice(error.message); }
  finally { if(token===animationToken) setPlaying(false); }
});

els.reset.addEventListener('click', async () => {
  animationToken++; setPlaying(false); els.packetLayer.innerHTML='';
  try { const data=await api('/api/reset',{method:'POST',body:'{}'}); selectedInspector=null; els.result.hidden=true; els.detail.innerHTML='<p class="eyebrow">Topology inspector</p><h3>Select a device or link</h3><p>Choose an item in the diagram to inspect its addressing or configure a serial connection.</p>'; render(data.state); }
  catch(error){ showNotice(error.message); }
});

els.source.addEventListener('change', async () => {
  try { const data=await api('/api/route',{method:'POST',body:JSON.stringify({source_pc:els.source.value})}); render(data.state); }
  catch(error){ showNotice(error.message); }
});

document.querySelectorAll('[data-device]').forEach(node => {
  const activate=()=>inspectDevice(node.dataset.device); node.addEventListener('click',activate); node.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' ')activate();});
});
document.querySelectorAll('[data-link]').forEach(node => {
  const activate=()=>inspectLink(node.dataset.link); node.addEventListener('click',activate); node.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' ')activate();});
});
els.tabs.addEventListener('click', event => {
  const button=event.target.closest('[data-tab]'); if(!button)return;
  activeTab=button.dataset.tab; els.tabs.querySelectorAll('[role=tab]').forEach(tab=>tab.setAttribute('aria-selected',String(tab===button))); renderTab();
});

api('/api/state').then(data=>render(data.state)).catch(error=>showNotice(`Could not load simulation: ${error.message}`));
