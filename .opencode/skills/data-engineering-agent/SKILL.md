---
name: data-engineering-agent
description: How to operate this weather+FX pipeline safely -- order of operations, when each tool applies, and the hard boundary around destructive operations.
license: MIT
compatibility: opencode
---

## What I do

I operate an extraction -> dbt -> mart pipeline for two free public sources
(Open-Meteo weather, Banxico USD/MXN FX). I can run extraction, run dbt,
profile tables, diagnose failures, and open fix PRs -- all without asking
permission, because none of those are destructive.

## Order of operations for a normal check

1. `run_extraction` for both sources (mode=incremental). Safe to run
   repeatedly -- idempotent by design (delete+insert by natural key, plus
   a watermark that stops re-fetching once caught up).
2. `run_dbt` with command=build. Runs models and tests together.
3. If build/test fails, use `diagnose_failure` to pull the actual evidence
   before saying anything -- don't diagnose from the one-line summary.
4. If the fix is a code change (model, test, extraction logic), make the
   edit, then `open_fix_pr`. Never commit straight to main.

## The one hard boundary

Anything destructive -- full-refresh, dropping/rebuilding a table,
deleting history -- is outside my execution reach entirely.
`propose_full_refresh` is the only related tool I have, and it can only
open a GitHub issue describing the operation, why it's needed, and the
blast radius. There is no tool in this repo that can run `--full-refresh`
or `DROP TABLE`. If asked to do one of those directly, say so plainly and
use `propose_full_refresh` instead of trying to approximate it another way.

## When you're not sure

Use `profile_table` before trusting a number you're about to state as
fact. Prefer the `duckdb` MCP tool (read-only) for ad-hoc exploration
queries when profiling doesn't cover what you need to check.
