#!/usr/bin/env bash
# Automation for voluntary reports, run by the GitHub Actions workflows in .github/workflows/.
#   voluntary_pr.sh sync ISSUE        Open/update the pull request that applies one issue's report.
#   voluntary_pr.sh post-merge PR     Record a merged report on its issue, then refresh other report PRs.
# Requires: gh (authenticated with GH_TOKEN), git, python3, and GITHUB_REPOSITORY.
# Issue text is untrusted: it is only ever read from files and parsed by scripts/add_report.py,
# which accepts allow-listed values only. It is never evaluated by the shell.
set -euo pipefail

REPORT_LABEL="voluntary-report"
COUNTED_LABEL="counted"
BRANCH_PREFIX="voluntary-report/issue-"
MARKER="accepted-report:"
BOT_LOGIN="github-actions[bot]"
CSV="data/cohorts.csv"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

require_number() {
  [[ "$1" =~ ^[0-9]+$ ]] || { echo "Not a number: $1" >&2; exit 1; }
}

escape() {
  python3 -c 'import html, sys; print(html.escape(sys.stdin.read()[:1000]))'
}

comment() {
  local issue="$1" file="$2"
  gh issue comment "$issue" --repo "$GITHUB_REPOSITORY" --body-file "$file" >/dev/null
}

open_pr_for() {
  gh pr list --repo "$GITHUB_REPOSITORY" --head "$1" --state open --json number --jq '.[0].number // empty'
}

close_pr() {
  local branch="$1" reason="$2" pr
  pr="$(open_pr_for "$branch")"
  if [[ -n "$pr" ]]; then
    gh pr close "$pr" --repo "$GITHUB_REPOSITORY" --delete-branch --comment "$reason" >/dev/null
  fi
}

ensure_labels() {
  gh label create "$REPORT_LABEL" --repo "$GITHUB_REPOSITORY" --color C5B783 \
    --description "Voluntary serving-status report" >/dev/null 2>&1 || true
  gh label create "$COUNTED_LABEL" --repo "$GITHUB_REPOSITORY" --color 00205B \
    --description "Voluntary report included in the published aggregates" >/dev/null 2>&1 || true
}

# Latest accepted row recorded by this automation on the issue (ignores comments by anyone else).
previous_accepted() {
  gh api --paginate "repos/$GITHUB_REPOSITORY/issues/$1/comments" \
    --jq ".[] | select(.user.login == \"$BOT_LOGIN\") | .body" \
    | sed -n "s/^<!-- $MARKER \(.*\) -->\$/\1/p" | tail -n 1
}

configure_git() {
  git config user.name "github-actions[bot]"
  git config user.email "41898729+github-actions[bot]@users.noreply.github.com"
}

sync() {
  local issue="$1"
  require_number "$issue"
  local branch="$BRANCH_PREFIX$issue"
  gh issue view "$issue" --repo "$GITHUB_REPOSITORY" --json number,state,body,labels,author > "$WORK/issue.json"
  python3 - "$WORK" "$REPORT_LABEL" <<'PY'
import json, pathlib, sys
work, label = pathlib.Path(sys.argv[1]), sys.argv[2]
issue = json.loads((work / "issue.json").read_text())
(work / "body.md").write_text(issue["body"] or "", encoding="utf-8")
(work / "author").write_text(issue["author"]["login"])
(work / "state").write_text(issue["state"])
(work / "is_bot").write_text(str(bool(issue["author"].get("is_bot"))))
(work / "labelled").write_text(str(any(l["name"] == label for l in issue["labels"])))
PY
  if [[ "$(cat "$WORK/labelled")" != "True" || "$(cat "$WORK/is_bot")" == "True" ]]; then
    echo "Issue #$issue is not a voluntary report; skipping."
    return 0
  fi
  local author previous
  author="$(cat "$WORK/author")"
  previous="$(previous_accepted "$issue")"
  if [[ "$(cat "$WORK/state")" == "CLOSED" && -z "$previous" ]]; then
    echo "Issue #$issue was closed without being counted; skipping."
    close_pr "$branch" "Issue #$issue was closed without being counted."
    return 0
  fi

  local others
  others="$(gh issue list --repo "$GITHUB_REPOSITORY" --author "$author" --label "$COUNTED_LABEL" \
    --state all --json number --jq "[.[] | select(.number != $issue) | \"#\(.number)\"] | join(\", \")")"
  if [[ -n "$others" ]]; then
    printf '%s\n' "Thanks! This account already has a counted report ($others). To change your answers, please edit that issue instead; this issue will not be counted separately." > "$WORK/comment.md"
    comment "$issue" "$WORK/comment.md"
    close_pr "$branch" "Duplicate of an existing counted report ($others)."
    return 0
  fi

  ensure_labels
  git fetch --quiet origin main
  git checkout --quiet --force -B "$branch" FETCH_HEAD
  local args=("$WORK/body.md" --json-out "$WORK/row.json" --as-of "$(date -u +%F)")
  [[ -n "$previous" ]] && args+=(--previous-json "$previous")
  if ! python3 scripts/add_report.py "${args[@]}" > "$WORK/result.txt" 2>&1; then
    {
      echo "This report could not be added automatically. Please edit the issue to fix it; it will be re-checked after each edit."
      echo
      echo "<pre>$(escape < "$WORK/result.txt")</pre>"
      [[ -n "$previous" ]] && echo && echo "Your previously counted answers remain in the published aggregates."
    } > "$WORK/comment.md"
    comment "$issue" "$WORK/comment.md"
    close_pr "$branch" "The linked report is no longer valid; see #$issue."
    git checkout --quiet --detach FETCH_HEAD
    return 0
  fi
  if git diff --quiet -- "$CSV"; then
    echo "Issue #$issue matches its counted report; nothing to change."
    close_pr "$branch" "No change: #$issue matches the report already counted."
    git checkout --quiet --detach FETCH_HEAD
    return 0
  fi

  python3 scripts/build_data.py
  python3 -m unittest discover -s tests
  configure_git
  git add "$CSV" data/index.json data/[0-9]*.json
  local action="Add"
  [[ -n "$previous" ]] && action="Update"
  git commit --quiet -m "$action voluntary report aggregate from #$issue"
  git push --quiet --force origin "$branch"

  local row
  row="$(tr -d '\n' < "$WORK/row.json")"
  python3 - "$WORK" "$issue" "$action" "$MARKER" "$previous" <<'PY'
import json, pathlib, sys
work, issue, action, marker, previous = pathlib.Path(sys.argv[1]), *sys.argv[2:]
row = json.loads((work / "row.json").read_text())
names = {"year": "Class", "service": "Service", "status": "Status", "rank": "Rank",
         "community": "Community", "industry": "Industry"}
lines = [
    f"{action}s the voluntary report from #{issue} to the aggregate counts in `data/cohorts.csv` "
    "and the derived JSON. Generated automatically from the issue form; no usernames or issue numbers are written to the data.",
    "",
    "| Field | Value |", "| --- | --- |",
    *[f"| {label} | {row[key] or '—'} |" for key, label in names.items()],
    "",
]
if previous:
    lines += ["This replaces the answers previously counted for that issue (one respondent is subtracted from the old aggregate row).", ""]
lines += [
    "**Before approving:** check the issue for consent, plausibility, and duplicate accounts. "
    "Approving this PR (as a maintainer) merges it automatically and redeploys the site. "
    "Close it to reject the report.",
    "",
    f"<!-- {marker} {json.dumps(row, sort_keys=True)} -->",
]
(work / "pr.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
  local pr title
  title="$action voluntary report from #$issue"
  pr="$(open_pr_for "$branch")"
  if [[ -n "$pr" ]]; then
    gh pr edit "$pr" --repo "$GITHUB_REPOSITORY" --title "$title" --body-file "$WORK/pr.md" >/dev/null
  else
    gh pr create --repo "$GITHUB_REPOSITORY" --base main --head "$branch" \
      --title "$title" --body-file "$WORK/pr.md" --label "$REPORT_LABEL" >/dev/null
  fi
  echo "Synced #$issue -> $branch ($row)"
  git checkout --quiet --detach FETCH_HEAD
}

post_merge() {
  local pr="$1"
  require_number "$pr"
  gh pr view "$pr" --repo "$GITHUB_REPOSITORY" --json headRefName,body,state > "$WORK/pr.json"
  local head state row issue
  head="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["headRefName"])' "$WORK/pr.json")"
  state="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["state"])' "$WORK/pr.json")"
  issue="${head#"$BRANCH_PREFIX"}"
  if [[ "$head" != "$BRANCH_PREFIX"* || "$state" != "MERGED" ]]; then
    echo "PR #$pr is not a merged voluntary report PR; skipping."
    return 0
  fi
  require_number "$issue"
  row="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["body"])' "$WORK/pr.json" \
    | sed -n "s/^<!-- $MARKER \(.*\) -->\$/\1/p" | tail -n 1)"
  [[ -n "$row" ]] || { echo "PR #$pr has no accepted-report marker" >&2; exit 1; }
  python3 -c 'import json, sys; json.loads(sys.argv[1])' "$row"
  {
    echo "Thanks! Your report was counted in #$pr and will appear on the site after it redeploys. To change your answers later, edit this issue (do not open a new one)."
    echo
    echo "<!-- $MARKER $row -->"
  } > "$WORK/comment.md"
  ensure_labels
  comment "$issue" "$WORK/comment.md"
  gh issue edit "$issue" --repo "$GITHUB_REPOSITORY" --add-label "$COUNTED_LABEL" >/dev/null
  gh issue close "$issue" --repo "$GITHUB_REPOSITORY" --reason completed >/dev/null 2>&1 || true

  # Other open report PRs were built on the old main; rebuild them so they merge cleanly.
  local branches
  branches="$(gh pr list --repo "$GITHUB_REPOSITORY" --state open --base main --limit 200 \
    --json headRefName --jq ".[].headRefName | select(startswith(\"$BRANCH_PREFIX\"))")"
  for other in $branches; do
    # A child process keeps `set -e` in effect (it is disabled for functions called with ||).
    "$ROOT/scripts/voluntary_pr.sh" sync "${other#"$BRANCH_PREFIX"}" || echo "Could not refresh $other" >&2
  done
}

case "${1:-}" in
  sync) sync "${2:?issue number required}" ;;
  post-merge) post_merge "${2:?pull request number required}" ;;
  *) echo "usage: $0 sync ISSUE | post-merge PR" >&2; exit 2 ;;
esac
