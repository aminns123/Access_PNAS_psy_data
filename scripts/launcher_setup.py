"""Shared offline startup gate and setup/update for Windows and Unix launchers."""
from pathlib import Path
import hashlib
import importlib
import importlib.metadata
import os
import subprocess
import sys
import tomllib
import venv
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]

VERIFY_MODULES = (
    'psyview.app',
    'psyview.data.pnas_psychophysics',
    'psyview.plotting.matplotlib_plots',
)


def verify_install():
    """Fast in-process verification for an already-established environment."""
    importlib.metadata.distribution('psyview')
    for name in VERIFY_MODULES:
        importlib.import_module(name)


def verify_install_fresh(root):
    """Verify a just-installed editable package in a fresh Python process.

    Editable installs can add the project's ``src`` directory through
    interpreter-startup path configuration. The launcher process performing the
    pip install was already running before that configuration existed, so a
    same-process import can incorrectly fail immediately after a successful
    install. A child interpreter accurately represents the process that will
    actually launch PsyView next.
    """
    root = Path(root).resolve()
    log = root / '.venv' / '.psyview_setup.log'

    checks = [
        "import importlib",
        "import importlib.metadata",
        "importlib.metadata.distribution('psyview')",
    ]
    checks.extend(
        f"importlib.import_module({name!r})"
        for name in VERIFY_MODULES
    )
    command = [
        sys.executable,
        '-c',
        '; '.join(checks),
    ]

    with log.open('a', encoding='utf-8') as stream:
        stream.write('\nFresh-interpreter import verification\n')
        stream.flush()
        result = subprocess.run(
            command,
            cwd=root,
            stdout=stream,
            stderr=subprocess.STDOUT,
        )

    if result.returncode:
        raise ImportError(
            'PsyView could not be imported by a fresh environment Python '
            f'(exit {result.returncode}). See {log}'
        )


def install(arguments, stage, root):
    log = root / '.venv' / '.psyview_setup.log'
    command = [sys.executable, '-m', 'pip', '--disable-pip-version-check',
               'install', '--retries', '5', '--timeout', '60', *arguments]
    with log.open('a', encoding='utf-8') as stream:
        stream.write(f'\n{stage}\n')
        stream.flush()
        result = subprocess.run(command, cwd=root, stdout=stream, stderr=subprocess.STDOUT)
    if result.returncode:
        detail = log.read_text(encoding='utf-8', errors='replace')
        network = any(term in detail.lower() for term in (
            'connectionerror', 'connectionreset', 'connection broken',
            'failed to establish', 'could not fetch', 'timed out',
            'network is unreachable', 'name resolution', 'proxyerror', 'sslerror'))
        print(f'ERROR: {stage} failed.', flush=True)
        if network:
            print('Network/PyPI access failed. Setup/update needs access to the configured package index or a complete local package cache.')
        print(f'Full package installation output: {log}')
        return False
    return True


def setup(root=ROOT):
    root = root.resolve()
    environment = root / '.venv'
    marker = environment / '.psyview_pyproject_hash'
    pending = environment / '.psyview_setup_pending'
    content = (root / 'pyproject.toml').read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    saved = marker.read_text(encoding='ascii').strip() if marker.exists() else None
    if saved == digest and not pending.exists():
        try:
            verify_install()
        except Exception as exc:
            print(f'ERROR: PsyView import failure: {exc}')
            print('The existing environment will be repaired without deleting it.')
        else:
            print('[PsyView] Project dependencies unchanged', flush=True)
            return 0
    elif saved is None:
        print('[PsyView] Initial setup required: no successful setup hash recorded.', flush=True)
    else:
        print('[PsyView] Dependency configuration changed or previous setup was interrupted.', flush=True)
    print('[PsyView] Setup/update may need an internet connection; normal unchanged startup does not.', flush=True)
    build = tomllib.loads(content.decode('utf-8'))['build-system']
    if build.get('build-backend') != 'setuptools.build_meta' or build.get('backend-path'):
        print('ERROR: Unsupported build backend. Review launcher setup before installing this configuration.')
        return 1
    requirements = build.get('requires')
    if not isinstance(requirements, list) or not requirements or not all(isinstance(x, str) for x in requirements):
        print('ERROR: Invalid build-system.requires in pyproject.toml.')
        return 1
    pending.write_text(digest, encoding='ascii')
    (environment / '.psyview_setup.log').write_text('', encoding='utf-8')
    # ensurepip uses Python's bundled wheels and does not access the network.
    if subprocess.run([sys.executable, '-m', 'pip', '--version'], stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL).returncode:
        if subprocess.run([sys.executable, '-m', 'ensurepip']).returncode:
            print('ERROR: Bundled pip bootstrap failed.')
            return 1
    print('[PsyView] Installing declared build tools...', flush=True)
    if not install(requirements, 'Build-tool installation', root):
        return 1
    print('[PsyView] Installing project dependencies...', flush=True)
    if not install(['-e', '.', '--no-build-isolation'], 'Project dependency installation', root):
        return 1
    if subprocess.run([sys.executable, '-m', 'pip', '--disable-pip-version-check', 'check'], cwd=root).returncode:
        print('ERROR: Installed dependency consistency check failed.')
        return 1

    # IMPORTANT: verify a fresh install using a NEW interpreter. The current
    # launcher process pre-dates the editable-install path configuration and
    # may not see it even though the next PsyView process will.
    try:
        verify_install_fresh(root)
    except Exception as exc:
        print(f'ERROR: PsyView import failure after installation: {exc}')
        return 1

    if (root / 'pyproject.toml').read_bytes() != content:
        print('ERROR: pyproject.toml changed during setup. Run the launcher again.')
        return 1
    temporary = marker.with_suffix('.tmp')
    temporary.write_text(digest + '\n', encoding='ascii')
    os.replace(temporary, marker)
    pending.unlink()
    print('[PsyView] Setup completed successfully.', flush=True)
    return 0


def create_environment(root=ROOT):
    root = root.resolve()
    target = root / '.venv'
    if target.exists():
        # Called only after a launcher rejects the existing environment Python.
        # Keep the old environment for recovery; never recursively delete it.
        if target.is_symlink() or target.resolve().parent != root:
            raise ValueError('Refusing to move an environment outside the project root.')
        backup = root / ('.venv.incompatible-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        target.rename(backup)
        print(f'[PsyView] Incompatible environment preserved at {backup}')
    print('[PsyView] Creating local .venv...', flush=True)
    venv.EnvBuilder(with_pip=True).create(target)
    return 0


if __name__ == '__main__':
    try:
        code = create_environment() if '--create' in sys.argv[1:] else setup()
    except Exception as exc:
        print(f'ERROR: {"venv creation" if "--create" in sys.argv else "Setup state/configuration"} failure: {exc}', flush=True)
        code = 1
    if code:
        print('Setup did not complete. The successful hash has not been advanced. PsyView will not be launched.')
        print('Resolve the reported error and run the launcher again. An update may have partially installed packages.')
    raise SystemExit(code)
