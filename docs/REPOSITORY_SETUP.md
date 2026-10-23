# Repository and Cursor Origin setup

GitHub is the canonical community source and download host:
https://github.com/sloppamadewithlove/my-career-training.
Cursor Origin is a mirror of GitHub, separate from the Git remote named `origin`.

Before creation, verify `gh api user --jq .login` returns the intended owner and
inspect any existing repository. Do not overwrite an unrelated repository.
From this project's checkout after its initial commit:

```sh
gh repo create sloppamadewithlove/my-career-training --public --source . --remote origin --push
origin auth status
origin repo create-mirrored sloppamadewithlove/my-career-training
```

Record the **returned** clone URL; do not construct one as evidence of creation.
Keep GitHub as `origin`; add the returned Origin remote as `cursor`:

```sh
git remote add cursor RETURNED_CLONE_URL
origin repo view sloppamadewithlove/my-career-training --json org,name,defaultBranch
git ls-remote cursor HEAD
```

If creation succeeded previously, inspect and reuse it; do not create duplicates.
Origin requires an eligible Cursor account, GitHub admin access and the Cursor
GitHub app's access to this repo. If the app only permits selected repositories,
add the new repo through the user's existing GitHub app installation. Missing
access is an explicit setup blocker, not a successful mirror. GitHub remains
usable independently. Never include credentials or session data in the repo.

Actual repository/mirror verification and release URLs belong in the release
report; this document contains reproducible setup instructions, not proof that
any remote was created.

Official references:
- https://cursor.com/docs/origin/mirror-github
- https://cursor.com/docs/origin/cli/reference/commands
- https://cursor.com/docs/origin/create-repository
