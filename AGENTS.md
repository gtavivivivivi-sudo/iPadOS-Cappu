# Rules for agents working on iPadOS-Cappu

1. Read `criticalKeepAnythingNotNeededOutOfHere/docs.md` first. It is the ONLY documentation file besides `README.md`. Reply to the user in Russian, short, no filler, call him "Бро".
2. Do NOT create new documentation files (no new `.md`, `.txt`, notes, handoffs, plans, logs, `UPDATE-*.txt`) anywhere in the repo. Put every doc update into the right section of `criticalKeepAnythingNotNeededOutOfHere/docs.md`. Keep it updated after each step; mark facts V (verified) or U (guess).
3. Do NOT add files to the repo root. New code goes where it belongs: `patches/` (numbered XNU patches), `shim/`, `tools/`. No scratch, test or backup files, no copies of old versions, no dumps, no Apple artifacts, no zips, no serial numbers.
4. Do NOT touch `README.md`, `LICENSE`, `trashbin/` (user's old upstream files) or the user's code unless asked.
5. Do NOT rewrite git history or force-push unless the user asks. Commit small, with a clear message, author `ClaudeAgent1` / `RandomFakeEmail@a.b.c`.
6. Do NOT run, restore or rewrite `tools/validate-repo.py`. Do NOT build the LSE emulator (decided: not needed).
7. Never claim something works without running it. Nothing destructive on the tablet without the user's confirmation; never write preloader/lk/boot/recovery; backups first (see section 6 of `docs.md`).
