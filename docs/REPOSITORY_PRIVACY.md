# Public repository privacy

Commit source, synthetic tests, build recipes, public dependency attributions and
sanitized validation summaries. Never commit or upload:

- API keys, tokens, environment files, passwords, cookies or sign-in state;
- personal saves, recordings, full game logs, crash dumps or raw agent logs;
- personal home paths, platform account IDs or private email addresses;
- installed Rocket League packages, extracted movies or decrypted game assets.

Keep local diagnosis in a private, ignored `work/` or build directory. Public
reports use relative source paths, observations, versions, hashes and test
results. Raw game logs can contain account IDs and authentication details even
when the relevant crash line looks harmless.

Review `git diff --cached` and the exact release file list before publication.
Review compiled metadata too. The BakkesMod SDK normally embeds the builder's
absolute source path; this plugin supplies a repository-relative metadata name.
Ignore rules help prevent accidents; they cannot guarantee no secret is ever
committed. Preserve upstream license attribution and official public project
URLs. Example account IDs and paths must be clearly synthetic.

Do not rewrite public history automatically. If an actual credential is found,
avoid copying its value into reports and arrange revocation before deciding how
to remove it from published history.
