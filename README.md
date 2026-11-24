# Kindle2Readwise

Kindle2Readwise 是一个基于 Python 3 开发的简单的工具，用于将 Kindle 中的 `My Clippings.txt` 文件转换为可导入 [Readwise](https://readwise.io) 的 CSV 文件, 以解决官方不支持导入中文剪贴文件的问题。

## 功能简介

- 解析 Kindle 的中文 `My Clippings.txt` 文件。
- 去除重复的高亮和笔记，保留最新版本。
- 将高亮文本与笔记一一对应
- 将整理后的内容导出为符合 Readwise 导入格式的 CSV 文件。

## 使用方法

### 1. 准备工作

- 确保您已经从 Kindle 设备中导出了 `My Clippings.txt` 文件。
- 将 `My Clippings.txt` 文件放在与本工具相同的目录下。

### 2. 安装依赖

运行以下命令安装所需的 Python 依赖：

```bash
pip install -r requirements.txt
```

> **注意**：如果您尚未安装 Python，请先从 [Python 官方网站](vscode-file://vscode-app/usr/share/code/resources/app/out/vs/code/electron-sandbox/workbench/workbench.html) 下载并安装。

### 3. 运行工具

在终端中运行以下命令：

```bash
python converter.py
```

默认情况下，程序会读取当前目录下的 `My Clippings.txt` 文件，并生成一个名为 `MyClippings.csv` 的文件。

### 4. 自定义输入和输出文件

如果您的 `My Clippings.txt` 文件或输出文件名不同，可以通过以下方式指定：

```bash
python converter.py --input "您的文件名.txt" --output "输出文件名.csv"
python converter.py --input "/home/user/kindle/My Clippings-2025_05_06.txt" --output "/home/user/kindle/ReadwiseClippings.csv"
# 或者更简洁的写法
python converter.py -i "/home/user/kindle/My Clippings-2025_05_06.txt"  -o "/home/user/kindle/ReadwiseClippings.csv"
```

### 5. 导入到 Readwise

- 打开 [Readwise](https://readwise.io/import_bulk) 网站。
- 上传生成的 CSV 文件即可。

## 注意事项

- 请确保 `My Clippings.txt` 文件的编码为 UTF-8。如果文件包含特殊字符，可能需要手动调整编码。
- 如果程序提示文件未找到，请检查文件名是否正确，并确保文件与程序在同一目录下。

## 示例

以下是一个简单的示例：

1. 将 `My Clippings.txt` 文件放在 `converter.py` 脚本同级目录下。

2. 运行以下命令：

```bash
python converter.py
```

3. 程序会生成一个 `MyClippings.csv` 文件，您可以将其导入到 Readwise。

## 支持

如果您在使用过程中遇到问题，请提交 Issue。