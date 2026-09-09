# Launcher verification

The build backend was inspected: `setuptools.build_meta`, with declared
`setuptools>=75`. No wheel requirement is declared. Setup installs the actual
`build-system.requires` list before using editable `--no-build-isolation`.

| Case | Verification |
| --- | --- |
| No `.venv` | Unit test of creation; BAT searches compatible Python before calling creation. |
| Valid `.venv`, unchanged TOML | Actual BAT launch with `PIP_NO_INDEX=1`; no pip output or installation. Unit test forbids every subprocess in the unchanged helper path. |
| Valid `.venv`, changed TOML | Unit test verifies changed content triggers install and a new SHA-256 marker. |
| Incompatible `.venv` | Unit test verifies preservation in timestamped backup and creation of replacement. BAT version gate inspected. |
| No Python installed | Discovery branches inspected: all three commands absent leads to the explicit missing-Python message; not simulated by removing host Python. |
| Python 3.11 only | Version predicates inspected: `(3,11) < (3,12)` rejects every candidate and reports outdated Python; no 3.11 interpreter installed for runtime testing. |
| Python 3.12+ | Actual Python 3.13.5 reused successfully; 3.12 accepted by the same predicate but not installed locally. |
| Installation network failure | Unit test injects ConnectionResetError and verifies network/PyPI diagnosis; actual index-disabled setup fails clearly on missing setuptools without writing a success marker. |
| Successful initial setup | Actual setup completed in the existing compatible venv with no prior marker, installed build tools/project, passed pip check/imports, and wrote the hash. Fresh environment creation tested separately. |
| Second launch offline | Actual BAT `--help` and full interactive TUI both launched with package-index access disabled; unchanged message and no installation output. |

Eight focused tests pass (`python -m pytest tests/test_launcher.py -q`).
The existing healthy environment was retained. No scientific files changed.
Failed updates preserve the previous successful hash and leave a pending marker,
so a subsequent launch cannot mistake a partially updated environment for a
completed installation, even if the TOML is later reverted.

Normal startup does not run pip, including pip's version/network checks.
Actual setup output is stored in `.venv/.psyview_setup.log`. Missing Python,
old Python, venv creation, build installation, project installation, recognized
network failures, import failures and application runtime failures have separate
messages. Failed setup stops; it does not offer an unsafe partial-update fallback.
