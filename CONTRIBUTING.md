# Contributing

Thanks for helping improve PDF Simple Tool.

## Before opening an issue

- Search existing issues first.
- Do not attach private or confidential PDF files.
- For security problems, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.

## Development setup

The project supports Python 3.10 through 3.13.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe app.py
```

Install `requirements-qa.txt` only when running the optional visual PDF QA script.

## Pull requests

1. Create a focused branch from `main`.
2. Keep changes small and include tests for behavior changes.
3. Run the complete unit test suite.
4. Update `CHANGELOG.md` when the change is user-visible.
5. Confirm that new dependencies have compatible licenses and add any required notices to `THIRD_PARTY_NOTICES.md`.

By submitting a contribution, you agree that it is licensed under the project's MIT License.
