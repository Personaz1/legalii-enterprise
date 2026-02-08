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

async function checkHealth(){
  try{ const h = await j('/health'); health.textContent = h.status === 'ok' ? 'healthy' : 'degraded'; }
  catch{ health.textContent = 'offline'; }
}

function show(data){ out.textContent = JSON.stringify(data, null, 2); }

document.getElementById('uploadBtn').onclick = async () => {
  const f = document.getElementById('file').files[0];
  if(!f) return alert('Select file first');
  const fd = new FormData(); fd.append('file', f);
  const r = await j(`${API}/analyze-upload`, { method:'POST', body:fd });
  show(r);
};

document.getElementById('batchBtn').onclick = async () => {
  const files = document.getElementById('file').files;
  if(!files || !files.length) return alert('Select files first');
  const fd = new FormData();
  for (const f of files) fd.append('files', f);
  const r = await j(`${API}/analyze-batch`, { method:'POST', body:fd });
  show(r);
};

for (const b of document.querySelectorAll('button[data-sample]')) {
  b.onclick = async () => {
    const sample = b.dataset.sample;
    const caseData = await j(`${API}/sample/${sample}`);
    const r = await j(`${API}/analyze`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ case_data: caseData })
    });
    show(r);
  };
}

document.getElementById('loadQueueBtn').onclick = async () => {
  const q = await j(`${API}/review-queue?status=pending`);
  document.getElementById('queueOut').textContent = JSON.stringify(q, null, 2);
};

checkHealth();


const apiKeyInput = document.getElementById('apiKey');
if (apiKeyInput) apiKeyInput.value = localStorage.getItem('legalii_api_key') || '';

document.getElementById('saveKeyBtn').onclick = () => {
  const v = (apiKeyInput.value || '').trim();
  if (v) localStorage.setItem('legalii_api_key', v);
  else localStorage.removeItem('legalii_api_key');
  alert('Key saved');
};

document.getElementById('loginBtn').onclick = async () => {
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
};

document.getElementById('resolveReviewBtn').onclick = async () => {
  const id = document.getElementById('reviewId').value.trim();
  const decision = document.getElementById('reviewDecision').value;
  const note = document.getElementById('reviewNote').value.trim() || 'resolved from UI';
  if (!id) return alert('Enter review id');
  const r = await j(`${API}/review-resolve`, {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({id, decision, note})
  });
  show(r);
  const q = await j(`${API}/review-queue?status=pending`);
  document.getElementById('queueOut').textContent = JSON.stringify(q, null, 2);
};
