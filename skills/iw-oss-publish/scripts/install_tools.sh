#!/usr/bin/env bash
# Idempotent tool installer for iw-oss-publish.
# Tier-1 tools are required; Tier-2 are opt-in via --tier2.
# Usage:
#   bash install_tools.sh            # install Tier-1 only
#   bash install_tools.sh --tier2    # install Tier-1 + Tier-2
#   bash install_tools.sh --check    # verify installed versions only, no install
#   bash install_tools.sh --force    # re-install even if already present

set -euo pipefail

TIER2=false
CHECK_ONLY=false
FORCE=false
INSTALL_DIR="${HOME}/.local/bin"

for arg in "$@"; do
  case "$arg" in
    --tier2) TIER2=true ;;
    --check) CHECK_ONLY=true ;;
    --force) FORCE=true ;;
    -h|--help)
      cat <<HLP
Usage: install_tools.sh [--tier2] [--check] [--force]
  --tier2   Also install recommended Tier-2 tools
  --check   Verify installed versions without installing
  --force   Re-install tools even if already present
HLP
      exit 0
      ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

mkdir -p "$INSTALL_DIR"
case ":$PATH:" in
  *":$INSTALL_DIR:"*) ;;
  *) echo "⚠  $INSTALL_DIR is not in \$PATH. Add it to your shell rc." >&2 ;;
esac

# ------------------------------------------------------------------
# Minimum version constraints (must match references/tools.md)
# ------------------------------------------------------------------
declare -A MIN_VER=(
  [gitleaks]="8.20.0"
  [git-filter-repo]="2.47.0"
  [syft]="1.14.0"
  [grant]="0.3.0"
  [grype]="0.85.0"
  [osv-scanner]="2.0.0"
  [pinact]="3.9.0"
  [gh]="2.62.0"
  [pre-commit]="4.0.1"
  [ripgrep]="13.0.0"
)

version_ge() {
  # returns 0 if $1 >= $2 (semver-ish)
  [ "$(printf '%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]
}

tool_version() {
  local tool="$1"
  case "$tool" in
    gitleaks)      gitleaks version 2>/dev/null | awk '{print $1}' | head -1 ;;
    git-filter-repo) git-filter-repo --version 2>/dev/null | awk '{print $NF}' ;;
    syft)          syft version 2>/dev/null | awk '/^Version/ {print $2}' ;;
    grant)         grant version 2>/dev/null | awk '/^Version/ {print $2}' ;;
    grype)         grype version 2>/dev/null | awk '/^Version/ {print $2}' ;;
    osv-scanner)   osv-scanner --version 2>/dev/null | awk '/^osv-scanner version:/ {print $NF}' ;;
    pinact)        pinact --version 2>/dev/null | awk '/pinact version/ {print $NF; exit}' | tr -d 'v' ;;
    gh)            gh --version 2>/dev/null | awk '/^gh version/ {print $3}' ;;
    pre-commit)    pre-commit --version 2>/dev/null | awk '{print $NF}' ;;
    ripgrep)       rg --version 2>/dev/null | awk 'NR==1 {print $2}' ;;
    trufflehog)    trufflehog --version 2>/dev/null 2>&1 | awk '{print $NF}' | head -1 ;;
    semgrep)       semgrep --version 2>/dev/null ;;
    licensee)      licensee version 2>/dev/null | awk '{print $NF}' ;;
    pip-licenses)  pip-licenses --version 2>/dev/null | awk '{print $NF}' ;;
    cosign)        cosign version 2>/dev/null | awk '/^GitVersion/ {print $2}' | tr -d 'v' ;;
    git-sizer)     git-sizer --version 2>/dev/null | awk '{print $NF}' | tr -d 'v' ;;
    reuse)         reuse --version 2>/dev/null | awk '{print $NF}' ;;
    detect-secrets) detect-secrets --version 2>/dev/null | awk '{print $NF}' ;;
    pip-audit)     pip-audit --version 2>/dev/null | awk '{print $NF}' ;;
    cargo-audit)   cargo audit --version 2>/dev/null | awk '{print $NF}' ;;
    govulncheck)   govulncheck -version 2>/dev/null | head -1 | awk '{print $NF}' ;;
    license-checker) license-checker --version 2>/dev/null ;;
    go-licenses)   go-licenses --help >/dev/null 2>&1 && echo "installed" ;;
    *)             echo "" ;;
  esac
}

# Map logical tool names to their actual binary names.
tool_binary() {
  case "$1" in
    ripgrep)       echo "rg" ;;
    cargo-audit)   echo "cargo" ;;
    *)             echo "$1" ;;
  esac
}

# Python libraries are verified via `python3 -c "import X"` instead of which(binary).
is_python_lib() {
  case "$1" in
    jinja2) return 0 ;;
    *)      return 1 ;;
  esac
}

check_tool() {
  local tool="$1" min="${2:-}"
  # Python-lib dependencies use import-check, not which()
  if is_python_lib "$tool"; then
    local v; v=$(python3 -c "import ${tool}; print(${tool}.__version__)" 2>/dev/null || echo "")
    if [ -z "$v" ]; then
      printf "  ✗ %-18s missing\n" "$tool"
      return 1
    fi
    printf "  ✓ %-18s %s\n" "$tool" "$v"
    return 0
  fi
  local binary; binary=$(tool_binary "$tool")
  if ! command -v "$binary" >/dev/null 2>&1; then
    printf "  ✗ %-18s missing\n" "$tool"
    return 1
  fi
  local v; v=$(tool_version "$tool" 2>/dev/null || echo "?")
  if [ -z "$v" ] || [ "$v" = "?" ]; then
    printf "  ✓ %-18s installed (version unknown)\n" "$tool"
    return 0
  fi
  if [ -n "$min" ] && ! version_ge "$v" "$min"; then
    printf "  ⚠ %-18s %s (min %s)\n" "$tool" "$v" "$min"
    return 2
  fi
  printf "  ✓ %-18s %s\n" "$tool" "$v"
  return 0
}

# ------------------------------------------------------------------
# Install helpers
# ------------------------------------------------------------------
os_arch() {
  case "$(uname -s)" in
    Linux)  echo "linux" ;;
    Darwin) echo "darwin" ;;
    *)      echo "unsupported" ;;
  esac
}
OS=$(os_arch)
[ "$OS" = "unsupported" ] && { echo "Unsupported OS: $(uname -s)" >&2; exit 2; }

# ------------------------------------------------------------------
# Download helpers
# ------------------------------------------------------------------
# gh_download <repo> <pattern> <workdir>
#   Uses `gh release download` if gh is authenticated; returns the path of
#   the downloaded asset on stdout and 0 on success. Returns non-zero if gh
#   is unavailable or the download fails.
gh_download() {
  local repo="$1" pattern="$2" workdir="$3"
  command -v gh >/dev/null 2>&1 || return 1
  gh auth status >/dev/null 2>&1 || return 1
  mkdir -p "$workdir"
  gh release download -R "$repo" --pattern "$pattern" --dir "$workdir" >/dev/null 2>&1 || return 1
  # Echo first matching asset path
  ls "$workdir"/$pattern 2>/dev/null | head -1
}

# extract_and_install <tarball> <member> <dest_name>
#   Extract <member> (file name inside the tarball) and move it to ~/.local/bin/<dest_name>.
#   Safely handles both "direct" tarballs (member at root) and "nested" tarballs (member inside a single top-level dir).
extract_and_install() {
  local tarball="$1" member="$2" dest="$3"
  local tmpdir; tmpdir=$(mktemp -d)
  tar -xzf "$tarball" -C "$tmpdir"
  local src
  src=$(find "$tmpdir" -name "$member" -type f | head -1)
  [ -n "$src" ] || { echo "    $member not found in $tarball" >&2; rm -rf "$tmpdir"; return 1; }
  mv -f "$src" "$INSTALL_DIR/$dest"
  chmod +x "$INSTALL_DIR/$dest"
  rm -rf "$tmpdir"
}

install_gitleaks() {
  local work; work=$(mktemp -d)
  local tarball
  tarball=$(gh_download "gitleaks/gitleaks" "gitleaks_*_${OS}_x64.tar.gz" "$work") || true
  if [ -z "$tarball" ]; then
    # Fallback: get the tag via GitHub API then construct URL (avoids 404 on /latest/download pattern)
    local tag
    tag=$(curl -sSfL "https://api.github.com/repos/gitleaks/gitleaks/releases/latest" \
      | grep -m1 '"tag_name"' | cut -d'"' -f4 | sed 's/^v//')
    [ -n "$tag" ] || { echo "    gitleaks: unable to resolve latest tag" >&2; return 1; }
    tarball="$work/gitleaks_${tag}_${OS}_x64.tar.gz"
    curl -sSfL "https://github.com/gitleaks/gitleaks/releases/download/v${tag}/gitleaks_${tag}_${OS}_x64.tar.gz" -o "$tarball"
  fi
  extract_and_install "$tarball" "gitleaks" "gitleaks"
  rm -rf "$work"
}

install_git_filter_repo() {
  if command -v uv >/dev/null 2>&1; then
    uv tool install git-filter-repo
  elif command -v pipx >/dev/null 2>&1; then
    pipx install git-filter-repo
  else
    pip install --user git-filter-repo
  fi
}

install_syft() {
  curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh \
    | sh -s -- -b "$INSTALL_DIR"
}

install_grant() {
  curl -sSfL https://raw.githubusercontent.com/anchore/grant/main/install.sh \
    | sh -s -- -b "$INSTALL_DIR"
}

install_grype() {
  curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh \
    | sh -s -- -b "$INSTALL_DIR"
}

install_osv_scanner() {
  # Prefer the gh release download path — it always lands on the current
  # major (v2.x today) and writes directly to $INSTALL_DIR, so it survives
  # a $PATH that doesn't include $GOPATH/bin.
  local work; work=$(mktemp -d)
  local asset
  asset=$(gh_download "google/osv-scanner" "osv-scanner_${OS}_amd64" "$work") || true
  if [ -n "$asset" ]; then
    mv -f "$asset" "$INSTALL_DIR/osv-scanner"
    chmod +x "$INSTALL_DIR/osv-scanner"
    rm -rf "$work"
    return 0
  fi
  rm -rf "$work"
  if command -v go >/dev/null 2>&1; then
    # GOBIN forces install into $INSTALL_DIR (otherwise binaries land in
    # $GOPATH/bin which is not on $PATH on GitHub runners). The /v2/
    # segment is required for go install @latest to resolve to the v2.x
    # major line — without it Go fetches the stale v1 series.
    GOBIN="$INSTALL_DIR" go install github.com/google/osv-scanner/v2/cmd/osv-scanner@latest
  else
    local url="https://github.com/google/osv-scanner/releases/latest/download/osv-scanner_${OS}_amd64"
    curl -sSfL "$url" -o "$INSTALL_DIR/osv-scanner"
    chmod +x "$INSTALL_DIR/osv-scanner"
  fi
}

install_pinact() {
  # Prefer gh release download — covers environments without a Go toolchain.
  local work; work=$(mktemp -d)
  local tarball
  tarball=$(gh_download "suzuki-shunsuke/pinact" "pinact_${OS}_amd64.tar.gz" "$work") || true
  if [ -n "$tarball" ]; then
    extract_and_install "$tarball" "pinact" "pinact"
    rm -rf "$work"
    return 0
  fi
  rm -rf "$work"
  if command -v go >/dev/null 2>&1; then
    # GOBIN puts the binary on $PATH; /v3/ is required for @latest to
    # resolve to the current major (v3.x). Without it Go silently picks
    # the last v1 tag (v1.6.0) which is far below MIN_VER[pinact].
    GOBIN="$INSTALL_DIR" go install github.com/suzuki-shunsuke/pinact/v3/cmd/pinact@latest
  else
    echo "  pinact: gh release download failed and go toolchain missing." >&2
    echo "    Either authenticate gh (gh auth login) or install Go: https://go.dev/dl/" >&2
    return 1
  fi
}

install_gh() {
  if [ "$OS" = "linux" ]; then
    echo "  gh: install via package manager. Instructions: https://github.com/cli/cli#installation" >&2
    return 1
  else
    brew install gh
  fi
}

install_pre_commit() {
  if command -v uv >/dev/null 2>&1; then
    uv tool install pre-commit
  elif command -v pipx >/dev/null 2>&1; then
    pipx install pre-commit
  else
    pip install --user pre-commit
  fi
}

install_jinja2() {
  # Python library needed by make_oss mode for template rendering.
  # Prefer uv pip install to isolate from system Python.
  if python3 -c "import jinja2" >/dev/null 2>&1; then
    return 0
  fi
  pip install --user jinja2 >/dev/null 2>&1 || return 1
}

install_ripgrep() {
  # Prefer gh release download (no sudo needed), then apt/brew fallbacks.
  local work; work=$(mktemp -d)
  local pattern
  if [ "$OS" = "linux" ]; then
    pattern="ripgrep-*-x86_64-unknown-linux-musl.tar.gz"
  else
    pattern="ripgrep-*-x86_64-apple-darwin.tar.gz"
  fi
  local tarball
  tarball=$(gh_download "BurntSushi/ripgrep" "$pattern" "$work") || true
  if [ -n "$tarball" ]; then
    extract_and_install "$tarball" "rg" "rg"
    rm -rf "$work"
    return 0
  fi
  rm -rf "$work"
  if [ "$OS" = "linux" ] && command -v apt-get >/dev/null && sudo -n true >/dev/null 2>&1; then
    sudo -n apt-get install -y ripgrep
  elif [ "$OS" = "darwin" ] && command -v brew >/dev/null 2>&1; then
    brew install ripgrep
  else
    echo "  ripgrep: gh release download failed and no passwordless sudo / brew available." >&2
    echo "    Authenticate gh (gh auth login) or install manually via your package manager." >&2
    return 1
  fi
}

install_trufflehog() {
  curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh \
    | sh -s -- -b "$INSTALL_DIR"
}

install_semgrep() {
  if command -v uv >/dev/null 2>&1; then
    uv tool install semgrep
  else
    pip install --user semgrep
  fi
}

install_licensee() {
  if ! command -v gem >/dev/null 2>&1; then
    echo "  licensee: Ruby/gem required. Skipping." >&2
    return 1
  fi
  gem install licensee
}

install_pip_licenses() {
  if command -v uv >/dev/null 2>&1; then
    uv tool install pip-licenses
  else
    pip install --user pip-licenses
  fi
}

install_cosign() {
  if command -v go >/dev/null 2>&1; then
    go install github.com/sigstore/cosign/v2/cmd/cosign@latest
  else
    local url="https://github.com/sigstore/cosign/releases/latest/download/cosign-${OS}-amd64"
    curl -sSfL "$url" -o "$INSTALL_DIR/cosign"
    chmod +x "$INSTALL_DIR/cosign"
  fi
}

install_git_sizer() {
  if command -v go >/dev/null 2>&1; then
    go install github.com/github/git-sizer@latest
  else
    echo "  git-sizer: go toolchain required" >&2
    return 1
  fi
}

install_reuse() {
  if command -v uv >/dev/null 2>&1; then
    uv tool install reuse
  else
    pip install --user reuse
  fi
}

install_detect_secrets() {
  if command -v uv >/dev/null 2>&1; then
    uv tool install detect-secrets
  else
    pip install --user detect-secrets
  fi
}

install_pip_audit() {
  if command -v uv >/dev/null 2>&1; then
    uv tool install pip-audit
  else
    pip install --user pip-audit
  fi
}

install_govulncheck() {
  if command -v go >/dev/null 2>&1; then
    go install golang.org/x/vuln/cmd/govulncheck@latest
  else
    echo "  govulncheck: go toolchain required" >&2
    return 1
  fi
}

install_go_licenses() {
  if command -v go >/dev/null 2>&1; then
    go install github.com/google/go-licenses@latest
  else
    echo "  go-licenses: go toolchain required" >&2
    return 1
  fi
}

install_license_checker() {
  if command -v npm >/dev/null 2>&1; then
    npm install -g license-checker
  else
    echo "  license-checker: npm required" >&2
    return 1
  fi
}

install_cargo_audit() {
  if command -v cargo >/dev/null 2>&1; then
    cargo install cargo-audit
  else
    echo "  cargo-audit: cargo required" >&2
    return 1
  fi
}

# ------------------------------------------------------------------
# Tier 1 — required
# ------------------------------------------------------------------
TIER1=(gitleaks git-filter-repo ripgrep syft grant grype osv-scanner pinact gh pre-commit jinja2)

declare -A INSTALLER=(
  [gitleaks]=install_gitleaks
  [git-filter-repo]=install_git_filter_repo
  [ripgrep]=install_ripgrep
  [syft]=install_syft
  [grant]=install_grant
  [grype]=install_grype
  [osv-scanner]=install_osv_scanner
  [pinact]=install_pinact
  [gh]=install_gh
  [pre-commit]=install_pre_commit
  [jinja2]=install_jinja2
  [trufflehog]=install_trufflehog
  [semgrep]=install_semgrep
  [licensee]=install_licensee
  [pip-licenses]=install_pip_licenses
  [cosign]=install_cosign
  [git-sizer]=install_git_sizer
  [reuse]=install_reuse
  [detect-secrets]=install_detect_secrets
  [pip-audit]=install_pip_audit
  [govulncheck]=install_govulncheck
  [go-licenses]=install_go_licenses
  [license-checker]=install_license_checker
  [cargo-audit]=install_cargo_audit
)

# Tier 2 — recommended
TIER2_TOOLS=(trufflehog semgrep licensee pip-licenses cosign git-sizer reuse detect-secrets pip-audit govulncheck go-licenses license-checker cargo-audit)

ensure() {
  local tool="$1"
  if is_python_lib "$tool"; then
    if [ "$FORCE" = false ] && python3 -c "import ${tool}" >/dev/null 2>&1; then
      return 0
    fi
  else
    local binary; binary=$(tool_binary "$tool")
    if [ "$FORCE" = false ] && command -v "$binary" >/dev/null 2>&1; then
      return 0
    fi
  fi
  local fn="${INSTALLER[$tool]:-}"
  if [ -z "$fn" ]; then
    echo "  No installer for $tool" >&2
    return 1
  fi
  echo "  installing $tool..."
  "$fn" || echo "  ⚠ $tool installation failed; see messages above" >&2
}

# ------------------------------------------------------------------
# Execute
# ------------------------------------------------------------------
if [ "$CHECK_ONLY" = true ]; then
  echo "Tier 1 (required):"
  rc=0
  for t in "${TIER1[@]}"; do
    check_tool "$t" "${MIN_VER[$t]:-}" || rc=$?
  done
  if [ "$TIER2" = true ]; then
    echo
    echo "Tier 2 (recommended):"
    for t in "${TIER2_TOOLS[@]}"; do
      check_tool "$t" "" || true
    done
  fi
  exit "$rc"
fi

echo "Installing Tier 1 tools (required)..."
for t in "${TIER1[@]}"; do
  ensure "$t"
done

if [ "$TIER2" = true ]; then
  echo
  echo "Installing Tier 2 tools (recommended)..."
  for t in "${TIER2_TOOLS[@]}"; do
    ensure "$t"
  done
fi

echo
echo "Verifying installations..."
echo "Tier 1:"
rc=0
for t in "${TIER1[@]}"; do
  check_tool "$t" "${MIN_VER[$t]:-}" || rc=$?
done
if [ "$TIER2" = true ]; then
  echo
  echo "Tier 2:"
  for t in "${TIER2_TOOLS[@]}"; do
    check_tool "$t" "" || true
  done
fi

echo
if [ "$rc" -eq 0 ]; then
  echo "✓ All required tools installed."
else
  echo "⚠ Some Tier-1 tools are missing or below minimum version. See output above." >&2
  echo "  Re-run with --force to force reinstall, or install manually per references/tools.md" >&2
fi

exit "$rc"
