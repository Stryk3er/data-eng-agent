---
name: diagnose-pipeline-failure
description: How to explain a pipeline failure -- mechanism first, not a stack trace repeat. Use whenever dbt build/test fails or extraction errors out.
license: MIT
compatibility: opencode
---

## What "good" looks like

Bad: "The test `assert_temp_max_gte_temp_min` failed with 1 row returned."
That's just repeating the tool output back.

Good: "cdmx has temp_max_c=5.0 and temp_min_c=25.0 for today -- those are
swapped. That's physically impossible, so this is either (a) a chaos
injection, or (b) an upstream API returning fields in the wrong order.
Given only one row is affected, this points to a single bad write, not a
systemic mapping bug in stg_open_meteo__daily (a mapping bug would affect
every row equally)."

## Steps

1. Call `diagnose_failure` to get the actual failing node(s) and message.
   Don't diagnose from memory of what you last touched.
2. **dbt test failure**: read the compiled SQL under
   `dbt_project/target/compiled/.../<test_name>.sql` to see exactly what
   condition triggered it, then use the `duckdb` MCP tool to query the
   offending rows directly.
3. **Contract violation**: the error names the column and the type
   mismatch. Check whether the upstream raw table's schema actually
   changed (schema drift) vs. a bad cast in staging.
4. **Extraction failure**: check whether it's one request failing
   (transient -- did the retry decorator exhaust its attempts?) vs. every
   request failing (credential/config issue, e.g. missing BANXICO_TOKEN).
5. State the mechanism in one sentence before proposing a fix. If you
   can't state it confidently, say so and show what you checked instead of
   papering over the uncertainty with a generic-sounding explanation.
