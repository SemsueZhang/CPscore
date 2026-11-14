#!/usr/bin/env python3
"""Bundle the common format source into independently installable review skills."""

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("cp-statement-review", "cp-editorial-review")
FILES = {
    "format_lint.py": "scripts/format_lint.py",
    "format.md": "references/format.md",
}


def sync(root, check=False):
    """Return stale relative paths; check mode never changes any files."""
    sources = {name: (root / "shared/review-format" / name).read_bytes() for name in FILES}
    stale = []
    for skill in SKILLS:
        for name, relative in FILES.items():
            target = root / "skills" / skill / relative
            if target.is_file() and target.read_bytes() == sources[name]:
                continue
            stale.append(target.relative_to(root).as_posix())
            if not check:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(sources[name])
    return stale


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只检查随包文件是否与共用源一致")
    args = parser.parse_args(argv)
    try:
        stale = sync(ROOT, check=args.check)
    except OSError as error:
        parser.exit(2, "Cannot read or synchronize format bundles: {}\n".format(error))
    if args.check and stale:
        print("Stale format bundles; run python3 scripts/sync_review_format.py:")
        print("\n".join(stale))
        return 1
    print("Format bundles are synchronized." if not stale else "Updated:\n" + "\n".join(stale))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
