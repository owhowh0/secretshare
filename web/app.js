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
function randomString(length = 64) {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~';
  const bytes = new Uint8Array(length);
  window.crypto.getRandomValues(bytes);
  return Array.from(bytes).map(b => chars[b % chars.length]).join('');
}

async function sha256Challenge(verifier) {
  const data = new TextEncoder().encode(verifier);
  const hash = await window.crypto.subtle.digest('SHA-256', data);
  return btoa(String.fromCharCode(...new Uint8Array(hash)))
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
