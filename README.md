# PDF 简工具

[![CI](https://github.com/xskxsjwjz/pdf-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/xskxsjwjz/pdf-tool/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/xskxsjwjz/pdf-tool)](https://github.com/xskxsjwjz/pdf-tool/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10--3.13-blue.svg)](https://www.python.org/)

[English](README.en.md)

一个简单、离线运行的 Windows PDF 桌面工具。界面使用 Tkinter，PDF 读写基于 `pypdf`，正式版本以单文件 EXE 发布。

## 功能

- 按列表顺序合并多个 PDF
- 删除指定页面
- 提取指定页面到新 PDF
- 旋转指定页面，页码留空时旋转全部
- 拆分为每页一个 PDF
- 从文件或文件夹添加 PDF
- 把 PDF 或包含 PDF 的文件夹直接拖入窗口
- 输出文件落盘前重新读取校验

页码支持 `1,3-5`、`1 3-5` 等写法，页码从 1 开始。

## 下载

请从 [GitHub Releases](https://github.com/xskxsjwjz/pdf-tool/releases/latest) 下载最新的 Windows x64 版本，并使用同一版本提供的 `SHA256SUMS.txt` 校验文件。

当前 EXE 未进行商业代码签名，首次运行时 Windows SmartScreen 可能显示提醒。

## 使用

1. 添加或拖入 PDF 文件，也可以选择一个包含 PDF 的文件夹。
2. 选择操作；合并时可用“上移”“下移”调整顺序。
3. 删页、提取或旋转时，在列表中选中一个 PDF 并填写页码。
4. 选择输出位置，然后点击“开始处理”。

## 直接运行源码

```powershell
python -m pip install -r requirements.txt
python app.py
```

要求 Python 3.10 至 3.13。拖放功能由 `tkinterdnd2` 提供。

## 构建 Windows EXE

```powershell
.\build.ps1
```

脚本会创建项目内的 `.venv`、安装依赖、运行测试，并输出：

```text
dist\PDFTool.exe
```

更详细的开发与提交要求见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 隐私与安全

- 文件全程在本机处理，不会上传网络。
- 当前不处理需要密码才能打开的加密 PDF。
- 输出先写入临时文件并重新读取校验，校验通过后才放到目标位置。
- 为避免破坏源文件，输出路径不能与正在处理的源 PDF 相同。
- 请不要在公开 Issue 中上传隐私 PDF；安全问题请遵循 [SECURITY.md](SECURITY.md)。

## 开源与第三方组件

本项目代码采用 [MIT License](LICENSE)。EXE 内含 Python、Tcl/Tk、pypdf、tkinterdnd2 和 TkDND 等开源组件，其版权和许可证声明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)，也可在应用的“关于与许可”窗口中查看。

## 参与项目

- [问题反馈](https://github.com/xskxsjwjz/pdf-tool/issues)
- [贡献指南](CONTRIBUTING.md)
- [行为准则](CODE_OF_CONDUCT.md)
- [支持说明](SUPPORT.md)
- [版本记录](CHANGELOG.md)
