import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urljoin
import yaml
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WEB_DIR = REPO_ROOT / "web"
INDEX_HTML = WEB_DIR / "index.html"
APP_JS = WEB_DIR / "app.js"
DOCKER_COMPOSE_PREVIEW = REPO_ROOT / "docker-compose.preview.yml"


class TestFrontendAssets:
    """Validates frontend static files and UI contracts."""

    def test_index_html_exists_and_contains_required_elements(self):
        assert INDEX_HTML.is_file(), f"Missing {INDEX_HTML}"
        content = INDEX_HTML.read_text(encoding="utf-8")

        required_ids = [
            'id="login-btn"',
            'id="logout-btn"',
            'id="user-info"',
            'id="username"',
            'id="secret"',
            'id="create-btn"',
            'id="payload-id"',
            'id="retrieve-btn"',
            'id="create-result"',
            'id="retrieve-result"',
        ]
        for element_id in required_ids:
            assert element_id in content, f"Expected {element_id} in web/index.html"

    def test_index_html_avoids_naive_relative_script_src(self):
        """Naive <script src="app.js"> fails RFC 3986 resolution when accessing subpath without trailing slash."""
        content = INDEX_HTML.read_text(encoding="utf-8")
        assert '<script src="app.js"></script>' not in content, (
            "web/index.html must not use naive <script src='app.js'></script> because "
            "it breaks RFC 3986 URL resolution when preview URLs (/pr-<N>) lack a trailing slash."
        )

    def test_index_html_includes_cache_control_headers(self):
        content = INDEX_HTML.read_text(encoding="utf-8")
        assert 'http-equiv="Cache-Control"' in content, "index.html should specify Cache-Control meta tag"

    def test_app_js_syntax_valid(self):
        assert APP_JS.is_file(), f"Missing {APP_JS}"
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed in environment, skipping JS syntax check.")

        proc = subprocess.run(
            [node_bin, "-c", str(APP_JS)],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, f"JS syntax check failed: {proc.stderr}"

    def test_app_js_contains_pkce_and_oauth_contract(self):
        content = APP_JS.read_text(encoding="utf-8")
        assert "randomString" in content
        assert "sha256Challenge" in content
        assert "client_id" in content
        assert "code_verifier" in content
        assert "code_challenge" in content
        assert "sessionStorage.setItem('token'" in content
        assert "${API}/me" in content

    def test_pkce_challenge_works_in_non_secure_context_without_subtle_crypto(self):
        """Validates that PKCE challenge computation succeeds when crypto.subtle is undefined (non-HTTPS)."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed in environment, skipping non-secure context test.")

        # Script simulates browser environment with window.crypto.subtle = undefined
        test_script = f"""
        const fs = require('fs');
        const code = fs.readFileSync('{APP_JS}', 'utf8');
        global.window = {{
            location: {{ pathname: '/pr-9/', origin: 'http://staging-server', search: '' }},
            crypto: {{}} // subtle is explicitly undefined (non-secure HTTP context)
        }};
        global.document = {{ title: 'Test', getElementById: () => null }};
        global.sessionStorage = {{ getItem: () => null, setItem: () => {{}}, removeItem: () => {{}} }};
        global.btoa = (str) => Buffer.from(str, 'binary').toString('base64');

        eval(code);

        (async () => {{
            const verifier = 'dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk';
            const challenge = await sha256Challenge(verifier);
            const expected = 'E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM';
            if (challenge !== expected) {{
                console.error(`Expected ${{expected}}, got ${{challenge}}`);
                process.exit(1);
            }}
            console.log('PKCE RFC 7636 test vector matched successfully without crypto.subtle');
        }})();
        """

        proc = subprocess.run([node_bin, "-e", test_script], capture_output=True, text=True)
        assert proc.returncode == 0, f"Non-secure context PKCE test failed: {proc.stderr}"


class TestPreviewSubpathResolutionEdgeCases:
    """Tests subpath RFC 3986 relative URL resolution and redirect protections."""

    def test_rfc3986_relative_resolution_edge_case(self):
        """Documents why hitting /pr-9 without trailing slash causes /app.js 404."""
        # When user navigates to /pr-9 (no trailing slash):
        naive_resolution = urljoin("http://staging-server/pr-9", "app.js")
        assert naive_resolution == "http://staging-server/app.js", (
            "RFC 3986 treats 'pr-9' as a file in '/', so 'app.js' resolves to root domain /app.js!"
        )

        # When redirected to /pr-9/ (with trailing slash):
        fixed_resolution = urljoin("http://staging-server/pr-9/", "app.js")
        assert fixed_resolution == "http://staging-server/pr-9/app.js"

    def test_js_dynamic_basepath_regex(self):
        """Verifies JS basePath regex logic across multiple URL formats."""
        pattern = re.compile(r"^(\/pr-\d+)")

        # Preview URL without trailing slash
        match = pattern.match("/pr-9")
        assert match is not None
        assert match.group(1) == "/pr-9"

        # Preview URL with trailing slash
        match = pattern.match("/pr-9/")
        assert match is not None
        assert match.group(1) == "/pr-9"

        # Preview URL with sub-resource
        match = pattern.match("/pr-42/api/health")
        assert match is not None
        assert match.group(1) == "/pr-42"

        # Local root URL
        match = pattern.match("/")
        assert match is None

    def test_docker_compose_preview_has_slash_redirect(self):
        """Ensures docker-compose.preview.yml configures Traefik to redirect /pr-N to /pr-N/."""
        assert DOCKER_COMPOSE_PREVIEW.is_file()
        content = DOCKER_COMPOSE_PREVIEW.read_text(encoding="utf-8")
        data = yaml.safe_load(content)

        web_labels = data.get("services", {}).get("web", {}).get("labels", [])
        labels_text = "\n".join(web_labels)

        assert "traefik.http.routers.pr-${PR_NUMBER}-web-redirect.rule=Path(`/pr-${PR_NUMBER}`)" in labels_text, (
            "docker-compose.preview.yml must define web-redirect router for Path(`/pr-${PR_NUMBER}`)"
        )
        assert "redirectregex" in labels_text, "docker-compose.preview.yml must define redirectregex middleware"
