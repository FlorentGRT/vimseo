<!--
 Copyright 2021 IRT Saint Exupery, https://www.irt-saintexupery.com

 This work is licensed under the Creative Commons Attribution-ShareAlike 4.0
 International License. To view a copy of this license, visit
 http://creativecommons.org/licenses/by-sa/4.0/ or send a letter to Creative
 Commons, PO Box 1866, Mountain View, CA 94042, USA.
-->

# Information for maintainers

## Deploy the documentation

The documentation is published on GitHub Pages, from the `gh-pages` branch of
[vimseo/vimseo](https://github.com/vimseo/vimseo), and is versioned with
[mike](https://github.com/jimporter/mike):

- each release is published under its version, e.g.
  [`0.1.7`](https://vimseo.github.io/vimseo/0.1.7/);
- the last release is also published under the alias `latest`, to which
  [the root of the site](https://vimseo.github.io/vimseo/) redirects;
- the `main` branch is published under `develop`.

The version selector of the documentation lists the versions deployed in
`versions.json` at the root of `gh-pages`. The links from the README to the
documentation point to `latest`.

### Prerequisites

- The `doc` tox environment, created with `tox -e doc --notest`.
- A clean checkout of the revision to document, e.g. a git worktree: MkDocs publishes
  every file under `docs/`, including the untracked ones.
- A local `gh-pages` branch up to date with the remote one: `mike` commits on top of it.

### Deploy a version

From the root of the checkout of the revision to document (here the tag `0.1.8`,
created by `git worktree add --detach ../vimseo-doc 0.1.8`), with `upstream` the remote
of [vimseo/vimseo](https://github.com/vimseo/vimseo):

```bash
git fetch upstream gh-pages:gh-pages

# The settings and preparation steps of the doc tox environment.
export DOCSTRING_INHERITANCE_ENABLE=1 PLOTLY_RENDERER=sphinx_gallery MPLBACKEND=AGG
# mike runs mkdocs in a subprocess: the doc environment must be in the PATH
# (.tox/doc/bin on Linux).
export PATH="$PWD/.tox/doc/Scripts:$PATH"
rm -rf docs/generated site
python docs/modify_readme_image_url.py

# A release, which becomes the latest one:
mike deploy --push --remote upstream --update-aliases 0.1.8 latest
# The main branch:
mike deploy --push --remote upstream develop
```

`mike deploy` builds the documentation, commits it in the directory of the version on
`gh-pages` and pushes it. The build fails if one of the runnable examples fails.

The other useful commands:

- `mike list` lists the deployed versions;
- `mike delete --push --remote upstream <version>` deletes a version;
- `mike serve` serves `gh-pages` locally, with the version selector (`mkdocs serve`
  does not show it).

!!! note

    `mike` only writes the directories of the versions, `versions.json` and the
    `index.html` redirecting the root to `latest`. If the history of `gh-pages` was
    rewritten, it refuses to deploy until you pass `--ignore-remote-status`, and the
    push must be forced with `git push --force-with-lease upstream gh-pages`.
