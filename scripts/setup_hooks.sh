#!/usr/bin/env bash
# Configure git to use version-controlled .githooks directory
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
git config core.hooksPath "$REPO_ROOT/.githooks"
chmod +x "$REPO_ROOT/.githooks/"*
echo "✅ Git hooks configured to use $REPO_ROOT/.githooks"
