# Contributing to dep-guard

Issues and pull requests are welcome!

## Reporting Issues
- **Bugs / crashes:** Open a [Bug Report](.github/ISSUE_TEMPLATE/bug_report.md) with the command and output.
- **False positives / policy updates:** Open a [False Positive / Policy Request](.github/ISSUE_TEMPLATE/false_positive.md).

## Submitting a Pull Request
1. Fork the repository and create a feature branch from `main`.
2. Make your changes (keep `bin/dep-guard` Python 3 stdlib-only — no third-party Python dependencies).
3. Add or update unit tests in `tests/test_dep_guard.py`.
4. Verify locally before opening a PR:
   ```bash
   python3 -m unittest -v tests/test_dep_guard.py
   ./bin/dep-guard .
   ```
