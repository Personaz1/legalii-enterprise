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
    return `<tr><td>${it.id||''}</td><td>${(it.report||{}).case_id||''}</td><td>${it.status||''}</td><td>${issues}</td><td><button data-fill-id="${it.id||''}">Use</button></td></tr>`;
  }).join('')}</tbody></table>`;
  wrap.querySelectorAll('button[data-fill-id]').forEach(btn => {
    btn.onclick = () => { document.getElementById('reviewId').value = btn.dataset.fillId || ''; };
  });
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

  document.getElementById('refreshAllBtn').onclick = async () => {
    await checkHealth();
    try { await loadQueue(); } catch {}
  };
}

setTabs();
bindActions();
checkHealth();