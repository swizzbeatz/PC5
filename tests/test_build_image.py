#!/usr/bin/env python3
"""Run the workflow's image output command for mixed-case fork owners."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
workflow = (root / '.github/workflows/build.yml').read_text(encoding='utf-8')
command, = [line.strip() for line in workflow.splitlines()
            if line.strip().startswith('echo "image=ghcr.io/')]
assert 'PC5_IMAGE_OWNER: ${{ github.repository_owner }}' in workflow
digest = hashlib.sha256((root / 'tools/Dockerfile').read_bytes()
                        + (root / 'tools/packages.txt').read_bytes()).hexdigest()[:16]
bash = (str(Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Git/bin/bash.exe')
        if os.name == 'nt' else shutil.which('bash'))
for owner in ('SwizzBeatz', 'bornaradusin', 'Mixed-Case-Org', 'USER123'):
    env = dict(os.environ, PC5_IMAGE_OWNER=owner, GITHUB_OUTPUT='/dev/stdout')
    result = subprocess.run([bash, '-c', command], cwd=root, env=env,
                            check=True, capture_output=True, text=True)
    expected = f'image=ghcr.io/{owner.lower()}/pc5-build:{digest}'
    assert result.stdout.strip() == expected, owner
print('Build image: mixed-case owners normalized; image fingerprint preserved')
