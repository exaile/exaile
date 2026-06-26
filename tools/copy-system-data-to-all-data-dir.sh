#!/usr/bin/env bash
#
# Copy an existing Exaile user profile into the flat layout used by:
#
#   exaile --all-data-dir=/path/to/target
#
# In that mode Exaile points data_home, config_home, and cache_home at the same
# directory. Files that normally live below these XDG roots are therefore copied
# directly into the target directory, not into data/, config/, or cache/
# subdirectories.

set -euo pipefail

usage() {
    cat <<EOF
Usage: ${0##*/} TARGET_DIR

Copy Exaile data from the current user's system XDG locations into TARGET_DIR
so it can be used with:

    exaile --all-data-dir=TARGET_DIR

Sources:
  data:   \${XDG_DATA_HOME:-\$HOME/.local/share}/exaile
  config: \${XDG_CONFIG_HOME:-\$HOME/.config}/exaile
  cache:  \${XDG_CACHE_HOME:-\$HOME/.cache}/exaile
  logs:   \${XDG_CACHE_HOME:-\$HOME/.cache}/exaile/logs -> TARGET_DIR/logs
EOF
}

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

abs_path() {
    local path=$1
    local dir base

    if [[ $path = /* ]]; then
        dir=${path%/*}
        base=${path##*/}
    else
        dir=${path%/*}
        base=${path##*/}
        if [[ $dir = "$base" ]]; then
            dir=.
        fi
    fi

    mkdir -p "$dir"
    dir=$(cd "$dir" && pwd -P)
    printf '%s/%s\n' "$dir" "$base"
}

copy_tree_contents() {
    local label=$1
    local source=$2
    local target=$3

    if [[ ! -d $source ]]; then
        printf 'skip %-7s %s (missing)\n' "$label:" "$source"
        return
    fi

    if [[ $(abs_path "$source") = "$target" ]]; then
        printf 'skip %-7s %s (already target)\n' "$label:" "$source"
        return
    fi

    printf 'copy %-7s %s -> %s\n' "$label:" "$source" "$target"
    (
        shopt -s dotglob nullglob
        cp -a "$source"/* "$target"/
    )
}

warn_conflicts() {
    local target=$1
    shift

    local tmp seen rel source
    tmp=$(mktemp)
    trap 'rm -f "$tmp"' RETURN

    for source in "$@"; do
        [[ -d $source ]] || continue
        [[ $(abs_path "$source") != "$target" ]] || continue
        (
            cd "$source"
            find . -mindepth 1 -print | sed 's#^\./##'
        ) >> "$tmp"
    done

    seen=$(sort "$tmp" | uniq -d)
    if [[ -n $seen ]]; then
        printf 'warning: duplicate relative paths found across source roots;\n' >&2
        printf '         later copies overwrite earlier copies in all-data-dir layout:\n' >&2
        while IFS= read -r rel; do
            printf '         %s\n' "$rel" >&2
        done <<< "$seen"
    fi
}

if [[ ${1:-} = "-h" || ${1:-} = "--help" ]]; then
    usage
    exit 0
fi

[[ $# -eq 1 ]] || {
    usage >&2
    exit 2
}

[[ -n ${HOME:-} ]] || die "HOME is not set"

target=$(abs_path "$1")
data_home="${XDG_DATA_HOME:-$HOME/.local/share}/exaile"
config_home="${XDG_CONFIG_HOME:-$HOME/.config}/exaile"
cache_home="${XDG_CACHE_HOME:-$HOME/.cache}/exaile"
logs_home="$cache_home/logs"

mkdir -p "$target"

warn_conflicts "$target" "$cache_home" "$data_home" "$config_home"

# Copy cache first, then data, then config. This keeps persistent data and
# settings authoritative if an unusual profile has duplicate relative paths.
copy_tree_contents "cache" "$cache_home" "$target"
copy_tree_contents "data" "$data_home" "$target"
copy_tree_contents "config" "$config_home" "$target"

# The intended all-data-dir layout keeps logs below TARGET_DIR/logs. The current
# Linux code path derives logs_home before --all-data-dir is applied, so this
# explicit copy preserves the documented layout for profiles and debugging.
if [[ -d $logs_home && $(abs_path "$logs_home") != "$target/logs" ]]; then
    mkdir -p "$target/logs"
    copy_tree_contents "logs" "$logs_home" "$target/logs"
fi

printf 'done: run Exaile with --all-data-dir=%s\n' "$target"
