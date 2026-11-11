#!/bin/sh
# File and copy-operation checks only; no model calls or global changes.
set -eu
cd "$(dirname "$0")/.."
cpscore_source=$(pwd)
cpscore_temp=$(mktemp -d "${TMPDIR:-/tmp}/cpscore-check.XXXXXX")
trap 'rm -rf "$cpscore_temp"' EXIT HUP INT TERM
fail() { printf '%s\n' "$*" >&2; exit 1; }
cpscore_count=0
for cpscore_dir in skills/*/; do
  test -f "${cpscore_dir}SKILL.md" || continue
  cpscore_name=$(basename "$cpscore_dir")
  test "$(head -n 1 "${cpscore_dir}SKILL.md")" = '---' || fail "Missing frontmatter: $cpscore_name"
  awk -v name="$cpscore_name" '
    NR==1 {next}
    $0=="---" {closed=1; exit}
    /^name: / {valid_name=($0=="name: " name)}
    /^description: ./ {valid_description=1}
    END {exit !(closed && valid_name && valid_description)}
  ' "${cpscore_dir}SKILL.md" || fail "Invalid name/description: $cpscore_name"
  case "$cpscore_name" in *[!a-z0-9-]*|-*|*-|*--*) fail "Invalid directory name: $cpscore_name";; esac
  test "${#cpscore_name}" -le 64 || fail "Name too long: $cpscore_name"
  if grep -E '\.cpscore/|scripts/cpscore\.py|python3 -m cpscore|docs/(protocol|assessment|data)\.md' "${cpscore_dir}SKILL.md"; then
    fail "Removed dependency in $cpscore_name"
  fi
  cpscore_count=$((cpscore_count + 1))
done
test "$cpscore_count" -gt 0 || fail 'No skills discovered'

# Add an extra skill to verify that installation does not assume a fixed list.
mkdir -p "$cpscore_temp/source"
cp -R skills "$cpscore_temp/source/"
mkdir -p "$cpscore_temp/source/skills/cp-future-check"
printf '%s\n' '---' 'name: cp-future-check' 'description: Temporary acceptance fixture.' '---' 'Reply in chat.' > "$cpscore_temp/source/skills/cp-future-check/SKILL.md"
cd "$cpscore_temp/source"
for cpscore_harness in codex claude-code opencode; do
  case "$cpscore_harness" in
    codex) cpscore_global='.agents/skills'; cpscore_project='.agents/skills';;
    claude-code) cpscore_global='.claude/skills'; cpscore_project='.claude/skills';;
    opencode) cpscore_global='.config/opencode/skills'; cpscore_project='.opencode/skills';;
  esac
  for cpscore_scope in global project; do
    if test "$cpscore_scope" = global; then
      cpscore_dest="$cpscore_temp/user with spaces/$cpscore_global"
    else
      cpscore_dest="$cpscore_temp/project with spaces/$cpscore_project"
    fi
    mkdir -p "$cpscore_dest/unrelated-skill"
    printf '%s\n' 'User content' > "$cpscore_dest/unrelated-skill/keep.txt"
    for cpscore_skill_dir in skills/*/; do
      test -f "${cpscore_skill_dir}SKILL.md" || continue
      cpscore_skill=$(basename "$cpscore_skill_dir")
      # Same single-copy, update and uninstall operations documented for users.
      cp -R "skills/$cpscore_skill" "$cpscore_dest/"
      diff -qr "skills/$cpscore_skill" "$cpscore_dest/$cpscore_skill" >/dev/null
      mkdir -p "$cpscore_dest/$cpscore_skill/scripts"
      printf '%s\n' 'Obsolete file' > "$cpscore_dest/$cpscore_skill/scripts/old-tool"
      rm -r "$cpscore_dest/$cpscore_skill"
      cp -R "skills/$cpscore_skill" "$cpscore_dest/"
      diff -qr "skills/$cpscore_skill" "$cpscore_dest/$cpscore_skill" >/dev/null
      rm -r "$cpscore_dest/$cpscore_skill"
      test ! -e "$cpscore_dest/$cpscore_skill" || fail 'Uninstall failed'
    done
    for cpscore_skill_dir in skills/*/; do
      test -f "${cpscore_skill_dir}SKILL.md" || continue
      cp -R "${cpscore_skill_dir%/}" "$cpscore_dest/"
    done
    cpscore_installed=0
    for cpscore_skill_dir in skills/*/; do
      test -f "${cpscore_skill_dir}SKILL.md" || continue
      cpscore_skill=$(basename "$cpscore_skill_dir")
      diff -qr "${cpscore_skill_dir%/}" "$cpscore_dest/$cpscore_skill" >/dev/null
      cpscore_installed=$((cpscore_installed + 1))
    done
    test "$cpscore_installed" -eq "$((cpscore_count + 1))" || fail 'Incomplete all-skills copy'
    test -f "$cpscore_dest/unrelated-skill/keep.txt" || fail 'Unrelated skill changed'
    printf '%s\n' "PASS $cpscore_harness $cpscore_scope: single/all/update/uninstall ($cpscore_installed skills including future fixture)"
  done
done
cd "$cpscore_source"
printf '%s\n' "PASS $cpscore_count current skills: frontmatter and removed-dependency checks"
