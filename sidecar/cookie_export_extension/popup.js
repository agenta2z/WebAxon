// WebAxon Cookie Export — Chrome Extension Popup Script
// Uses chrome.cookies API to get ALL cookies (including HttpOnly)

function setStatus(type, message) {
  const box = document.getElementById('statusBox');
  box.className = 'status ' + type;
  box.innerHTML = message;
}

async function exportCookies() {
  const btn = document.getElementById('exportBtn');
  btn.disabled = true;
  btn.textContent = 'Exporting...';

  try {
    const sidecarUrl = document.getElementById('sidecarUrl').value.trim();
    const sessionId = document.getElementById('sessionId').value.trim();
    const token = document.getElementById('token').value.trim();
    let domain = document.getElementById('domain').value.trim();

    if (!sessionId || !token) {
      setStatus('error', 'Session ID and Token are required');
      btn.disabled = false;
      btn.textContent = 'Export Cookies';
      return;
    }

    // If no domain specified, use current tab's domain
    if (!domain) {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab && tab.url) {
        const url = new URL(tab.url);
        domain = url.hostname;
      }
    }

    setStatus('info', `Fetching cookies for ${domain}...`);

    // Use chrome.cookies API — gets ALL cookies including HttpOnly!
    const cookies = await chrome.cookies.getAll({ domain: domain });

    // Also get cookies for subdomains (e.g., .atlassian.net)
    const parts = domain.split('.');
    let parentDomainCookies = [];
    if (parts.length > 2) {
      const parentDomain = parts.slice(-2).join('.');
      parentDomainCookies = await chrome.cookies.getAll({ domain: '.' + parentDomain });
    }

    // Merge and deduplicate
    const allCookies = [...cookies];
    const seen = new Set(cookies.map(c => c.name + '::' + c.domain));
    for (const c of parentDomainCookies) {
      const key = c.name + '::' + c.domain;
      if (!seen.has(key)) {
        allCookies.push(c);
        seen.add(key);
      }
    }

    document.getElementById('cookieCount').textContent =
      `Found ${allCookies.length} cookies (${allCookies.filter(c => c.httpOnly).length} HttpOnly)`;

    if (allCookies.length === 0) {
      setStatus('error', `No cookies found for ${domain}. Make sure you're logged in.`);
      btn.disabled = false;
      btn.textContent = 'Export Cookies';
      return;
    }

    // Format cookies for WebAxon
    const formattedCookies = allCookies.map(c => ({
      name: c.name,
      value: c.value,
      domain: c.domain,
      path: c.path,
      secure: c.secure,
      httpOnly: c.httpOnly,
      sameSite: c.sameSite || 'unspecified',
      expirationDate: c.expirationDate || null,
    }));

    // Send to sidecar
    setStatus('info', 'Sending cookies to WebAxon sidecar...');

    const response = await fetch(sidecarUrl + '/auth/cookies', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        token: token,
        cookies: formattedCookies,
      }),
    });

    const result = await response.json();

    if (result.ok) {
      setStatus('success',
        `✅ Exported ${allCookies.length} cookies to WebAxon!<br>` +
        `(${allCookies.filter(c => c.httpOnly).length} HttpOnly cookies included)<br>` +
        'The remote browser should now be authenticated.'
      );
      btn.textContent = '✅ Done!';
    } else {
      throw new Error(result.error || 'Unknown error');
    }

  } catch (err) {
    setStatus('error', '❌ Error: ' + err.message);
    btn.disabled = false;
    btn.textContent = 'Retry Export';
  }
}

// Auto-fill from URL parameters if opened via relay link
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get('session_id')) {
  document.getElementById('sessionId').value = urlParams.get('session_id');
}
if (urlParams.get('token')) {
  document.getElementById('token').value = urlParams.get('token');
}
if (urlParams.get('domain')) {
  document.getElementById('domain').value = urlParams.get('domain');
}
if (urlParams.get('sidecar_url')) {
  document.getElementById('sidecarUrl').value = urlParams.get('sidecar_url');
}
