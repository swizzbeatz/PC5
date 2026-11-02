"""Keep this fork's main current without overwriting game fixes or force pushing."""
import argparse
import os
from pathlib import Path
import subprocess

UPSTREAM = 'https://github.com/bornaradusin/PC5.git'
AUTOMATION_FILES = (
    '.github/workflows/sync-upstream.yml',
    '.github/scripts/sync_upstream.py',
    '.github/scripts/test_sync_upstream.py',
)


def git(*args, check=True):
    return subprocess.run(['git', *args], check=check, capture_output=True, text=True)


def synchronize(upstream=UPSTREAM):
    if git('branch', '--show-current').stdout.strip() != 'main':
        raise RuntimeError('Only main may be synchronized.')
    if git('status', '--porcelain', '--untracked-files=no').stdout.strip():
        raise RuntimeError('Tracked local changes must be saved before synchronization.')
    git('fetch', '--no-tags', upstream, 'main')
    source = git('rev-parse', 'FETCH_HEAD').stdout.strip()
    ancestor = git('merge-base', '--is-ancestor', source, 'HEAD', check=False)
    if ancestor.returncode == 0:
        return 'Already up to date; no push needed.'
    if ancestor.returncode != 1:
        raise RuntimeError(ancestor.stderr)
    base = git('merge-base', 'HEAD', source).stdout.strip()
    # The scheduler must live on main, so its own files are the only allowed
    # fork-specific changes. Real fixes belong on separate branches.
    exclusions = [f':(exclude){name}' for name in AUTOMATION_FILES]
    changes = git('diff', '--name-only', base, 'HEAD', '--', '.', *exclusions).stdout.strip()
    if changes:
        raise RuntimeError('Fork-specific changes on main require review; no merge or push:\n' + changes)
    git('config', 'user.name', 'github-actions[bot]')
    git('config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
    merged = git('merge', '--no-edit', source, check=False)
    if merged.returncode:
        git('merge', '--abort', check=False)
        raise RuntimeError('Merge failed; nothing pushed.\n' + merged.stderr + merged.stdout)
    # A concurrent update or branch protection rejects this normal push;
    # never discard another writer's work with --force.
    git('push', 'origin', 'HEAD:refs/heads/main')
    return f'Synchronized main with upstream {source}.'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', default=UPSTREAM)
    args = parser.parse_args()
    try:
        message = synchronize(args.upstream)
    except (RuntimeError, subprocess.CalledProcessError) as error:
        detail = error.stderr if isinstance(error, subprocess.CalledProcessError) else str(error)
        print(detail)
        raise SystemExit(1) from error
    print(message)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a', encoding='utf-8') as summary:
            summary.write(message + '\n')


if __name__ == '__main__':
    main()
