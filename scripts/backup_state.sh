#!/usr/bin/env bash
# 为运行中的 SQLite 状态库创建一致性 gzip 快照，并按份数清理旧备份。

set -eu

DB_PATH="${1:-}"
BACKUP_DIR="${2:-}"
RETENTION_COUNT="${3:-14}"

if [ -z "$DB_PATH" ] || [ -z "$BACKUP_DIR" ]; then
  echo "用法: $0 <db_path> <backup_dir> [retention_count]" >&2
  exit 2
fi

if [ ! -f "$DB_PATH" ]; then
  echo "状态库不存在: $DB_PATH" >&2
  exit 1
fi

case "$RETENTION_COUNT" in
  ''|*[!0-9]*|0)
    echo "retention_count 必须是正整数" >&2
    exit 2
    ;;
esac

mkdir -p "$BACKUP_DIR"

TODAY="$(date +%F)"
SNAPSHOT_TMP="$BACKUP_DIR/.state-$TODAY.db.tmp"
ARCHIVE_TMP="$BACKUP_DIR/.state-$TODAY.db.gz.tmp"
ARCHIVE_PATH="$BACKUP_DIR/state-$TODAY.db.gz"

cleanup() {
  rm -f "$SNAPSHOT_TMP" "$ARCHIVE_TMP"
}
trap cleanup EXIT HUP INT TERM

# SQLite 的 .backup API 会在数据库仍有写入时生成事务一致的在线快照。
sqlite3 "$DB_PATH" ".backup \"$SNAPSHOT_TMP\""
gzip -c "$SNAPSHOT_TMP" > "$ARCHIVE_TMP"
mv -f "$ARCHIVE_TMP" "$ARCHIVE_PATH"

BACKUP_LIST="$(find "$BACKUP_DIR" -maxdepth 1 -type f \
  -name 'state-????-??-??.db.gz' -print | sort)"
BACKUP_COUNT="$(printf '%s\n' "$BACKUP_LIST" | sed '/^$/d' | wc -l | tr -d ' ')"

if [ "$BACKUP_COUNT" -gt "$RETENTION_COUNT" ]; then
  REMOVE_COUNT=$((BACKUP_COUNT - RETENTION_COUNT))
  printf '%s\n' "$BACKUP_LIST" | sed '/^$/d' | head -n "$REMOVE_COUNT" | \
    while IFS= read -r old_backup; do
      rm -f "$old_backup"
    done
fi

echo "备份完成: $ARCHIVE_PATH"
