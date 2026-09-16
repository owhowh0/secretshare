// Path-based dynamic base URL (supports local / and preview /pr-<N>)
const basePath = window.location.pathname.match(/^(\/pr-\d+)/)?.[1] || '';
const API = `${basePath}/api`;
const KEYCLOAK = `${basePath}/keycloak`;
const REALM = 'secretshare';
const CLIENT_ID = 'secretshare-api';

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function getHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  const token = sessionStorage.getItem('token');
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

// --- PKCE OAuth Helpers ---
// Pure JS SHA-256 fallback for non-secure contexts (e.g. HTTP on staging-server where window.crypto.subtle is undefined)
function sha256Sync(ascii) {
  function rightRotate(value, amount) {
    return (value >>> amount) | (value << (32 - amount));
  }
  const mathPow = Math.pow;
  const maxWord = mathPow(2, 32);
  const lengthProperty = 'length';
  let i, j;

  const words = [];
  const asciiBitLength = ascii[lengthProperty] * 8;

  let hash = [];
  const k = [];
  let primeCounter = 0;

  const isComposite = {};
  for (let candidate = 2; primeCounter < 64; candidate++) {
    if (!isComposite[candidate]) {
      for (i = 0; i < 313; i += candidate) {
        isComposite[i] = candidate;
      }
      hash[primeCounter] = (mathPow(candidate, 0.5) * maxWord) | 0;
      k[primeCounter++] = (mathPow(candidate, 1 / 3) * maxWord) | 0;
    }
  }

  ascii += '\x80';
  while ((ascii[lengthProperty] % 64) - 56) ascii += '\x00';
  for (i = 0; i < ascii[lengthProperty]; i++) {
    j = ascii.charCodeAt(i);
    words[i >> 2] |= j << ((3 - i) % 4) * 8;
  }
  words[words[lengthProperty]] = (asciiBitLength / maxWord) | 0;
  words[words[lengthProperty]] = asciiBitLength;

  for (j = 0; j < words[lengthProperty]; ) {
    const w = words.slice(j, (j += 16));
    const oldHash = hash;
    hash = hash.slice(0, 8);

    for (i = 0; i < 64; i++) {
      const w15 = w[i - 15], w2 = w[i - 2];
      const s0 = rightRotate(w15, 7) ^ rightRotate(w15, 18) ^ (w15 >>> 3);
      const s1 = rightRotate(w2, 17) ^ rightRotate(w2, 19) ^ (w2 >>> 10);
      w[i] = (i < 16) ? (w[i] || 0) : (w[i - 16] + s0 + w[i - 7] + s1) | 0;

      const s1h = rightRotate(hash[4], 6) ^ rightRotate(hash[4], 11) ^ rightRotate(hash[4], 25);
      const ch = (hash[4] & hash[5]) ^ (~hash[4] & hash[6]);
      const temp1 = hash[7] + s1h + ch + k[i] + w[i];
      const s0h = rightRotate(hash[0], 2) ^ rightRotate(hash[0], 13) ^ rightRotate(hash[0], 22);
      const maj = (hash[0] & hash[1]) ^ (hash[0] & hash[2]) ^ (hash[1] & hash[2]);
      const temp2 = s0h + maj;

      hash = [(temp1 + temp2) | 0].concat(hash);
      hash[4] = (hash[4] + temp1) | 0;
    }

    for (i = 0; i < 8; i++) {
      hash[i] = (hash[i] + oldHash[i]) | 0;
    }
  }

  const rawBytes = [];
  for (i = 0; i < 8; i++) {
    for (let b = 3; b >= 0; b--) {
      rawBytes.push((hash[i] >> (b * 8)) & 255);
    }
  }
  return new Uint8Array(rawBytes);
}

function randomString(length = 64) {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~';
  const bytes = new Uint8Array(length);
  if (window.crypto && window.crypto.getRandomValues) {
    window.crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < length; i++) {
      bytes[i] = Math.floor(Math.random() * 256);
    }
  }
  return Array.from(bytes).map(b => chars[b % chars.length]).join('');
}

async function sha256Challenge(verifier) {
  let hashBytes;
  if (window.crypto && window.crypto.subtle && window.crypto.subtle.digest) {
    try {
      const data = new TextEncoder().encode(verifier);
      const hash = await window.crypto.subtle.digest('SHA-256', data);
      hashBytes = new Uint8Array(hash);
    } catch (e) {
      hashBytes = sha256Sync(verifier);
    }
  } else {
    hashBytes = sha256Sync(verifier);
  }

  let binary = '';
  for (let i = 0; i < hashBytes.byteLength; i++) {
    binary += String.fromCharCode(hashBytes[i]);
  }
  return btoa(binary)
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

async function login() {
  console.log('Initiating Keycloak OAuth login...');
  try {
    const verifier = randomString();
    sessionStorage.setItem('verifier', verifier);
    const challenge = await sha256Challenge(verifier);

    let redirectUri = window.location.origin + (basePath ? basePath + '/' : '/');
    sessionStorage.setItem('redirectUri', redirectUri);

    const authUrl = `${window.location.origin}${KEYCLOAK}/realms/${REALM}/protocol/openid-connect/auth`;
    const url = new URL(authUrl);
    url.searchParams.set('client_id', CLIENT_ID);
    url.searchParams.set('response_type', 'code');
    url.searchParams.set('scope', 'openid profile email');
    url.searchParams.set('redirect_uri', redirectUri);
    url.searchParams.set('code_challenge', challenge);
    url.searchParams.set('code_challenge_method', 'S256');

    console.log('Redirecting to:', url.toString());
    window.location.href = url.toString();
  } catch (err) {
    console.error('Failed to start login:', err);
    alert('Failed to start login: ' + err.message);
  }
}

async function handleAuthCallback() {
  const params = new URLSearchParams(window.location.search);
  const code = params.get('code');
  if (!code) return;

  const verifier = sessionStorage.getItem('verifier');
  let redirectUri = sessionStorage.getItem('redirectUri') || (window.location.origin + (basePath ? basePath + '/' : '/'));

  // Clean code param from URL without refreshing
  window.history.replaceState({}, document.title, window.location.pathname);

  if (!verifier) {
    console.warn('No PKCE verifier found in sessionStorage');
    return;
  }

  try {
    const tokenUrl = `${KEYCLOAK}/realms/${REALM}/protocol/openid-connect/token`;
    const res = await fetch(tokenUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        grant_type: 'authorization_code',
        client_id: CLIENT_ID,
        code: code,
        redirect_uri: redirectUri,
        code_verifier: verifier,
      }).toString(),
    });

    if (!res.ok) {
      const errBody = await res.text().catch(() => '');
      throw new Error(`Token exchange failed (HTTP ${res.status}): ${errBody}`);
    }

    const data = await res.json();
    sessionStorage.setItem('token', data.access_token);
    sessionStorage.removeItem('verifier');
    console.log('OAuth token obtained successfully');
  } catch (err) {
    console.error('OAuth token exchange error:', err);
    alert('OAuth login failed: ' + err.message);
  }
}

async function updateAuthUI() {
  const token = sessionStorage.getItem('token');
  const loginBtn = document.getElementById('login-btn');
  const userInfo = document.getElementById('user-info');
  const usernameSpan = document.getElementById('username');

  if (!loginBtn || !userInfo || !usernameSpan) return;

  if (!token) {
    loginBtn.style.display = 'inline-block';
    userInfo.style.display = 'none';
    return;
  }

  try {
    const res = await fetch(`${API}/me`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (!res.ok) {
      sessionStorage.removeItem('token');
      loginBtn.style.display = 'inline-block';
      userInfo.style.display = 'none';
      return;
    }

    const user = await res.json();
    usernameSpan.textContent = user.preferred_username || user.sub || 'Logged in';
    loginBtn.style.display = 'none';
    userInfo.style.display = 'flex';
  } catch (e) {
    loginBtn.style.display = 'inline-block';
    userInfo.style.display = 'none';
  }
}

function logout() {
  sessionStorage.removeItem('token');
  updateAuthUI();
}

function setupListeners() {
  const createBtn = document.getElementById('create-btn');
  if (createBtn) {
    createBtn.addEventListener('click', async () => {
      const secret = document.getElementById('secret').value.trim();
      if (!secret) return;

      const btn = document.getElementById('create-btn');
      const result = document.getElementById('create-result');
      const error = document.getElementById('create-error');
      btn.disabled = true;
      result.hidden = true;
      error.hidden = true;

      try {
        const res = await fetch(`${API}/secrets`, {
          method: 'POST',
          headers: getHeaders(),
          body: JSON.stringify({ ciphertext: secret }),
        });
        if (!res.ok) throw new Error(`API returned HTTP ${res.status}`);

        const { payload_id } = await res.json();
        result.textContent = payload_id;
        result.hidden = false;
        document.getElementById('secret').value = '';
      } catch (e) {
        error.textContent = e.message;
        error.hidden = false;
      } finally {
        btn.disabled = false;
      }
    });
  }

  const retrieveBtn = document.getElementById('retrieve-btn');
  if (retrieveBtn) {
    retrieveBtn.addEventListener('click', async () => {
      const id = document.getElementById('payload-id').value.trim();
      if (!id) return;

      const btn = document.getElementById('retrieve-btn');
      const result = document.getElementById('retrieve-result');
      const error = document.getElementById('retrieve-error');
      btn.disabled = true;
      result.hidden = true;
      error.hidden = true;

      try {
        const res = await fetch(`${API}/secrets/${id}`, {
          headers: getHeaders(),
        });
        if (res.status === 404) throw new Error('Secret not found or already burned.');
        if (!res.ok) throw new Error(`API returned HTTP ${res.status}`);

        const { ciphertext } = await res.json();
        result.innerHTML = escapeHtml(ciphertext);
        result.hidden = false;
        document.getElementById('payload-id').value = '';
      } catch (e) {
        error.textContent = e.message;
        error.hidden = false;
      } finally {
        btn.disabled = false;
      }
    });
  }

  const loginBtn = document.getElementById('login-btn');
  if (loginBtn) {
    loginBtn.addEventListener('click', login);
  }

  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', logout);
  }
}

// --- Init ---
async function init() {
  setupListeners();
  if (window.location.search.includes('code=')) {
    await handleAuthCallback();
  }
  await updateAuthUI();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
