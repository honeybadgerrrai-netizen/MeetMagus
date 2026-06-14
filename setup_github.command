#!/bin/bash
# MeetMagus — One-time GitHub setup
# Double-click this file in Finder, or run: bash ~/Documents/Claude/Projects/MeetMagus/setup_github.command
#
# What this does:
#   1. Initializes a proper git repo in this folder
#   2. Renames the GitHub repo from 'dealflow' to 'MeetMagus'
#   3. Pushes all local code to GitHub main branch
#   4. Deletes this script (no longer needed after first run)
#
# Requires a GitHub Personal Access Token with "repo" scope:
#   1. Go to: https://github.com/settings/tokens/new
#   2. Check "repo" → Generate token → copy it
#   3. Run: export GITHUB_TOKEN="ghp_your_token_here"
#   4. Then double-click this file (or run the export + script in same terminal session)

set -e
cd "$(dirname "$0")"
FOLDER="$(pwd)"
OWNER="honeybadgerrrai-netizen"
OLD_REPO="dealflow"
NEW_REPO="MeetMagus"

echo ""
echo "============================================"
echo "  MeetMagus — GitHub Setup"
echo "============================================"
echo ""

# ── Auth check ────────────────────────────────────────────────────────────────
if [ -z "$GITHUB_TOKEN" ]; then
  echo "ERROR: GITHUB_TOKEN not set."
  echo ""
  echo "Run this in Terminal first, then re-run this script:"
  echo ""
  echo '  export GITHUB_TOKEN="ghp_your_token_here"'
  echo '  bash ~/Documents/Claude/Projects/MeetMagus/setup_github.command'
  echo ""
  exit 1
fi

# ── Clean up any broken .git from previous attempt ───────────────────────────
if [ -d ".git" ]; then
  echo "→ Removing existing .git directory..."
  rm -rf .git
fi

# ── Initialize git ────────────────────────────────────────────────────────────
echo "→ Initializing git repo..."
git init -b main
git config user.email "honeybadgerrrai@gmail.com"
git config user.name "Anand"

echo "→ Staging files..."
git add -A

echo "→ Files to be committed:"
git status --short

echo ""
echo "→ Creating initial commit..."
git commit -m "feat: initial MeetMagus commit — EDGAR + news pipeline, 13D trigger agent

Renamed from dealflow. Includes:
- app/fetchers/      EDGAR 13D/8-K/Form4 + Google News RSS fetchers
- app/workers/       extraction, embedding, prompts for edgar + news
- app/agents/        13D trigger agent (the defining use case)
- app/notifications/ SendGrid email alerts
- scripts/           schema creation, seed data, pipeline runners
- config/models.yaml LLM provider + model routing (Qwen3 via DeepInfra)
- tests/             EDGAR, extractor, embedder, 13D trigger coverage"

# ── Rename GitHub repo ────────────────────────────────────────────────────────
echo ""
echo "→ Renaming GitHub repo '$OLD_REPO' → '$NEW_REPO'..."
HTTP_STATUS=$(curl -s -o /tmp/gh_rename_response.json -w "%{http_code}" \
  -X PATCH \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/repos/$OWNER/$OLD_REPO" \
  -d "{\"name\":\"$NEW_REPO\",\"default_branch\":\"main\"}")

if [ "$HTTP_STATUS" = "200" ]; then
  echo "   ✓ Repo renamed to $NEW_REPO"
elif [ "$HTTP_STATUS" = "422" ]; then
  echo "   ℹ Repo may already be named '$NEW_REPO' — continuing..."
else
  echo "   ⚠ Rename returned HTTP $HTTP_STATUS:"
  cat /tmp/gh_rename_response.json
  echo ""
  echo "   You may need to rename the repo manually at:"
  echo "   https://github.com/$OWNER/$OLD_REPO/settings"
  echo "   Then re-run this script."
fi

# ── Set remote and push ───────────────────────────────────────────────────────
echo ""
echo "→ Setting remote origin..."
git remote add origin "https://${GITHUB_TOKEN}@github.com/${OWNER}/${NEW_REPO}.git"

echo "→ Pushing to GitHub (main)..."
git push -u origin main --force

echo ""
echo "============================================"
echo "  Done!"
echo "  Repo: https://github.com/$OWNER/$NEW_REPO"
echo "============================================"
echo ""

# Self-delete — this script is a one-time setup tool
echo "→ Removing this setup script (no longer needed)..."
rm -- "$0"
