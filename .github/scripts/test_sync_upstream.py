"""Exercise synchronization against disposable local repositories, without network."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

SCRIPT = Path(__file__).with_name('sync_upstream.py').resolve()
ROOT = SCRIPT.parents[2]


def run(*args, cwd, ok=True):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if ok and result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return result


def git(*args, cwd):
    return run('git', *args, cwd=cwd).stdout.strip()


def commit(repo, name, content):
    file = repo / name
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(content, encoding='utf-8')
    git('add', '--', name, cwd=repo)
    git('commit', '-m', name, cwd=repo)


def main():
    folder = ROOT / '.build' / ('sync-check-' + uuid.uuid4().hex)
    folder.mkdir(parents=True)
    try:
        source, remote, fork = (folder / name for name in ('source', 'remote.git', 'fork'))
        source.mkdir()
        git('init', '-b', 'main', cwd=source)
        git('config', 'user.name', 'Sync test', cwd=source)
        git('config', 'user.email', 'sync-test@example.invalid', cwd=source)
        commit(source, 'game.txt', 'original\n')
        git('clone', '--no-hardlinks', '--bare', str(source), str(remote), cwd=folder)
        git('clone', '--no-hardlinks', str(remote), str(fork), cwd=folder)
        git('config', 'user.name', 'Sync test', cwd=fork)
        git('config', 'user.email', 'sync-test@example.invalid', cwd=fork)
        commit(fork, '.github/workflows/sync-upstream.yml', 'scheduler\n')
        git('push', 'origin', 'main', cwd=fork)

        def synchronize(ok=True):
            return run(sys.executable, str(SCRIPT), '--upstream', str(source), cwd=fork, ok=ok)

        before = git('rev-parse', 'main', cwd=remote)
        assert 'Already up to date' in synchronize().stdout
        assert git('rev-parse', 'main', cwd=remote) == before
        commit(source, 'game.txt', 'upstream update\n')
        assert 'Synchronized' in synchronize().stdout
        assert (fork / 'game.txt').read_text() == 'upstream update\n'
        assert (fork / '.github/workflows/sync-upstream.yml').exists()
        assert git('rev-parse', 'main', cwd=remote) == git('rev-parse', 'HEAD', cwd=fork)

        commit(fork, 'local-fix.txt', 'keep this fix\n')
        commit(source, 'next.txt', 'new upstream commit\n')
        before = git('rev-parse', 'main', cwd=remote)
        result = synchronize(ok=False)
        assert result.returncode and 'Fork-specific changes' in result.stdout
        assert git('rev-parse', 'main', cwd=remote) == before
        assert (fork / 'local-fix.txt').read_text() == 'keep this fix\n'
        git('switch', '-c', 'fix/example', cwd=fork)
        assert 'Only main' in synchronize(ok=False).stdout
        print('Sync checks passed: no-op, upstream merge, workflow retained, local fix protected, main only.')
    finally:
        # All disposable repositories are created under this unique workspace directory.
        if folder.resolve().parent != (ROOT / '.build').resolve():
            raise RuntimeError('Unexpected temporary repository path')
        def writable(function, path, exc):
            os.chmod(path, 0o777)
            function(path)
        shutil.rmtree(folder, onerror=writable)


if __name__ == '__main__':
    main()
