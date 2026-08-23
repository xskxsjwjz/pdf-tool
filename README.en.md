# PDF Simple Tool 2.1

[简体中文](README.md)

A Windows desktop app for organizing and visually editing PDFs. Version 2.1 adds image-to-PDF conversion for JPG, PNG, BMP, GIF, TIFF, and WebP alongside the existing PDF workflows.

## Features

- Preview and edit every page at 75%–200% zoom
- Add multiline text, including CJK text
- Draw freehand annotations and choose colors
- Capture a signature in an in-memory pad, then drag it to move and use four corner handles to resize it proportionally
- Highlight or visually cover an area
- Undo, redo, clear a page, and save to a validated new PDF
- Extract current-page text, translate through a LibreTranslate-compatible endpoint, and place the translation back on the page
- Merge, delete, extract, rotate, and split pages
- Add files and folders or drag PDFs into the app

> Whiteout is a visual overlay. It does not securely remove underlying text or metadata and must not be used for confidential redaction.

## Run from source

```powershell
python -m pip install -r requirements.txt
python app.py
```

Python 3.10–3.13 is supported.

## Translation and privacy

PDF organization, rendering, editing, and signing remain local. Text is sent over the network only after the user clicks **Translate**, and only to the configured LibreTranslate-compatible service. The endpoint and optional API key can be entered in the dialog or provided through `PDFTOOL_TRANSLATE_ENDPOINT` and `PDFTOOL_TRANSLATE_API_KEY`. Scanned pages currently require manual text entry because OCR is not included.

## Test and build

```powershell
python -m unittest discover -s tests -v
.\build.ps1
```

The single-file Windows build is written to `dist\PDFTool.exe`.

The project is licensed under the [MIT License](LICENSE). See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for bundled components and [CHANGELOG.md](CHANGELOG.md) for release history.
