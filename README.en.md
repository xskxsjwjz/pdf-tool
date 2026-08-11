# PDF Simple Tool

[简体中文](README.md)

A small, offline Windows desktop utility for common PDF page operations. It uses Python, Tkinter, and pypdf, and ships as a single-file executable.

## Features

- Merge PDFs in a chosen order.
- Delete, extract, or rotate selected pages.
- Split a document into one PDF per page.
- Add PDFs through a file picker, a folder picker, or drag and drop.
- Validate output before replacing the destination file.
- Process every file locally without uploading it.

Page expressions use one-based numbers, for example `1,3-5`.

## Download

Download the latest Windows x64 package from [GitHub Releases](https://github.com/xskxsjwjz/pdf-tool/releases/latest). Verify downloads with the accompanying `SHA256SUMS.txt` file.

The executable is currently unsigned, so Windows SmartScreen may show a warning on first launch.

## Run from source

```powershell
python -m pip install -r requirements.txt
python app.py
```

## Build

```powershell
.\build.ps1
```

The build script creates `dist\PDFTool.exe`. See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow.

## Privacy and security

PDFs stay on the local computer. Password-protected PDFs are not currently supported. Do not report security issues publicly; follow [SECURITY.md](SECURITY.md).

## License

Project code is available under the [MIT License](LICENSE). Binary distributions contain third-party open-source components; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
