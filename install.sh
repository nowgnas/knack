#!/usr/bin/env bash
# install.sh — 하네스를 에이전트(Claude Code, Codex, Copilot CLI)에 연결한다.
#   스킬·서브에이전트·CLI: 이 레포를 가리키는 심링크           → git pull 만으로 갱신
#   룰: 지시 파일(CLAUDE.md / AGENTS.md / copilot-instructions.md)에 마커 블록 삽입 → 기존 내용 보존
#   Copilot CLI: 스킬은 ~/.agents/skills 를 Codex 와 함께 쓰고, 룰만 연결한다 (서브에이전트·훅·모델 미지원)
#   훅: settings.json / hooks.json 에 --knack-hook 표식 항목만 추가·제거 (lib/knack.py)
#   모델: models.json 기준으로 서브에이전트(Claude 파일·Codex 역할)와 세션 기본 모델 반영 (lib/knack.py)
# macOS 기본 bash 3.2 호환. 훅 JSON 병합에만 python3 사용.
set -euo pipefail

KNACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUPPORTED="claude codex copilot"
CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"
COPILOT_DIR="${COPILOT_HOME:-$HOME/.copilot}"
MD_START="<!-- knack:start"
MD_END="<!-- knack:end -->"
GIT_START="# knack:start"
# 개명(harness → knack) 전 마커. 이미 설치된 파일에서 구 블록을 걷어내는 데만 쓴다
OLD_MD_START="<!-- harness:start"
OLD_MD_END="<!-- harness:end -->"
GIT_END="# knack:end"

ACTION=install
REINSTALL=0
PASS_ARGS=()
MODE=global
PROJECT=""
AGENTS=""
DRY=0
FORCE=0
BACKUP_DIR="$HOME/.knack-backups/$(date +%Y%m%d-%H%M%S)"
N_SKIP=0
N_CHANGE=0

usage() {
  cat <<EOF
사용법: $(basename "$0") [옵션]

  --global              사용자 전역 설정에 설치 (기본값): 스킬·서브에이전트·룰·훅·CLI
  --project <path>      특정 레포에만 설치 (스킬·서브에이전트 링크, .git/info/exclude 등록)
  --agents <list>       대상 에이전트 (쉼표 구분: ${SUPPORTED// /,}). 생략 시 설치된 것 자동 감지
  --status              설치 상태 확인
  --uninstall           제거 (하네스가 만든 링크·블록·훅만 제거)
  --reinstall           제거 후 다시 설치 (설치 상태가 꼬였거나 다른 클론으로 옮길 때)
  --dry-run             변경하지 않고 무엇이 바뀔지만 출력
  --force               기존 파일과 충돌 시 백업(~/.knack-backups) 후 교체
  -h, --help            도움말
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --global) MODE=global; PASS_ARGS=(${PASS_ARGS[@]+"${PASS_ARGS[@]}"} "$1") ;;
    --project) MODE=project; PROJECT="${2:?--project 뒤에 경로가 필요합니다}"
               PASS_ARGS=(${PASS_ARGS[@]+"${PASS_ARGS[@]}"} "$1" "$2"); shift ;;
    --agents) AGENTS="$(echo "${2:?--agents 뒤에 목록이 필요합니다}" | tr ',' ' ')"
              PASS_ARGS=(${PASS_ARGS[@]+"${PASS_ARGS[@]}"} "$1" "$2"); shift ;;
    --status) ACTION=status ;;
    --uninstall) ACTION=uninstall ;;
    --reinstall) REINSTALL=1 ;;
    --dry-run) DRY=1; PASS_ARGS=(${PASS_ARGS[@]+"${PASS_ARGS[@]}"} "$1") ;;
    --force) FORCE=1; PASS_ARGS=(${PASS_ARGS[@]+"${PASS_ARGS[@]}"} "$1") ;;
    -h|--help) usage; exit 0 ;;
    *) echo "알 수 없는 옵션: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

# 재설치: 제거 한 번, 설치 한 번. 각 단계가 그대로 출력되어 무엇이 바뀌는지 보인다
if [ $REINSTALL -eq 1 ]; then
  [ "$ACTION" = install ] || { echo "--reinstall 은 --status·--uninstall 과 함께 쓸 수 없습니다" >&2; exit 2; }
  echo "재설치 1/2 — 제거"
  "$0" --uninstall ${PASS_ARGS[@]+"${PASS_ARGS[@]}"}
  echo
  [ $DRY -eq 1 ] && echo "(dry-run 이라 제거가 실제로 일어나지 않아, 아래 설치 단계는 지금 설치된 상태를 기준으로 계산됩니다)"
  echo "재설치 2/2 — 설치"
  exec "$0" ${PASS_ARGS[@]+"${PASS_ARGS[@]}"}
fi

if [ "$MODE" = project ]; then
  PROJECT="$(cd "$PROJECT" 2>/dev/null && pwd)" || { echo "프로젝트 경로가 없습니다" >&2; exit 1; }
fi

if [ -z "$AGENTS" ]; then
  { [ -d "$HOME/.claude" ] || command -v claude >/dev/null 2>&1; } && AGENTS="claude"
  { [ -d "$CODEX_DIR" ] || command -v codex >/dev/null 2>&1; } && AGENTS="${AGENTS:+$AGENTS }codex"
  { [ -d "$COPILOT_DIR" ] || command -v copilot >/dev/null 2>&1; } && AGENTS="${AGENTS:+$AGENTS }copilot"
  [ -z "$AGENTS" ] && { echo "설치된 에이전트를 찾지 못했습니다. --agents 로 지정하세요." >&2; exit 1; }
fi
for a in $AGENTS; do
  case " $SUPPORTED " in *" $a "*) ;; *) echo "지원하지 않는 에이전트: $a (지원: $SUPPORTED)" >&2; exit 2 ;; esac
done

# ── 공통 유틸 ─────────────────────────────────
pretty() { case "$1" in "$HOME"/*) echo "~${1#"$HOME"}" ;; *) echo "$1" ;; esac; }
say() { printf '  %-7s %s\n' "$1" "$2"; }

backup() {  # 원본을 백업 디렉터리로 복사(copy) 또는 이동(move). 같은 실행에서 이미 백업했으면 원본을 유지
  local dst="$BACKUP_DIR${1#"$HOME"}"
  mkdir -p "$(dirname "$dst")"
  if [ "$2" = move ]; then mv "$1" "$dst"
  elif [ ! -e "$dst" ]; then cp -P "$1" "$dst"; fi
}

# 파일에서 마커 블록을 뺀 내용 (끝의 빈 줄 제거)
strip_block() {
  [ -f "$1" ] || return 0
  awk -v s="$2" -v e="$3" '
    index($0, s) == 1 { skip = 1; next }
    skip && $0 == e   { skip = 0; next }
    skip              { next }
    { buf[++n] = $0 }
    END { while (n > 0 && buf[n] ~ /^[[:space:]]*$/) n--; for (i = 1; i <= n; i++) print buf[i] }' "$1"
}

# ── 대상별 처리 (ACTION 에 따라 설치/제거/상태) ─────
handle_link() {  # src dst
  local src="$1" dst="$2" cur=""
  [ -L "$dst" ] && cur="$(readlink "$dst")"
  case "$ACTION" in
    status)
      if [ "$cur" = "$src" ]; then say OK "$(pretty "$dst")"
      elif [ -n "$cur" ] && knack_link "$cur"; then say STALE "$(pretty "$dst") (다른 knack 클론을 가리킴 → install 시 교체)"
      elif moved_link "$dst" "$src"; then say STALE "$(pretty "$dst") (옮겨지거나 사라진 knack 폴더를 가리킴 → install 시 교체)"
      elif [ -e "$dst" ] || [ -L "$dst" ]; then say CONFLICT "$(pretty "$dst") (하네스가 아닌 파일)"
      else say MISSING "$(pretty "$dst")"; fi ;;
    uninstall)
      if { [ -n "$cur" ] && knack_link "$cur"; } || moved_link "$dst" "$src"; then
        N_CHANGE=$((N_CHANGE + 1)); say REMOVE "$(pretty "$dst")"; [ $DRY -eq 1 ] || rm "$dst"
      fi ;;
    install)
      if [ "$cur" = "$src" ]; then say OK "$(pretty "$dst")"; return; fi
      if [ -e "$dst" ] || [ -L "$dst" ]; then
        if { [ -n "$cur" ] && knack_link "$cur"; } || moved_link "$dst" "$src"; then
          :  # 하네스(이 폴더, 다른 클론, 옮기기 전 폴더)의 링크 → 백업 없이 교체
        elif [ $FORCE -eq 0 ]; then
          N_SKIP=$((N_SKIP + 1)); say SKIP "$(pretty "$dst") (기존 항목 존재. --force 로 백업 후 교체)"; return
        else
          say BACKUP "$(pretty "$dst")"; [ $DRY -eq 1 ] || backup "$dst" move
        fi
        [ $DRY -eq 1 ] || rm -f "$dst"
      fi
      N_CHANGE=$((N_CHANGE + 1)); say LINK "$(pretty "$dst") -> $(pretty "$src")"
      [ $DRY -eq 1 ] && return
      mkdir -p "$(dirname "$dst")"
      ln -s "$src" "$dst" ;;
  esac
}

# 링크가 knack 레포를 가리키는지 — 이 폴더뿐 아니라 다른 클론도 포함한다.
# 하네스를 수정하는 폴더와 사용자로 쓰는 클론이 따로 있을 때 서로 넘겨받을 수 있어야 한다.
knack_link() {  # 링크 대상 경로
  local root="$1"
  case "$root" in "$KNACK_DIR"/*) return 0 ;; esac
  while [ -n "$root" ] && [ "$root" != "/" ] && [ "$root" != "." ]; do
    root="$(dirname "$root")"
    [ -f "$root/bin/knack" ] && [ -f "$root/lib/knack.py" ] && [ -f "$root/install.sh" ] && return 0
  done
  return 1
}

# 레포 폴더를 옮기거나 이름을 바꾸면 링크 대상이 사라져 knack_link 로는 알아볼 수 없다.
# 끊어진 링크이면서 대상의 끝 두 경로(skills/<이름>, bin/knack)가 이 레포의 원본과 같으면 우리 링크로 본다.
moved_link() {  # dst src
  local cur
  [ -L "$1" ] && [ ! -e "$1" ] || return 1
  cur="$(readlink "$1")"
  [ "$(basename "$(dirname "$cur")")/$(basename "$cur")" = "$(basename "$(dirname "$2")")/$(basename "$2")" ]
}

# 하네스를 가리키지만 대상이 사라진 링크 정리 (스킬 삭제·이름 변경 후)
prune_links() {  # dir
  local l t
  [ -d "$1" ] || return 0
  for l in "$1"/* "$1"/.[!.]*; do
    [ -L "$l" ] || continue
    t="$(readlink "$l")"
    case "$t" in "$KNACK_DIR"/*) ;; *) continue ;; esac
    case "$ACTION" in
      install) [ -e "$l" ] && continue
               # 이름이 아직 하네스에 있으면 handle_link 가 교체한다 (dry-run 에서 중복 보고 방지)
               [ -e "$KNACK_DIR/skills/$(basename "$l")" ] || [ -e "$KNACK_DIR/agents/$(basename "$l")" ] && continue
               N_CHANGE=$((N_CHANGE + 1)); say PRUNE "$(pretty "$l") (하네스에서 삭제된 항목)"; [ $DRY -eq 1 ] || rm "$l" ;;
      uninstall) N_CHANGE=$((N_CHANGE + 1)); say REMOVE "$(pretty "$l")"; [ $DRY -eq 1 ] || rm "$l" ;;
      status) [ -e "$l" ] || say BROKEN "$(pretty "$l") (대상 없음 → install 시 정리)" ;;
    esac
  done
}

# 개명(harness → knack) 전 이름으로 설치된 링크 정리. 우리가 만든 이름만, 그리고
# 하네스를 가리키거나 끊어진 링크만 건드린다 (레포 폴더까지 개명하면 옛 링크는 끊어진다)
OLD_LINK_NAMES="harness-help harness-manage"
cleanup_old_link() {  # path 설명
  local l="$1" what="$2" tgt
  [ -L "$l" ] || return 0
  tgt="$(readlink "$l")"
  case "$tgt" in
    "$KNACK_DIR"/*) ;;                      # 이 레포를 가리키는 옛 링크
    *) [ -e "$l" ] && return 0 ;;           # 살아 있는 남의 링크는 두고, 끊어진 것만 정리
  esac
  if [ "$ACTION" = status ]; then say STALE "$(pretty "$l") ($what → install 시 정리)"; return 0; fi
  N_CHANGE=$((N_CHANGE + 1)); say REMOVE "$(pretty "$l") ($what)"
  [ $DRY -eq 1 ] || rm -f "$l"
}
prune_old_names() {  # dir
  local n
  for n in $OLD_LINK_NAMES; do cleanup_old_link "$1/$n" "개명 전 스킬 링크"; done
}

handle_block() {  # file start end content
  local file="$1" start="$2" end="$3" content="$4" base current new hdr
  base="$(strip_block "$file" "$start" "$end")"
  # 개명 전 블록이 남아 있으면 같이 걷어낸다 (룰이 두 번 주입되지 않게)
  if [ "$start" = "$MD_START" ]; then
    base="$(printf '%s\n' "$base" | awk -v s="$OLD_MD_START" -v e="$OLD_MD_END" '
      index($0, s) == 1 { skip = 1; next }
      skip && $0 == e   { skip = 0; next }
      skip              { next }
      { buf[++n] = $0 }
      END { while (n > 0 && buf[n] ~ /^[[:space:]]*$/) n--; for (i = 1; i <= n; i++) print buf[i] }')"
  fi
  current="$([ -f "$file" ] && cat "$file" || true)"
  hdr="$start (managed by $(pretty "$KNACK_DIR")/install.sh — 직접 수정 금지)"
  [ "$start" = "$MD_START" ] && hdr="$hdr -->"
  new="$(printf '%s\n%s\n%s' "$hdr" "$content" "$end")"
  [ -n "$base" ] && new="$(printf '%s\n\n%s' "$base" "$new")"
  case "$ACTION" in
    status)
      if [ "$current" = "$new" ]; then say OK "$(pretty "$file") (블록 최신)"
      elif grep -qF "$start" "$file" 2>/dev/null; then say STALE "$(pretty "$file") (블록 갱신 필요 → install.sh 재실행)"
      else say MISSING "$(pretty "$file") (블록 없음)"; fi ;;
    uninstall)
      grep -qF "$start" "$file" 2>/dev/null || return 0
      N_CHANGE=$((N_CHANGE + 1)); say UNBLOCK "$(pretty "$file")"
      [ $DRY -eq 1 ] && return
      backup "$file" copy
      # 블록만 있던 파일은 지운다 (설치 전 상태. 원본은 위에서 백업)
      if [ -n "$base" ]; then printf '%s\n' "$base" > "$file"; else rm -f "$file"; fi ;;
    install)
      if [ "$current" = "$new" ]; then say OK "$(pretty "$file") (블록 최신)"; return; fi
      N_CHANGE=$((N_CHANGE + 1)); say BLOCK "$(pretty "$file") (하네스 블록 추가/갱신)"
      [ $DRY -eq 1 ] && return
      [ -f "$file" ] && backup "$file" copy
      mkdir -p "$(dirname "$file")"
      printf '%s\n' "$new" > "$file" ;;
  esac
}

# JSON·TOML 설정 동기화 (lib/knack.py). 출력 마지막 줄 "@@ changes=N skips=M" 로 집계
py_sync() {  # label, knack.py 인자...
  local label="$1" out c s
  shift
  if ! command -v python3 >/dev/null 2>&1; then
    N_SKIP=$((N_SKIP + 1)); say SKIP "$label: python3 가 없어 건너뜀"; return
  fi
  out="$(python3 "$KNACK_DIR/lib/knack.py" "$@" --action "$ACTION" --knack "$KNACK_DIR" \
    --backup-dir "$BACKUP_DIR" $( [ $DRY -eq 1 ] && echo --dry-run ) $( [ $FORCE -eq 1 ] && echo --force ))" ||
    { N_SKIP=$((N_SKIP + 1)); say ERROR "$label 동기화 실패"; return; }
  printf '%s\n' "$out" | grep -v '^@@' || true
  c="$(printf '%s\n' "$out" | sed -n 's/^@@ changes=\([0-9]*\).*/\1/p')"
  s="$(printf '%s\n' "$out" | sed -n 's/^@@ .*skips=\([0-9]*\).*/\1/p')"
  N_CHANGE=$((N_CHANGE + ${c:-0}))
  N_SKIP=$((N_SKIP + ${s:-0}))
}
sync_hooks() { py_sync "훅" hooks-sync --agent "$1" --file "$2"; }
sync_models() { py_sync "모델·서브에이전트" models-sync --agent "$@"; }
models_index() {
  command -v python3 >/dev/null 2>&1 || return 0
  python3 "$KNACK_DIR/lib/knack.py" models-index --agent "$1" 2>/dev/null || true
}
# 사용자 페르소나(설정했을 때만). 결정에 쓰이는 사실이라 블록 맨 앞에 둔다
persona_block() {
  command -v python3 >/dev/null 2>&1 || return 0
  python3 "$KNACK_DIR/lib/knack.py" persona-block 2>/dev/null || true
}

# ── 항목 목록 ─────────────────────────────────
skill_names() { for d in "$KNACK_DIR"/skills/*/; do [ -f "$d/SKILL.md" ] && basename "$d"; done; }

rule_load() { sed -n 's/^load: *//p' "$1" | head -1; }
always_rules() {
  local f
  for f in "$KNACK_DIR"/rules/*.md; do
    [ -f "$f" ] || continue
    [ "$(rule_load "$f")" = on-demand ] || echo "$f"
  done
}
# on-demand 룰은 본문 대신 한 줄 색인만 넣는다 (토큰 절약)
ondemand_index() {
  local f name when found=0
  for f in "$KNACK_DIR"/rules/*.md; do
    [ -f "$f" ] && [ "$(rule_load "$f")" = on-demand ] || continue
    [ $found -eq 0 ] && echo "필요할 때 읽는 룰 (\`knack show rule <이름>\`):"
    found=1
    name="$(sed -n 's/^name: *//p' "$f" | head -1)"
    when="$(sed -n 's/^when: *//p' "$f" | head -1)"
    echo "- \`${name:-$(basename "$f" .md)}\`${when:+ — $when}"
  done
}
rule_body() {  # frontmatter 와 앞뒤 빈 줄 제거
  awk 'NR == 1 && $0 == "---" { fm = 1; next }
       fm { if ($0 == "---") fm = 0; next }
       { buf[++n] = $0 }
       END { s = 1; while (s <= n && buf[s] ~ /^[[:space:]]*$/) s++
             while (n >= s && buf[n] ~ /^[[:space:]]*$/) n--
             for (i = s; i <= n; i++) print buf[i] }' "$1"
}
claude_rules() {
  local idx
  idx="$(persona_block)"
  [ -z "$idx" ] || printf '%s\n\n' "$idx"
  always_rules | sed 's/^/@/'
  idx="$(ondemand_index)"
  [ -z "$idx" ] || printf '\n%s\n' "$idx"
  idx="$(models_index claude)"
  [ -z "$idx" ] || printf '\n%s\n' "$idx"
}
# 룰 본문을 그대로 넣는다 (@import 를 읽지 않는 에이전트용). 인자: 모델 색인을 넣을 에이전트 (없으면 생략)
inline_rules() {
  local f first=1 idx
  idx="$(persona_block)"
  [ -z "$idx" ] || printf '%s\n\n' "$idx"
  while IFS= read -r f; do
    [ $first -eq 1 ] || echo
    first=0
    rule_body "$f"
  done < <(always_rules)
  idx="$(ondemand_index)"
  [ -z "$idx" ] || printf '\n%s\n' "$idx"
  [ -z "${1:-}" ] || idx="$(models_index "$1")"
  [ -z "${1:-}" ] || [ -z "$idx" ] || printf '\n%s\n' "$idx"
}

# 링크 대상 목록을 "src<TAB>dst" 로 출력 (서브에이전트는 모델을 넣어 생성하므로 sync_models 가 처리)
targets_claude() {  # base_dir
  local s
  for s in $(skill_names); do printf '%s\t%s\n' "$KNACK_DIR/skills/$s" "$1/skills/$s"; done
}
agent_files() { local f; for f in "$KNACK_DIR"/agents/*.md; do [ -f "$f" ] && basename "$f"; done; }
targets_codex() {  # skills_dir
  local s
  for s in $(skill_names); do printf '%s\t%s\n' "$KNACK_DIR/skills/$s" "$1/$s"; done
}
# Copilot CLI 는 ~/.agents/skills(프로젝트는 .agents/skills)도 읽는다. Codex 와 함께 설치하면 그쪽이 처리한다
copilot_shares_codex() { case " $AGENTS " in *" codex "*) return 0 ;; *) return 1 ;; esac; }

process_links() { local src dst; while IFS="$(printf '\t')" read -r src dst; do handle_link "$src" "$dst"; done; }

# ── 실행 ─────────────────────────────────────
case "$ACTION" in
  install) title="설치" ;; uninstall) title="제거" ;; status) title="상태" ;;
esac
echo "하네스 $title — $(pretty "$KNACK_DIR")"
echo "  모드: $MODE${PROJECT:+ ($(pretty "$PROJECT"))} · 에이전트: $AGENTS$( [ $DRY -eq 1 ] && echo ' · [dry-run: 실제 변경 없음]')"

for agent in $AGENTS; do
  echo
  echo "[$agent]"
  if [ "$MODE" = global ]; then
    case "$agent" in
      claude)
        process_links < <(targets_claude "$HOME/.claude")
        prune_links "$HOME/.claude/skills"
        prune_old_names "$HOME/.claude/skills"
        sync_models claude
        handle_block "$HOME/.claude/CLAUDE.md" "$MD_START" "$MD_END" "$(claude_rules)"
        sync_hooks claude "$HOME/.claude/settings.json" ;;
      codex)
        process_links < <(targets_codex "$HOME/.agents/skills")
        prune_links "$HOME/.agents/skills"
        prune_old_names "$HOME/.agents/skills"
        sync_models codex
        handle_block "$CODEX_DIR/AGENTS.md" "$MD_START" "$MD_END" "$(inline_rules codex)"
        sync_hooks codex "$CODEX_DIR/hooks.json" ;;
      copilot)
        if copilot_shares_codex; then say SHARED "$(pretty "$HOME/.agents/skills") (스킬은 codex 와 공유)"
        else
          process_links < <(targets_codex "$HOME/.agents/skills")
          prune_links "$HOME/.agents/skills"
        fi
        handle_block "$COPILOT_DIR/copilot-instructions.md" "$MD_START" "$MD_END" "$(inline_rules)" ;;
    esac
  else
    case "$agent" in
      claude)
        process_links < <(targets_claude "$PROJECT/.claude")
        prune_links "$PROJECT/.claude/skills"
        prune_old_names "$PROJECT/.claude/skills"
        sync_models claude --agents-dir "$PROJECT/.claude/agents" --no-main ;;
      codex)
        process_links < <(targets_codex "$PROJECT/.agents/skills")
        prune_links "$PROJECT/.agents/skills"
        prune_old_names "$PROJECT/.agents/skills" ;;
      copilot)
        if copilot_shares_codex; then say SHARED "$(pretty "$PROJECT/.agents/skills") (스킬은 codex 와 공유)"
        else
          process_links < <(targets_codex "$PROJECT/.agents/skills")
          prune_links "$PROJECT/.agents/skills"
        fi ;;
    esac
  fi
done

# 글로벌 모드: 터미널 명령 knack
if [ "$MODE" = global ]; then
  echo
  echo "[cli]"
  handle_link "$KNACK_DIR/bin/knack" "$HOME/.local/bin/knack"
  cleanup_old_link "$HOME/.local/bin/harness" "개명 전 CLI 링크"
  if [ "$ACTION" = install ]; then
    case ":$PATH:" in
      *":$HOME/.local/bin:"*) ;;
      *) echo "  참고: ~/.local/bin 이 PATH에 없습니다. 셸 설정에 export PATH=\"\$HOME/.local/bin:\$PATH\" 를 추가하세요." ;;
    esac
  fi
fi

# 프로젝트 모드: 심링크가 커밋되지 않도록 로컬 전용 exclude 에 등록
if [ "$MODE" = project ] && [ -d "$PROJECT/.git" ]; then
  echo
  echo "[git]"
  excl=""
  for agent in $AGENTS; do
    if [ "$agent" = claude ]; then
      excl="$excl$(targets_claude "/.claude" | cut -f2)"$'\n'
      excl="$excl$(agent_files | sed 's|^|/.claude/agents/|')"$'\n'
    elif [ "$agent" = copilot ] && copilot_shares_codex; then
      continue
    else
      excl="$excl$(targets_codex "/.agents/skills" | cut -f2)"$'\n'
    fi
  done
  excl="$(printf '%s' "$excl" | sed '/^$/d')"
  # 다른 에이전트 조합으로 재설치해도 이전 항목이 남지 않도록 블록 전체를 교체
  handle_block "$PROJECT/.git/info/exclude" "$GIT_START" "$GIT_END" "$excl"
fi

echo
case "$ACTION" in
  status) ;;
  *)
    backup_note=""
    [ -d "$BACKUP_DIR" ] && backup_note=" · 백업: $(pretty "$BACKUP_DIR")"
    [ $DRY -eq 1 ] && echo "dry-run 완료: 변경 예정 ${N_CHANGE}건, 건너뜀 ${N_SKIP}건" ||
      echo "완료: 변경 ${N_CHANGE}건, 건너뜀 ${N_SKIP}건${backup_note}"
    [ "$ACTION" = install ] && [ $DRY -eq 0 ] && [ $N_CHANGE -gt 0 ] && echo "새 에이전트 세션부터 적용됩니다."
    [ "$MODE" = project ] && [ "$ACTION" = install ] && echo "참고: 프로젝트 모드는 스킬·서브에이전트만 설치합니다. 룰·훅은 --global 에서 적용됩니다."
    ;;
esac
exit 0
