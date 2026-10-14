---
name: pr-review
description: Assess whether the current Git branch is ready to open or update a pull request in any repository. Review the proposed branch diff, run relevant checks, and report blockers and verification gaps without changing the PR or files.
---

# PR Readiness

Evaluate the *proposed PR*, not just the staged diff. This is a read-only preflight: do not edit files, stage, commit, push, fetch, create/update a PR, or install dependencies without a separate request or required authorization. Do not apply repository-specific rules from another skill unless they are applicable and available in the current repository.

## Establish the scope

1. Check `git status --short --branch`, `git branch --show-current`, and available remote/PR metadata. Prefer a base branch named by the user, then the base of an existing PR (if accessible). The repository's default branch is only a *provisional* base when the actual PR target is unknown; state that assumption. Do not mistake a feature branch's upstream tracking branch for the PR base. If no credible base can be identified, ask for it rather than declaring the PR ready. Do not fetch just to guess the base; disclose when local refs may be stale.
2. Use `git merge-base <base> HEAD`, `git diff --name-status -M <base>...HEAD`, `git diff --stat <base>...HEAD`, `git diff --check <base>...HEAD`, and the full diff to inspect the branch's proposed changes. Check for an empty diff, unexpected commits, merges/reverts, added/deleted/renamed files, binary assets, submodules, and generated files. Confirm the comparison is based on the intended target, especially if histories have diverged.
3. Inspect `git diff --cached` and `git diff` separately to disclose staged/unstaged changes, plus relevant untracked files. They are not in the current PR until committed. Never claim a HEAD-based test covers these changes. For file context, inspect the committed version (`git show HEAD:path`) rather than an independently modified worktree file; for a pre-commit check explicitly requested by the user, identify that as a separate scope.

## Check feasibility

Select checks based on changed files and repository conventions; do not assume a language or framework.

- **Behavior:** Trace changed behavior through callers, public APIs, error paths, data migrations, configuration, and backward compatibility. Check that deletions/renames do not leave broken references or omit required files.
- **Delivery:** Check manifests, lockfiles, imports, assets, generated artifacts, deployment/build configuration, CI definitions, and any project-specific contribution or PR rules. Check tests and documentation when behavior or interfaces changed.
- **Evidence:** Run `git diff --check` for the proposed diff; identify the repository's relevant tests, lint, type checks, and build, then run focused checks and broader checks when risk warrants it. Prefer an isolated snapshot of committed `HEAD` for checks when the worktree differs from `HEAD`; `git archive HEAD` can make such a snapshot but omits submodules and other untracked/ignored inputs, so adapt to the project's build requirements. Avoid overwriting existing build products. Distinguish pre-existing failures, missing tools/dependencies, network restrictions, and checks not run from new failures; do not present an untested branch as passing.
- **Integration:** If PR/CI status is available through authorized, read-only tooling, inspect required checks and merge conflicts. Local checks alone do not establish remote CI success, approval, permissions, or mergeability. Do not trigger pipelines or mutate remote state as part of the review.

For every suspected issue, establish whether the branch introduced it and cite the changed file/line and supporting evidence. Search affected callers and similar cases when the change has a shared contract. Avoid unrelated pre-existing defects and speculative findings.

## Report

Lead with confirmed findings ordered by severity, including `path:line`, consequence, evidence, and a concrete fix. Then give a single verdict: **ready to submit** (no known blockers and material checks passed), **needs changes** (confirmed blocker), or **undetermined** (base, required checks, or essential evidence missing). State the base/head scope, checks actually run and their results, and any uncommitted changes or remote checks excluded from the verdict. A clean local review is not a guarantee that a PR will be accepted or merged; if no issues were found, say so explicitly and name important gaps.
