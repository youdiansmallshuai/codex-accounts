# codex-accounts

`codex-accounts` 是一个用于保存和切换 Codex ChatGPT 登录配置的终端工具。

## 功能

- 将当前 `~/.codex/auth.json` 保存为命名账号配置
- 在已保存账号之间快速切换
- 查看已保存账号列表和当前账号
- 查看套餐限额参考信息
- 调用后端接口查看实时用量（`5 小时`与`本周`）

## 数据位置

- 当前登录配置文件: `~/.codex/auth.json`
- 已保存账号文件: `~/.local/share/codex-accounts/accounts/*.json`

## 命令

```bash
codex-accounts save <name>
codex-accounts use <name>
codex-accounts list
codex-accounts current
codex-accounts limits [name]
codex-accounts dashboard
codex-accounts dashboard --watch
codex-accounts usage [name]
codex-accounts remove <name>
```

账号名需匹配正则: `[A-Za-z0-9._-]+`

## 本地开发

在仓库中直接运行:

```bash
./bin/codex-accounts --help
```

使用 `pip` 安装为用户级可编辑包:

```bash
./scripts/install_local.sh
```

安装后可直接运行:

```bash
codex-accounts --help
```

如果系统 Python 没有 `pip`，可使用软链接模式:

```bash
./scripts/link_local_bin.sh
```

## 说明

- `dashboard` 和 `usage` 会使用账号内的 access token 调用 `https://chatgpt.com/backend-api/wham/usage`。
- `dashboard --watch` 会实时动态刷新：当前使用账号随机 `1-5` 分钟刷新一次，未使用账号随机 `5-10` 分钟刷新一次。
- 输出中的套餐限额是基于 OpenAI Help Center 的静态参考，后续可能变化。
