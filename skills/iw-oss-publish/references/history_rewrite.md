# History Rewrite Decision Tree

Used by `publish` mode when the skill asks the user to pick a history strategy. Each branch links to the exact commands the skill will emit.

---

## Decision Tree

```
Q1. Does this repo's git history have external consumer value?
    (i.e., do any current or future OSS users need to see the evolution of the code?)
    │
    ├── NO  → recommend NUKE (simplest; zero history risk)
    │
    └── YES → Q2

Q2. Did OSS-SEC-02 find secrets in history?
    │
    ├── YES → Q3
    │
    └── NO  → Q4

Q3. Can the secret leaks be surgically removed by specific file paths
    or string replacements without losing significant history?
    │
    ├── YES → recommend FILTER-REPO (surgical rewrite, preserves shape)
    │
    └── NO (widespread contamination) → recommend NUKE

Q4. Are there non-secret reasons to rewrite history?
    Examples: non-noreply contributor emails (OSS-HIST-03 SHOULD),
              large binaries (OSS-HYG-04), internal URLs in commit messages
    │
    ├── YES → recommend FILTER-REPO
    │
    └── NO  → recommend PRESERVE (publish as-is)
```

The skill runs the questions interactively in `publish` mode and recommends a strategy. The user is free to override the recommendation.

---

## Strategy A — NUKE-AND-REINIT

Fresh squashed init commit. Zero prior history. Simplest and safest when history has no consumer value.

### When to choose

- Personal projects, early-stage tooling, or internal-born repos where prior commits have no archeological value.
- OSS-SEC-02 found widespread secret contamination across history.
- Contributor identity concerns (many non-noreply emails you'd rather not expose).

### Commands emitted (user runs manually)

```bash
# 1. Ensure working tree is clean
cd {target}
git status

# 2. Capture current state for a retroactive private archive (optional but recommended)
git bundle create ~/private-archive/{repo-name}-pre-public.bundle --all

# 3. Nuke history by checking out an orphan branch with the current tree
git checkout --orphan iw-public-root

# 4. Add everything, commit, rename branch
git add -A
git commit -m "Initial public release" -s
git branch -M main

# 5. Force-push to replace remote history
git push --force origin main

# 6. Delete all other branches on the remote (publish-playbook step)
# (emitted separately; only executed by user explicit approval)

# 7. Delete all tags both locally and remotely (if any)
git tag -l | xargs -I {} git push --delete origin {}
git tag -l | xargs git tag -d

# 8. Open GitHub Support ticket for SHA cache purge (playbook reminder)
```

### Pitfalls / side effects

- **All collaborators must re-clone.** Existing clones become divergent permanently.
- **All PRs are invalidated.** They were targeting now-unreachable SHAs.
- **Existing forks are detached.** GitHub will not update them.
- **Release-page history is gone.** If prior releases existed, they detach from their commits.
- **GitHub SHA cache** may still serve old commits by direct URL for up to 90 days unless you open a Support ticket.

### Verification after rewrite

```bash
# Should show exactly one commit
git log --oneline | wc -l
# Re-run skill to verify no secret traces remain in the new history
iw-oss-publish scan
```

---

## Strategy B — FILTER-REPO

Surgical rewrite: remove specific files, specific byte patterns, or specific author identities across history while preserving overall commit graph.

### When to choose

- OSS-SEC-02 found localized secrets in a handful of files.
- OSS-HIST-03 flagged contributor emails to pseudonymize.
- OSS-HYG-04 flagged large binaries to strip.
- History shape has consumer value (e.g., a meaningful feature evolution).

### Pre-work (critical)

`git-filter-repo` refuses to operate on a non-fresh clone by design. Run it against a **fresh** clone:

```bash
cd ~/tmp
git clone --no-local {path_or_url} {repo-name}-rewrite
cd {repo-name}-rewrite
```

### Commands — removing a file from history

```bash
# Remove a specific path from all history (commit graph preserved)
git filter-repo --path secrets.env --invert-paths --force

# Remove multiple paths
git filter-repo \
  --path secrets.env \
  --path .env.production \
  --path tools/internal/ \
  --invert-paths --force
```

### Commands — replacing strings in content

Create a replacements file:

```
# replacements.txt
AKIAIOSFODNN7EXAMPLE==>REDACTED
ghp_*==>REDACTED
https://internal.wiki/==>https://example.com/docs/
```

Then:

```bash
git filter-repo --replace-text replacements.txt --force
```

### Commands — rewriting contributor emails to noreply

```bash
# Create mailmap-style file: mailmap.txt
# old-email@personal.com => ID+username@users.noreply.github.com

git filter-repo --mailmap mailmap.txt --force
```

### Push

```bash
# Add original remote back (filter-repo strips it for safety)
git remote add origin {original-remote-url}

# Force-push rewritten history
git push --force origin main
git push --force --tags origin
```

### Pitfalls / side effects

- **Signed commits lose their signatures.** Every rewritten commit has a new SHA; GPG/SSH signatures bound to old SHAs become invalid. Re-signing requires `git rebase --exec 'git commit --amend --no-edit --gpg-sign'` per commit — impractical for large histories.
- **Submodules are not rewritten.** Submodules pointing to internal URLs must be removed or redirected **before** running filter-repo; `OSS-HIST-04` is a MUST-level pre-check.
- **LFS objects are not automatically purged.** If LFS contained secrets, run `git lfs prune` and delete objects from LFS storage explicitly.
- **Annotated tags preserved; lightweight tags re-created.** If a tag's signature mattered, re-sign after rewrite.
- **`refs/original/` leftovers**: filter-repo does NOT leave these (unlike legacy `filter-branch`), but `git for-each-ref refs/original/` is a belt-and-braces check.
- **Collaborators must re-clone.** Same as NUKE strategy.
- **GitHub SHA cache** persists until Support ticket is opened.

### Verification after rewrite

```bash
# Re-run secrets scan on rewritten history
gitleaks detect --log-opts='--all'

# Re-run the full skill scan
iw-oss-publish scan

# Confirm no ref/original leftovers
git for-each-ref refs/original/   # should be empty
```

---

## Strategy C — PRESERVE

Publish history exactly as-is. The default when the repo is clean enough and the history has consumer value.

### When to choose

- OSS-SEC-02 passed clean.
- OSS-HIST-03 non-noreply emails were accepted (contributors agreed, or have been contacted).
- No large-binary blobs in history.
- Commit messages contain no internal references.

### Commands emitted

None — `publish` mode proceeds directly to the post-publish playbook.

### Follow-up

- Configure `git config user.email {id}+{username}@users.noreply.github.com` in the repo's `.git/config` for all future contributors to avoid adding new personal emails going forward.

---

## GitHub Support Cache Purge (shared by A and B)

Any history rewrite requires opening a GitHub Support ticket to purge cached commit views. The skill emits this reminder in the post-publish playbook:

1. Visit https://support.github.com/contact
2. Category: "Sensitive data in a repository"
3. Provide:
   - Repository full name: `{org}/{repo}`
   - Reason: "Force-pushed history rewrite to remove secrets/PII; cached commit SHAs should be purged."
   - List of affected SHAs (if known)
4. Support will confirm when the purge is complete (typically within 1-3 business days).

GitHub Support will only perform the purge when sensitive data is genuinely at risk. For "hygiene-only" rewrites (large-binary removal, email pseudonymization without secrets), the purge is best-effort and the ticket may be declined.

---

## Decision Recorder

The chosen strategy is written to `.iw/oss-publish.toml`:

```toml
[history]
strategy = "nuke"  # or "filter-repo" or "preserve"
decided_at = "2026-04-21T14:32:00Z"
decided_by = "{git config user.name}"
rationale = "Personal project; no external consumer value"
```

Future `scan` runs read this field and downgrade OSS-HIST-01 from MUST to INFO since the decision is recorded.
