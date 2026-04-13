import argparse
import base64
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


CODEX_DIR = Path.home() / ".codex"
AUTH_FILE = CODEX_DIR / "auth.json"
ACCOUNTS_DIR = Path.home() / ".local" / "share" / "codex-accounts" / "accounts"
LIMITS_DOC_URL = "https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan"
USAGE_API_URL = "https://chatgpt.com/backend-api/wham/usage"

# Official Help Center guidance accessed on 2026-04-11.
PLAN_LIMITS = {
    "plus": {
        "local_5h": "45-225 local messages / 5h",
        "cloud_5h": "10-60 cloud tasks / 5h",
        "weekly": "shared weekly limit exists, exact numeric cap not publicly specified",
        "mini_note": "GPT-5-Codex-Mini: about 4x more local message capacity",
    },
    "pro": {
        "local_5h": "300-1,500 local messages / 5h",
        "cloud_5h": "50-400 cloud tasks / 5h",
        "weekly": "shared weekly limit exists, exact numeric cap not publicly specified",
        "mini_note": "GPT-5-Codex-Mini: about 4x more local message capacity",
    },
    "business": {
        "local_5h": "same included per-seat limits as Plus",
        "cloud_5h": "same included per-seat limits as Plus",
        "weekly": "shared weekly limit exists, exact numeric cap not publicly specified",
        "mini_note": "flexible pricing can add paid usage beyond included limits",
    },
    "enterprise": {
        "local_5h": "not published as a fixed per-user number",
        "cloud_5h": "usage can draw from workspace shared credit pool",
        "weekly": "not published as a fixed per-user number",
        "mini_note": "depends on workspace flexible pricing / shared credits",
    },
    "edu": {
        "local_5h": "not published as a fixed per-user number",
        "cloud_5h": "usage can draw from workspace shared credit pool",
        "weekly": "not published as a fixed per-user number",
        "mini_note": "depends on workspace flexible pricing / shared credits",
    },
}


def ensure_accounts_dir() -> None:
    ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)


def die(message: str, code: int = 1) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def load_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text())
        if not isinstance(payload, dict):
            die(f"json root is not an object: {path}")
        return payload
    except FileNotFoundError:
        die(f"missing file: {path}")
    except json.JSONDecodeError as exc:
        die(f"invalid json in {path}: {exc}")


def save_copy(src: Path, dst: Path) -> None:
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)


def decode_jwt_payload(token: str) -> dict:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
        parsed = json.loads(decoded.decode("utf-8"))
        if isinstance(parsed, dict):
            return parsed
        return {}
    except Exception:
        return {}


def parse_auth_metadata(auth: dict) -> dict:
    tokens = auth.get("tokens") or {}
    id_payload = decode_jwt_payload(tokens.get("id_token", ""))
    access_payload = decode_jwt_payload(tokens.get("access_token", ""))
    auth_claims = id_payload.get("https://api.openai.com/auth", {})
    profile_claims = access_payload.get("https://api.openai.com/profile", {})

    return {
        "email": id_payload.get("email") or profile_claims.get("email") or "-",
        "name": id_payload.get("name") or "-",
        "plan": auth_claims.get("chatgpt_plan_type") or "-",
        "account_id": tokens.get("account_id") or auth_claims.get("chatgpt_account_id") or "-",
        "auth_mode": auth.get("auth_mode") or "-",
        "expires_at": id_payload.get("exp"),
        "last_refresh": auth.get("last_refresh") or "-",
    }


def fetch_live_usage(auth: dict) -> dict:
    tokens = auth.get("tokens") or {}
    access_token = tokens.get("access_token")
    if not access_token:
        die("missing access_token in auth data")

    req = urllib.request.Request(
        USAGE_API_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if isinstance(payload, dict):
                return payload
            die("usage api returned non-object json")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        die(f"usage api returned HTTP {exc.code}: {body[:300]}")
    except urllib.error.URLError as exc:
        die(f"usage api request failed: {exc}")


def format_ts(value) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.fromtimestamp(int(value), tz=timezone.utc).astimezone()
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception:
        return str(value)


def format_duration(seconds) -> str:
    try:
        seconds = int(seconds)
    except Exception:
        return "-"

    if seconds < 0:
        seconds = 0

    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes or not parts:
        parts.append(f"{minutes}m")
    return " ".join(parts)


def progress_bar(percent, width: int = 18) -> str:
    try:
        percent = max(0, min(100, int(percent)))
    except Exception:
        return "[" + ("-" * width) + "]"
    filled = round(width * percent / 100)
    return "[" + ("#" * filled) + ("-" * (width - filled)) + "]"


def sanitize_name(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
        die("account name must match [A-Za-z0-9._-]+")
    return name


def account_file(name: str) -> Path:
    return ACCOUNTS_DIR / f"{sanitize_name(name)}.json"


def current_account_id() -> str:
    if not AUTH_FILE.exists():
        return ""
    return parse_auth_metadata(load_json(AUTH_FILE)).get("account_id", "")


def plan_limits(plan: str):
    return PLAN_LIMITS.get((plan or "").strip().lower())


def print_limits_block(plan: str, prefix: str = "") -> None:
    limits = plan_limits(plan)
    if not limits:
        print(f"{prefix}5h local: unavailable for plan={plan}")
        print(f"{prefix}5h cloud: unavailable for plan={plan}")
        print(f"{prefix}weekly:   exact limit not available locally")
        print(f"{prefix}source:   {LIMITS_DOC_URL}")
        return

    print(f"{prefix}5h local: {limits['local_5h']}")
    print(f"{prefix}5h cloud: {limits['cloud_5h']}")
    print(f"{prefix}weekly:   {limits['weekly']}")
    print(f"{prefix}note:     {limits['mini_note']}")
    print(f"{prefix}source:   {LIMITS_DOC_URL}")


def print_live_usage_block(usage: dict, prefix: str = "") -> None:
    rl = usage.get("rate_limit") or {}
    primary = rl.get("primary_window") or {}
    secondary = rl.get("secondary_window") or {}
    p1 = primary.get("used_percent", "-")
    p2 = secondary.get("used_percent", "-")

    print(f"{prefix}5小时  {progress_bar(p1)} {p1}%")
    print(
        f"{prefix}重置于  {format_ts(primary.get('reset_at'))}  "
        f"剩余 {format_duration(primary.get('reset_after_seconds'))}"
    )
    print(f"{prefix}本周    {progress_bar(p2)} {p2}%")
    print(
        f"{prefix}重置于  {format_ts(secondary.get('reset_at'))}  "
        f"剩余 {format_duration(secondary.get('reset_after_seconds'))}"
    )


def cmd_save(args: argparse.Namespace) -> None:
    ensure_accounts_dir()
    if not AUTH_FILE.exists():
        die(f"current auth file not found: {AUTH_FILE}")
    dst = account_file(args.name)
    save_copy(AUTH_FILE, dst)
    meta = parse_auth_metadata(load_json(dst))
    print(f"已保存账号: {args.name}")
    print(f"邮箱: {meta['email']}")


def cmd_use(args: argparse.Namespace) -> None:
    src = account_file(args.name)
    if not src.exists():
        die(f"saved account not found: {args.name}")
    save_copy(src, AUTH_FILE)
    meta = parse_auth_metadata(load_json(AUTH_FILE))
    print(f"已切换到: {args.name}")
    print(f"邮箱: {meta['email']}")
    print("请新开一个 codex 会话再使用，避免旧会话沿用之前的登录态")


def cmd_list(_: argparse.Namespace) -> None:
    ensure_accounts_dir()
    files = sorted(ACCOUNTS_DIR.glob("*.json"))
    if not files:
        print("还没有保存的账号")
        print("先执行: codex-accounts save <名字>")
        return

    live_account_id = current_account_id()
    print("已保存账号")
    for path in files:
        meta = parse_auth_metadata(load_json(path))
        marker = "*" if meta["account_id"] == live_account_id and live_account_id else " "
        print(f"{marker} {path.stem:16} {meta['email']}")


def cmd_current(_: argparse.Namespace) -> None:
    if not AUTH_FILE.exists():
        die(f"current auth file not found: {AUTH_FILE}")
    meta = parse_auth_metadata(load_json(AUTH_FILE))
    print("当前账号")
    print(f"邮箱: {meta['email']}")
    print(f"套餐: {meta['plan']}")
    print(f"登录过期: {format_ts(meta['expires_at'])}")


def cmd_limits(args: argparse.Namespace) -> None:
    if args.name:
        path = account_file(args.name)
        if not path.exists():
            die(f"saved account not found: {args.name}")
        meta = parse_auth_metadata(load_json(path))
        print(f"套餐限额参考: {args.name}")
    else:
        if not AUTH_FILE.exists():
            die(f"current auth file not found: {AUTH_FILE}")
        meta = parse_auth_metadata(load_json(AUTH_FILE))
        print("当前账号套餐限额参考")

    print(f"邮箱: {meta['email']}")
    print(f"套餐: {meta['plan']}")
    print("")
    print_limits_block(meta["plan"])


def cmd_dashboard(_: argparse.Namespace) -> None:
    ensure_accounts_dir()
    files = sorted(ACCOUNTS_DIR.glob("*.json"))
    if not files:
        print("还没有保存的账号")
        print("先执行: codex-accounts save <名字>")
        return

    live_account_id = current_account_id()
    print("账号用量面板")
    print("")
    for path in files:
        auth = load_json(path)
        meta = parse_auth_metadata(auth)
        marker = "*" if meta["account_id"] == live_account_id and live_account_id else " "
        print(f"{marker} {path.stem}")
        print(f"  邮箱    {meta['email']}")
        try:
            usage = fetch_live_usage(auth)
            print_live_usage_block(usage, prefix="  ")
        except SystemExit as exc:
            code = exc.code if hasattr(exc, "code") else exc
            print(f"  用量    获取失败 ({code})")
        print("")


def cmd_usage(args: argparse.Namespace) -> None:
    if args.name:
        path = account_file(args.name)
        if not path.exists():
            die(f"saved account not found: {args.name}")
        auth = load_json(path)
        meta = parse_auth_metadata(auth)
        print(f"账号实时用量: {args.name}")
    else:
        if not AUTH_FILE.exists():
            die(f"current auth file not found: {AUTH_FILE}")
        auth = load_json(AUTH_FILE)
        meta = parse_auth_metadata(auth)
        print("当前账号实时用量")

    usage = fetch_live_usage(auth)
    print(f"邮箱: {meta['email']}")
    print("")
    print_live_usage_block(usage)


def cmd_remove(args: argparse.Namespace) -> None:
    path = account_file(args.name)
    if not path.exists():
        die(f"saved account not found: {args.name}")
    path.unlink()
    print(f"已删除账号: {args.name}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codex-accounts",
        description=(
            "Codex 多账号切换工具\n\n"
            "常用命令:\n"
            "  codex-accounts save <名字>      保存当前登录账号\n"
            "  codex-accounts use <名字>       切换到已保存账号\n"
            "  codex-accounts dashboard        查看所有账号的实时 5 小时/周用量\n"
            "  codex-accounts usage [名字]     查看单个账号的实时用量\n"
            "  codex-accounts list             列出已保存账号\n"
            "  codex-accounts remove <名字>    删除已保存账号\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    save = sub.add_parser("save", help="保存当前登录账号")
    save.add_argument("name")
    save.set_defaults(func=cmd_save)

    use = sub.add_parser("use", help="切换到已保存账号")
    use.add_argument("name")
    use.set_defaults(func=cmd_use)

    list_cmd = sub.add_parser("list", help="列出已保存账号")
    list_cmd.set_defaults(func=cmd_list)

    current = sub.add_parser("current", help="查看当前登录账号")
    current.set_defaults(func=cmd_current)

    limits = sub.add_parser("limits", help="查看套餐限额参考")
    limits.add_argument("name", nargs="?")
    limits.set_defaults(func=cmd_limits)

    dashboard = sub.add_parser("dashboard", help="查看所有账号的实时用量面板")
    dashboard.set_defaults(func=cmd_dashboard)

    usage = sub.add_parser("usage", help="查看单个账号的实时 5 小时/周用量")
    usage.add_argument("name", nargs="?")
    usage.set_defaults(func=cmd_usage)

    remove = sub.add_parser("remove", help="删除已保存账号")
    remove.add_argument("name")
    remove.set_defaults(func=cmd_remove)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
