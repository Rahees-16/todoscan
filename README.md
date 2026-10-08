# todoscan

Scan a directory tree for `TODO`, `FIXME`, `HACK` and `XXX` comments. Python 3 standard library only, no dependencies.

## Install

    git clone https://github.com/Rahees-16/todoscan.git
    cd todoscan
    python3 todoscan.py --help

## Usage

    python3 todoscan.py [path] [--tag TAG ...] [--json] [--summary] [--blame] [--exclude NAME ...]

    python3 todoscan.py ~/projects/myapp
    python3 todoscan.py . --tag FIXME --tag HACK
    python3 todoscan.py . --summary
    python3 todoscan.py . --json --summary
    python3 todoscan.py . --blame
    python3 todoscan.py . --exclude vendor --exclude private-repo

Sample output:

    src/app.py
      src/app.py:12: TODO handle empty input
      src/app.py:40: FIXME retry on timeout
    web/main.js
      web/main.js:7: HACK work around layout bug

- `--tag TAG` limit to a tag (repeatable)
- `--json` JSON output (with `--summary`, includes counts)
- `--summary` counts per tag and per file
- `--blame` add the author of each line via `git blame` (off by default; needs a git repo)
- `--exclude NAME` directory name to never enter (repeatable)

## Exclusions

Always skipped: `node_modules`, `build`, `.git`, `.gradle`, virtualenvs, other common cache/build dirs, and binary files.

To skip more directories by name, use `--exclude NAME` or list them in `~/.config/devtools/exclude`, one directory name per line (`#` starts a comment; a missing file means no extra exclusions):

    # ~/.config/devtools/exclude
    private-repo
    vendor

Set `DEVTOOLS_EXCLUDE_FILE` to use a different config path. Excluded directories are never entered or read.

## Safety

todoscan is read-only: it never modifies files. `--blame` only runs read-only `git blame`.

## Tests

    python3 -m unittest -v

## License

MIT, see [LICENSE](LICENSE).
