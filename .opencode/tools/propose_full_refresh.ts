import { tool } from "@opencode-ai/plugin"

export default tool({
  description:
    "Propose a destructive operation (full-refresh, table drop/rebuild) by opening a GitHub " +
    "issue explaining WHAT would run, WHY it's needed, and the blast radius (tables affected, " +
    "row counts, estimated downtime). This tool has no execution path -- it can only write " +
    "the proposal, never run the command. A human reads it and manually triggers the " +
    "'full-refresh' GitHub Actions workflow, which is gated behind a required-reviewer " +
    "approval on the destructive-ops environment. The agent cannot bypass that gate; the " +
    "capability to run the destructive command simply does not exist in this tool's code.",
  args: {
    operation: tool.schema.string().describe("e.g. 'dbt build --full-refresh --select marts.fct_daily_conditions'"),
    reason: tool.schema.string(),
    blast_radius: tool.schema.string().describe("Tables/rows affected, estimated downtime"),
  },
  async execute(args, context) {
    const title = `[approval-needed] ${args.operation}`
    const body = [
      `**Proposed operation:** \`${args.operation}\``,
      ``,
      `**Why:** ${args.reason}`,
      ``,
      `**Blast radius:** ${args.blast_radius}`,
      ``,
      `**To approve:** run the "full-refresh" workflow from the Actions tab (workflow_dispatch), `,
      `with confirm=yes and operation="${args.operation}". It will pause for review on the `,
      `destructive-ops environment before anything executes.`,
      ``,
      `_Opened automatically by the data-engineer agent. It has no tool that can run this itself._`,
    ].join("\n")
    const result = await Bun.$`gh issue create --title ${title} --body ${body} --label needs-approval`
      .cwd(context.worktree)
      .nothrow()
    return result.stdout.toString() + result.stderr.toString()
  },
})
