#!/usr/bin/env bash
# Quick AI cost dashboard — runs the canonical aggregation queries against
# the production ai_logs table over SSH + docker exec.
#
# Usage:
#   ./scripts/ai-cost.sh
#
# Requires:
#   - SSH access to the Hetzner host (key at ~/.ssh/hetzner_megabuy)
#   - DOMAIN env var or hardcoded HOST below
#
# Phase 0 stop-gap until an admin UI ships. See ADR-003 + RCA
# docs/rca/2026-06-04-ai-logs-empty.md for context.
set -euo pipefail

HOST="${HOST:-135.181.149.237}"
KEY="${KEY:-$HOME/.ssh/hetzner_megabuy}"
SQL=$(cat <<'EOSQL'
\echo === TOTAL ===
SELECT COUNT(*) AS calls, ROUND(SUM(cost_usd)::numeric, 4) AS total_usd
FROM ai_logs WHERE success=true;

\echo
\echo === Par provider/modele ===
SELECT provider, model, COUNT(*) AS calls,
       ROUND(SUM(cost_usd)::numeric, 4) AS total_usd,
       ROUND(AVG(cost_usd)::numeric, 6) AS avg_per_call
FROM ai_logs WHERE success=true GROUP BY 1,2 ORDER BY total_usd DESC;

\echo
\echo === 14 derniers jours ===
SELECT date_trunc('day', created_at)::date AS day,
       COUNT(*) AS calls,
       ROUND(SUM(cost_usd)::numeric, 4) AS daily_usd
FROM ai_logs WHERE success=true
  AND created_at > NOW() - INTERVAL '14 days'
GROUP BY day ORDER BY day DESC;

\echo
\echo === Top 10 articles les plus chers ===
SELECT raw_article_id, COUNT(*) AS calls,
       ROUND(SUM(cost_usd)::numeric, 4) AS article_usd
FROM ai_logs
WHERE raw_article_id IS NOT NULL AND success=true
GROUP BY raw_article_id ORDER BY article_usd DESC LIMIT 10;

\echo
\echo === Echecs ===
SELECT provider, model, COUNT(*) AS failures, MAX(created_at) AS last_failure
FROM ai_logs WHERE success=false
GROUP BY 1,2 ORDER BY failures DESC;
EOSQL
)
ssh -i "$KEY" -o StrictHostKeyChecking=no "root@$HOST" \
  "docker exec -i infra-postgres-1 psql -U darija -d darija_ai" <<< "$SQL"
