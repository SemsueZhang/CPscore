"""CPScore's standard-library test suite."""

import json

from cpscore.harness import HARNESSES, LEGACY_SKILLS, MANIFEST, SKILLS, V2_SKILLS, V3_SKILLS


def downgrade_installation(project, version):
    """Build an older manifest fixture by removing assets added after its version."""
    keep = {1: LEGACY_SKILLS, 2: V2_SKILLS, 3: V3_SKILLS}[version]
    removed = set(SKILLS) - set(keep)
    additions = {
        2: (".cpscore/novelty.md", ".cpscore/runtime/cpscore/novelty_evidence.py", ".cpscore/runtime/cpscore/novelty_search.py"),
        3: (".cpscore/data.md", ".cpscore/runtime/cpscore/data.py"),
        4: (".cpscore/assessment.md", ".cpscore/runtime/cpscore/assessment.py"),
    }
    shared = {name for introduced, names in additions.items() if introduced > version for name in names}
    path = project / MANIFEST
    manifest = json.loads(path.read_text())
    for relative in list(manifest["files"]):
        if relative in shared or any(f"/{skill}/" in relative for skill in removed):
            (project / relative).unlink()
            del manifest["files"][relative]
    for harness in manifest["harnesses"]:
        for skill in removed:
            directory = project / HARNESSES[harness]["directory"] / skill
            (directory / "scripts").rmdir()
            directory.rmdir()
    manifest["format"] = version
    path.write_text(json.dumps(manifest))
