import re
from pathlib import Path
from urllib.parse import urljoin
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WEB_DIR = REPO_ROOT / "web"
APP_PAGE = WEB_DIR / "app" / "page.tsx"
AUTH_TS = WEB_DIR / "lib" / "auth.ts"
PKCE_TS = WEB_DIR / "lib" / "pkce.ts"
NEXT_CONFIG = WEB_DIR / "next.config.ts"
DOCKER_COMPOSE_PREVIEW = REPO_ROOT / "docker-compose.preview.yml"


class TestFrontendAssets:
    """Validates frontend Next.js files and UI contracts."""

    def test_app_page_exists_and_contains_required_elements(self):
        assert APP_PAGE.is_file(), f"Missing {APP_PAGE}"
        content = APP_PAGE.read_text(encoding="utf-8")

        required_snippets = [
            "<h1>SecretShare</h1>",
            'id="auth-section"',
            'id="login-btn"',
            'id="logout-btn"',
            'id="create-btn"',
            'id="retrieve-btn"',
        ]
        for snippet in required_snippets:
            assert snippet in content, f"Expected {snippet} in web/app/page.tsx"

    def test_next_config_enables_standalone_output(self):
        assert NEXT_CONFIG.is_file(), f"Missing {NEXT_CONFIG}"
        content = NEXT_CONFIG.read_text(encoding="utf-8")
        assert "output: 'standalone'" in content
        assert "basePath: process.env.NEXT_PUBLIC_BASE_PATH ?? ''" in content

    def test_auth_module_contains_pkce_and_oauth_contract(self):
        assert AUTH_TS.is_file(), f"Missing {AUTH_TS}"
        content = AUTH_TS.read_text(encoding="utf-8")
        assert "randomString" in content
        assert "sha256Challenge" in content
        assert "client_id" in content
        assert "code_verifier" in content
        assert "code_challenge" in content
        assert "sessionStorage.setItem('token'" in content
        assert "${apiBase}/me" in content

    def test_pkce_module_exposes_random_and_challenge(self):
        assert PKCE_TS.is_file(), f"Missing {PKCE_TS}"
        content = PKCE_TS.read_text(encoding="utf-8")
        assert "export function randomString(length = 64): string" in content
        assert "window.crypto?.getRandomValues" in content
        assert "export async function sha256Challenge(verifier: string): Promise<string>" in content


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
