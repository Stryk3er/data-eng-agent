import { tool } from "@opencode-ai/plugin"
import { readFile } from "fs/promises"
import path from "path"

export default tool({
  description:
    "Gather raw evidence for a pipeline failure: the last dbt run_results.json (which " +
    "model/test failed and its message). Returns structured facts, not a stack trace dump -- " +
    "pair this with the diagnose-pipeline-failure skill to explain the mechanism, not just " +
    "repeat the error text back.",
  args: {},
  async execute(args, context) {
    const parts: string[] = []
    try {
      const runResultsPath = path.join(context.worktree, "dbt_project", "target", "run_results.json")
      const raw = await readFile(runResultsPath, "utf-8")
      const data = JSON.parse(raw)
      const failures = (data.results ?? []).filter(
        (r: any) => r.status === "fail" || r.status === "error"
      )
      parts.push(`dbt failures (${failures.length}):`)
      for (const f of failures) {
        parts.push(`- node: ${f.unique_id}\n  status: ${f.status}\n  message: ${f.message ?? "(none)"}`)
      }
      if (failures.length === 0) parts.push("(no dbt failures in the last recorded run)")
    } catch (e) {
      parts.push(
        `no run_results.json found under dbt_project/target -- dbt hasn't run yet in this ` +
          `working directory, or it ran somewhere else. Error: ${e}`
      )
    }
    return parts.join("\n")
  },
})
