# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.0.0] - 2026-08-12

### Added

- Visual multi-page PDF editor with zoomed PDFium previews.
- Multiline text, CJK text, freehand ink, highlighting, and visual whiteout overlays.
- In-memory handwritten signature pad with click-to-place, drag-to-move, and proportional corner resizing.
- Undo, redo, per-page clearing, and verified Save As output.
- Current-page text extraction and optional LibreTranslate-compatible translation.

### Changed

- Updated the desktop interface and release dependencies for the 2.0 editing workflow.
- Clarified that translation is the only workflow that may send user-entered text to a configured service.

## [1.0.0] - 2026-08-12

### Added

- Merge multiple PDF files in a user-defined order.
- Delete, extract, and rotate selected pages.
- Split a PDF into one file per page.
- Add inputs using file selection, folder selection, or drag and drop.
- Validate generated PDFs before replacing their destination files.
- Package the app as a single-file Windows executable.

[Unreleased]: https://github.com/xskxsjwjz/pdf-tool/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/xskxsjwjz/pdf-tool/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/xskxsjwjz/pdf-tool/releases/tag/v1.0.0
