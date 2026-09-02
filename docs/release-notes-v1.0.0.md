# 文桥 Document Bridge 1.0.0

首个正式版本现已发布。文桥可以在 Word、LaTeX 与 Markdown 之间完成六条双向转换路径，提供本地网页、命令行与 HTTP API，并尽量保留文档结构、常见公式、表格、脚注和图片。

## 直接下载

| 系统 | 文件 | 大小 |
|---|---|---:|
| Windows 10/11 x64 | `DocumentBridge-windows-x86_64.zip` | 55.2 MB |
| macOS Apple Silicon | `DocumentBridge-macos-arm64.tar.gz` | 39.6 MB |
| Linux x86_64 | `DocumentBridge-linux-x86_64.tar.gz` | 66.6 MB |

下载页面下方的对应文件并解压：

- Windows：双击 `DocumentBridge.exe`；
- macOS / Linux：运行 `DocumentBridge`；
- 程序会启动本地服务并自动打开浏览器；
- 发布包已包含 Python 运行时与 Pandoc 3.9，无需另装依赖。

> 当前发布包没有商业代码签名。macOS 或 Windows 首次运行时可能显示安全确认提示，详细处理方式见项目 README。

## 主要能力

- Word ↔ LaTeX；
- Word ↔ Markdown；
- LaTeX ↔ Markdown；
- Word 图片自动提取与 ZIP 打包；
- LaTeX / Markdown 完整项目 ZIP；
- 项目主文件自动识别与手动指定；
- 本地优先处理，不上传第三方；
- ZIP 路径穿越、符号链接、解压体积和转换超时保护；
- Windows、macOS、Linux 原生免安装构建。

## 构建与验证

- Python 3.10、3.12、3.14 测试通过；
- 六条转换路径集成测试通过；
- 图片资源提取测试通过；
- LaTeX 项目 ZIP 资源保留测试通过；
- 三个平台的免安装程序均通过启动冒烟测试；
- Linux Release 包已从公开链接重新下载，并实际完成 Markdown → Word 转换验证。

## SHA-256

```text
cc744f0813b02245038cc5f99aacfa7af6bb7d5459d9eb1587307a33b24d882e  DocumentBridge-linux-x86_64.tar.gz
de64f00c0454f2f0248ff9c3c88bc49ab3cf5890df84e612948ee85c2869c67e  DocumentBridge-macos-arm64.tar.gz
73f2e7223a691df7e528ae6011a71aaf9b847db0fb24b7cb46a6869dd81fb0e4  DocumentBridge-windows-x86_64.zip
```

完整安装方法、界面截图、项目 ZIP 规范、保真度说明、CLI/API 示例和 FAQ 请阅读[项目首页](https://github.com/KarlHeinrich-jpg/document-bridge#readme)。
