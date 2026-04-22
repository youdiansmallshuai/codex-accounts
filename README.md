# codex-accounts

`codex-accounts` is a terminal tool for saving and switching Codex ChatGPT auth profiles.

中文文档: [README.zh-CN.md](./README.zh-CN.md)

## Features

- Save current `~/.codex/auth.json` as a named profile
- Switch between saved profiles
- List saved profiles and current profile
- Show plan limits reference
- Query live usage (`5h` and weekly) from the backend API

## Storage

- Current auth file: `~/.codex/auth.json`
- Saved profiles: `~/.local/share/codex-accounts/accounts/*.json`

## Commands

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

Profile names must match: `[A-Za-z0-9._-]+`

## Local Development

Run directly from repo:

```bash
./bin/codex-accounts --help
```

Install editable package to user site:

```bash
./scripts/install_local.sh
```

Then:

```bash
codex-accounts --help
```

If your system Python has no `pip`, use symlink mode instead:

```bash
./scripts/link_local_bin.sh
```

## Notes

- `dashboard` and `usage` call `https://chatgpt.com/backend-api/wham/usage` with each profile's access token.
- `dashboard --watch` runs a dynamic refresh loop: active account refreshes every random `1-5` minutes, inactive accounts every random `5-10` minutes.
- Plan limits in output are static references from OpenAI Help Center and may change over time.
