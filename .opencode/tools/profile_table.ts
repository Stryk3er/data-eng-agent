import { tool } from "@opencode-ai/plugin"

export default tool({
  description:
    "Profile a table in the DuckDB warehouse: row count, per-column null %, and min/max/distinct " +
    "for numeric or date columns. Use this before stating a number as fact, and before " +
    "diagnosing a failure.",
  args: {
    schema: tool.schema.string().describe("e.g. raw, staging, intermediate, marts"),
    table: tool.schema.string().describe("table or view name, without the schema prefix"),
  },
  async execute(args, context) {
    const result = await Bun.$`python -m extraction.profile --schema ${args.schema} --table ${args.table}`
      .cwd(context.worktree)
      .nothrow()
    return result.stdout.toString() + result.stderr.toString()
  },
})
