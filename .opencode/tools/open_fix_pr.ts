import { tool } from "@opencode-ai/plugin"

export default tool({
  description:
    "Create a branch, commit the working tree's current changes, push, and open a pull " +
    "request against main describing the fix. Never merges -- a human reviews and merges. " +
    "Requires GITHUB_TOKEN (set automatically inside GitHub Actions).",
  args: {
    branch: tool.schema.string().describe("e.g. fix/fx-rate-bounds-2026-07-30"),
    title: tool.schema.string(),
    body: tool.schema.string().describe("Explain the mechanism of the bug and the fix, not just 'fixed it'"),
  },
  async execute(args, context) {
    await Bun.$`git checkout -b ${args.branch}`.cwd(context.worktree).nothrow()
    await Bun.$`git add -A`.cwd(context.worktree).nothrow()
    const commit = await Bun.$`git commit -m ${args.title}`.cwd(context.worktree).nothrow()
    if (commit.exitCode !== 0) {
      return `nothing to commit on ${args.branch} (working tree clean) -- no PR opened`
    }
    await Bun.$`git push -u origin ${args.branch}`.cwd(context.worktree).nothrow()
    const pr = await Bun.$`gh pr create --title ${args.title} --body ${args.body} --base main --head ${args.branch}`
      .cwd(context.worktree)
      .nothrow()
    return pr.stdout.toString() + pr.stderr.toString()
  },
})
