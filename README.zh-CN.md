# kuaishou-fill

[English](./README.md) | 简体中文

一个可独立安装的 Agent 技能：把视频帖子填进快手创作者中心的表单，并在**发布前一步停下**。它给 Claude Code、Codex、OpenClaw、ZCode 等 Agent 一个确定性的 CLI，而不是让它们临场摸索浏览器点击。

姊妹项目：[douyin-fill](https://github.com/huiguyy/douyin-fill)。表单流程设计参考 [social-auto-upload](https://github.com/dreammis/social-auto-upload)；"人的节奏"参考 [Easel](https://github.com/ZJU-REAL/Easel)。见 `NOTICE`。

## 为什么只填不发

Agent 负责上传视频与封面、填写所需信息、留存证据，然后让专用 Chrome 窗口保持打开。由人来核对真实表单并决定是否发布。整个流程**没有提交开关、没有隐藏的发布路径、没有发布重试、没有登录自动化，也不处理验证码**。

快手的标题与描述共用同一个编辑器，所以这两项是一起填的，不会假装存在一个独立的标题输入框。

## 安装

需要 Python 3.10+、Chrome/Chromium，以及一个**已登录快手创作者中心**的独立 Chrome 配置。

```bash
npx skills add huiguyy/kuaishou-fill
```

或者克隆本仓库，把目录复制 / 软链到 `~/.agents/skills/kuaishou-fill`（或你的 Agent 等价技能目录）。在技能目录内：

```bash
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
```

运行依赖已精确锁定。CLI 的 `--help` 在未安装 Playwright 时也能运行，Agent 可以先安全地查看契约。

## 使用

```bash
python3 scripts/kuaishou_fill.py \
  --video /absolute/video.mp4 \
  --cover /absolute/cover.jpg \
  --title "已审核的标题" \
  --desc "已审核的描述" \
  --tags "标签一,标签二" \
  --chrome-profile /absolute/dedicated-chrome-profile \
  --fill-only
```

可选参数：

- `--storage-state /private/storage-state.json`：导入既有 Playwright 登录态，不会打印出来。
- `--cdp-url http://127.0.0.1:PORT`：附加到既有专用 Chrome；只接受回环地址。
- `--schedule "YYYY-MM-DD HH:MM"`：仅在明确要求时填写未来的定时发布。
- `--headless`：抓取一次性证据后关闭 Chrome 并跳过重复历史；人工复核需再用有头模式跑一遍。
- `--chrome-path`、`--evidence-dir`、`--history-file`、`--timeout`：受控的运行时覆盖。

视频必须是 faststart MP4（`moov` 位于首个 `mdat` 之前）。校验在打开 Chrome 之前完成，且不会改写源文件。**最多接受 3 个标签**。

## 结果

stdout 只输出一个 JSON 对象；日志走 stderr。成功结果包含 `ok:true`、`filled:true`、核对过的 `evidence.fields`、本地截图，以及 `submit:"left_to_human"`。有头运行报告 `browser.left_open:true`；一次性无头运行报告 `left_open:false` 与 `history_recorded:false`。

同一视频在快手重复提交会返回 `skipped:true, reason:"already_filled"`，不会打开 Chrome。这是一个只基于平台与视频 SHA-256 的本地小防重。

安全、隐私、错误与证据语义见 [fill-only 契约](docs/fill-only.md)。

## 验证

```bash
sh tools/run_checks.sh
python3 -m unittest discover -s tests -v
```

检查项包括：编译、隔离 CLI help、媒体 atom 解析、去重行为、输入输出契约、依赖精确锁定、红线扫描、（如适用）内置核心一致性，以及**证明"只填不发"闸门在危险实现下会失败的变异测试**。真实平台的可用性与选择器兼容性仍需用单独授权的测试账号验证；验证过程不含任何发布动作。

## 许可

本项目为 MIT。第三方声明以及 SAU 的 MIT / Easel 的 Apache-2.0 文本见 `licenses/`。本项目与快手无隶属关系。
