import { tool } from "@opencode-ai/plugin"

export default tool({
  description:
    "Run the incremental (or backfill) extraction for one source (open_meteo|banxico). " +
    "Safe to call anytime: writes are idempotent upserts keyed by natural key, so re-running " +
    "the same window never duplicates rows, and the incremental watermark skips windows " +
    "that were already extracted.",
  args: {
    source: tool.schema.enum(["open_meteo", "banxico"]).describe("Which source to extract"),
    mode: tool.schema.enum(["incremental", "backfill"]).default("incremental"),
    start: tool.schema.string().optional().describe("YYYY-MM-DD, required when mode=backfill"),
    end: tool.schema.string().optional().describe("YYYY-MM-DD, defaults to the source's freshness lag"),
  },
  async execute(args, context) {
    const extra: string[] = []
    if (args.start) extra.push("--start", args.start)
    if (args.end) extra.push("--end", args.end)
    const result = await Bun.$`python -m extraction.extract --source ${args.source} --mode ${args.mode} ${extra}`
      .cwd(context.worktree)
      .nothrow()
    return [`exit_code=${result.exitCode}`, result.stdout.toString(), result.stderr.toString()].join("\n")
  },
})
