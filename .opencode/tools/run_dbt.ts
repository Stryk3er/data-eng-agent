import { tool } from "@opencode-ai/plugin"

export default tool({
  description:
    "Run dbt (build, run, or test) against the DuckDB warehouse. This tool never performs a " +
    "full-refresh -- there is no full_refresh argument, and no code path here that adds one. " +
    "A full-refresh is a destructive operation and must go through propose_full_refresh plus " +
    "human approval on the destructive-ops GitHub environment instead.",
  args: {
    command: tool.schema.enum(["build", "run", "test"]).default("build"),
    select: tool.schema.string().optional().describe("dbt --select expression, e.g. 'marts.*'"),
  },
  async execute(args, context) {
    const extra: string[] = []
    if (args.select) extra.push("--select", args.select)
    const result =
      await Bun.$`dbt ${args.command} --project-dir dbt_project --profiles-dir dbt_project ${extra}`
        .cwd(context.worktree)
        .nothrow()
    return [`exit_code=${result.exitCode}`, result.stdout.toString(), result.stderr.toString()].join("\n")
  },
})
