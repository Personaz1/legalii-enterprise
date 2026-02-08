const out = document.getElementById('out');
const health = document.getElementById('health');
const API = '/api/v1/pilot';

function authHeaders(){
  const key = localStorage.getItem('legalii_api_key') || '';
  return key ? {'x-api-key': key} : {};
}

async function j(url, opts={}) {
  const headers = {...authHeaders(), ...(opts.headers || {})};
  const r = await fetch(url, {...opts, headers});
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

function show(data){ if (out) out.textContent = JSON.stringify(data, null, 2); }

function setTabs(){
  for (const t of document.querySelectorAll('.tab')) {
    t.onclick = () => {
      document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
      document.querySelectorAll('.pane').forEach(x=>x.classList.remove('active'));
      t.classList.add('active');
      document.querySelector(`.pane[data-pane="${t.dataset.tab}"]`)?.classList.add('active');
    };
  }
}

async function checkHealth(){
  try{ const h = await j('/health'); health.textContent = h.status === 'ok' ? 'healthy' : 'degraded'; }
  catch{ health.textContent = 'offline'; }
}

async function loadQueue(){
  const q = await j(`${API}/review-queue?status=pending`);
  renderReviewTable(q.items || []);
}

function renderReviewTable(items){
  const wrap = document.getElementById('reviewTableWrap');
  if (!wrap) return;
  if (!items.length) { wrap.innerHTML = '<div style="padding:12px">No pending items.</div>'; return; }
  wrap.innerHTML = `<table><thead><tr><th>ID</th><th>Case</th><th>Status</th><th>Issues</th><th>Action</th></tr></thead><tbody>${items.map(it => {
    const issues = ((it.review||{}).issues||[]).slice(0,3).join(', ');
    return `<tr><td>${it.id||''}</td><td>${(it.case_ref||((it.report||{}).case_id)||'')}</td><td>${it.status||''}</td><td>${issues}</td><td><button data-fill-id="${it.id||''}">Use</button></td></tr>`;
  }).join('')}</tbody></table>`;
  wrap.querySelectorAll('button[data-fill-id]').forEach(btn => {
    btn.onclick = () => { document.getElementById('reviewId').value = btn.dataset.fillId || ''; };
  });
}

async function loadCases(){
  const q = encodeURIComponent((document.getElementById('casesQuery')?.value || '').trim());
  const status = encodeURIComponent((document.getElementById('casesStatus')?.value || '').trim());
  const r = await j(`/api/v1/cases?limit=200&q=${q}&status=${status}`);
  const wrap = document.getElementById('casesTableWrap');
  if (!wrap) return;
  const items = r.items || [];
  if (!items.length){ wrap.innerHTML = '<div style="padding:12px">No cases.</div>'; return; }
  wrap.innerHTML = `<table><thead><tr><th>ID</th><th>Client</th><th>Title</th><th>Type</th><th>Status</th><th>Reports</th></tr></thead><tbody>${items.map(c=>`<tr data-case-id="${c.id}"><td>${c.id||''}</td><td>${c.client_name||''}</td><td>${c.title||''}</td><td>${c.case_type||''}</td><td>${c.status||''}</td><td>${c.reports_count||0}</td></tr>`).join('')}</tbody></table>`;
  wrap.querySelectorAll('tr[data-case-id]').forEach(tr=>{
    tr.onclick=()=>{ document.getElementById('caseId').value = tr.dataset.caseId || ''; };
  });
}

async function loadCaseDetail(){
  const caseId = (document.getElementById('caseId')?.value || '').trim();
  if (!caseId) return alert('case id required');
  const c = await j(`/api/v1/cases/${encodeURIComponent(caseId)}`);
  const r = await j(`/api/v1/cases/${encodeURIComponent(caseId)}/reports?limit=100`);
  document.getElementById('caseTitle').value = c.case?.title || '';
  document.getElementById('caseClient').value = c.case?.client_name || '';
  if (c.case?.case_type) document.getElementById('caseType').value = c.case.case_type;
  if (c.case?.status) document.getElementById('caseStatus').value = c.case.status;
  document.getElementById('caseDetailOut').textContent = JSON.stringify({case: c.case, reports: r.items}, null, 2);
}

function bindActions(){
  const apiKeyInput = document.getElementById('apiKey');
  if (apiKeyInput) apiKeyInput.value = localStorage.getItem('legalii_api_key') || '';

  document.getElementById('saveKeyBtn').onclick = () => {
    const v = (apiKeyInput.value || '').trim();
    if (v) localStorage.setItem('legalii_api_key', v);
    else localStorage.removeItem('legalii_api_key');
    alert('Key saved');
  };

  document.getElementById('loginBtn').onclick = async () => {
    try {
      const username = document.getElementById('username').value.trim();
      const password = document.getElementById('password').value;
      if (!username || !password) return alert('Enter username/password');
      const r = await j('/api/v1/auth/login', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({username, password})
      });
      localStorage.setItem('legalii_api_key', r.token);
      apiKeyInput.value = r.token;
      alert(`Logged in as ${r.identity.user} (${r.identity.role})`);
    } catch (e) { alert(String(e)); }
  };

  document.getElementById('whoamiBtn').onclick = async () => show(await j('/api/v1/auth/me'));

  document.getElementById('uploadBtn').onclick = async () => {
    const f = document.getElementById('file').files[0];
    if(!f) return alert('Select file first');
    const fd = new FormData(); fd.append('file', f);
    show(await j(`${API}/analyze-upload`, { method:'POST', body:fd }));
  };

  document.getElementById('batchBtn').onclick = async () => {
    const files = document.getElementById('file').files;
    if(!files || !files.length) return alert('Select files first');
    const fd = new FormData();
    for (const f of files) fd.append('files', f);
    show(await j(`${API}/analyze-batch`, { method:'POST', body:fd }));
  };

  for (const b of document.querySelectorAll('button[data-sample]')) {
    b.onclick = async () => {
      const sample = b.dataset.sample;
      const caseData = await j(`${API}/sample/${sample}`);
      show(await j(`${API}/analyze`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ case_data: caseData })
      }));
    };
  }

  document.getElementById('loadQueueBtn').onclick = loadQueue;
  document.getElementById('resolveReviewBtn').onclick = async () => {
    const id = document.getElementById('reviewId').value.trim();
    const decision = document.getElementById('reviewDecision').value;
    const note = document.getElementById('reviewNote').value.trim() || 'resolved from UI';
    if (!id) return alert('Enter review id');
    show(await j(`${API}/review-resolve`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id, decision, note})
    }));
    await loadQueue();
  };

  document.getElementById('loadConfigBtn').onclick = async () => {
    document.getElementById('configOut').textContent = JSON.stringify(await j('/api/v1/system/config'), null, 2);
  };

  document.getElementById('listUsersBtn').onclick = async () => {
    document.getElementById('usersOut').textContent = JSON.stringify(await j('/api/v1/auth/users'), null, 2);
  };

  document.getElementById('upsertUserBtn').onclick = async () => {
    const payload = {
      username: document.getElementById('newUsername').value.trim(),
      password: document.getElementById('newPassword').value,
      role: document.getElementById('newRole').value,
      enabled: document.getElementById('newEnabled').value === 'true',
    };
    show(await j('/api/v1/auth/users', {
      method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)
    }));
    document.getElementById('usersOut').textContent = JSON.stringify(await j('/api/v1/auth/users'), null, 2);
  };

  document.getElementById('createCaseBtn').onclick = async () => {
    const payload = {
      case_id: document.getElementById('caseId').value.trim(),
      title: document.getElementById('caseTitle').value.trim(),
      client_name: document.getElementById('caseClient').value.trim(),
      case_type: document.getElementById('caseType').value,
      status: document.getElementById('caseStatus').value,
      owner: '',
      case_data: {},
    };
    if (!payload.case_id) return alert('case id required');
    show(await j('/api/v1/cases', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)}));
    await loadCases();
  };

  document.getElementById('loadCasesBtn').onclick = loadCases;
  document.getElementById('loadCaseDetailBtn').onclick = loadCaseDetail;
  document.getElementById('updateCaseBtn').onclick = async () => {
    const caseId = document.getElementById('caseId').value.trim();
    if (!caseId) return alert('case id required');
    const payload = {
      title: document.getElementById('caseTitle').value.trim(),
      client_name: document.getElementById('caseClient').value.trim(),
      status: document.getElementById('caseStatus').value,
      case_type: document.getElementById('caseType').value,
    };
    show(await j(`/api/v1/cases/${encodeURIComponent(caseId)}`, {method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)}));
    await loadCases();
    await loadCaseDetail();
  };

  document.getElementById('caseAnalyzeBtn').onclick = async () => {
    const caseId = document.getElementById('caseId').value.trim();
    if (!caseId) return alert('case id required');
    const f = document.getElementById('file').files[0];
    if (!f) return alert('select file first');
    const fd = new FormData(); fd.append('file', f);
    show(await j(`/api/v1/cases/${encodeURIComponent(caseId)}/analyze-upload`, {method:'POST', body: fd}));
    await loadCases();
    await loadCaseDetail();
  };

  document.getElementById('exportDossierMdBtn').onclick = async () => {
    const caseId = document.getElementById('caseId').value.trim();
    if (!caseId) return alert('case id required');
    const txt = await fetch(`/api/v1/cases/${encodeURIComponent(caseId)}/dossier-markdown`, {headers: authHeaders()}).then(r=>r.text());
    document.getElementById('caseDetailOut').textContent = txt;
  };

  document.getElementById('exportDossierPdfBtn').onclick = async () => {
    const caseId = document.getElementById('caseId').value.trim();
    if (!caseId) return alert('case id required');
    const resp = await fetch(`/api/v1/cases/${encodeURIComponent(caseId)}/dossier-pdf`, {headers: authHeaders()});
    if (!resp.ok) return alert(`${resp.status} ${await resp.text()}`);
    const blob = await resp.blob();
    window.open(URL.createObjectURL(blob), '_blank');
  };

  document.getElementById('refreshAllBtn').onclick = async () => {
    await checkHealth();
    try { await loadQueue(); } catch {}
    try { await loadCases(); } catch {}
  };
}

setTabs();
bindActions();
checkHealth();
loadCases().catch(()=>{});
