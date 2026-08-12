# PDF 简工具 2.0

[![CI](https://github.com/xskxsjwjz/pdf-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/xskxsjwjz/pdf-tool/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/xskxsjwjz/pdf-tool)](https://github.com/xskxsjwjz/pdf-tool/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10--3.13-blue.svg)](https://www.python.org/)

[English](README.en.md)

一个面向 Windows 的 PDF 整理与可视编辑工具。2.0 在原有合并、删页、提取、旋转和拆分能力上，新增页面预览、文字批注、自由绘制、手写签名、荧光标记、视觉遮盖与翻译。

## 2.0 功能

- 可视预览并逐页编辑 PDF，支持 75%–200% 缩放
- 点击页面添加单行或多行文字，支持中文
- 画笔自由批注、颜色选择、撤销与重做
- 独立签名板采集手写签名；放置后可拖动位置，并用四角控制点等比例缩放
- 荧光标记与白色视觉遮盖
- 提取当前页文字，通过 LibreTranslate 兼容服务翻译，并把译文放回页面
- 编辑结果另存为新 PDF，写入后会重新读取校验
- 保留 1.x 的合并、删除页面、提取页面、旋转和拆分功能
- 支持添加文件、文件夹以及拖放 PDF

> “遮盖”只是覆盖一个白色图层，不会安全删除底层文字或元数据，请勿把它当作涉密信息脱敏工具。

## 使用

批量整理：添加或拖入 PDF，选择操作、页码与输出位置，然后点击“开始处理”。页码支持 `1,3-5` 等写法。

可视编辑：选中一个 PDF 后点击“可视编辑 / 手写签名”，也可以双击列表中的 PDF。在编辑窗口选择画笔、文字、荧光、遮盖或手写签名工具。签名放置后，拖动签名本体可移动，拖动四角蓝色控制点可等比例缩放；稍后可用“选择/调整”重新选中。完成后点击“另存为 PDF”。所有修改只有另存后才会写入文件，源文件不会被覆盖。

翻译：在编辑器点击“翻译本页”。应用会先在本地提取页面文字，只有点击“开始翻译”后，输入框里的内容才会发送到所配置的 LibreTranslate 兼容服务。服务地址和 API Key 可在窗口内输入，也可使用环境变量：

```powershell
$env:PDFTOOL_TRANSLATE_ENDPOINT = "https://your-service.example/translate"
$env:PDFTOOL_TRANSLATE_API_KEY = "your-key"
python app.py
```

扫描页暂不支持 OCR，但可以手动粘贴文字进行翻译。

## 运行源码

```powershell
python -m pip install -r requirements.txt
python app.py
```

要求 Python 3.10–3.13。PDF 读写使用 `pypdf`，预览使用 `pypdfium2`/PDFium，编辑图层使用 ReportLab，界面预览适配使用 Pillow。

## 测试与构建 Windows EXE

```powershell
python -m unittest discover -s tests -v
.\build.ps1
```

构建结果位于 `dist\PDFTool.exe`。当前 EXE 未进行商业代码签名，首次运行时 Windows SmartScreen 可能显示提醒。

## 隐私与安全

- PDF 整理、预览、编辑与签名都在本机完成。
- 只有用户主动开始在线翻译时，翻译框中的文字才会发送到用户配置的服务；API Key 不写入项目配置文件。
- 暂不支持需要密码才能打开的 PDF。
- 输出先写入临时文件并重新读取校验，成功后才放到目标位置。
- 输出路径不能与正在处理的源 PDF 相同。
- 请勿在公开 Issue 中上传隐私 PDF；安全问题请参阅 [SECURITY.md](SECURITY.md)。

## 开源与参与

项目代码采用 [MIT License](LICENSE)。第三方组件及其许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)，也可在应用的“关于与许可”窗口查看。

- [问题反馈](https://github.com/xskxsjwjz/pdf-tool/issues)
- [贡献指南](CONTRIBUTING.md)
- [行为准则](CODE_OF_CONDUCT.md)
- [版本记录](CHANGELOG.md)
