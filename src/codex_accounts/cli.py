import argparse
import base64
import json
import os
import random
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
CODEX_DIR = Path.home() / ".codex"
AUTH_FILE = CODEX_DIR / "auth.json"
ACCOUNTS_DIR = Path.home() / ".local" / "share" / "codex-accounts" / "accounts"
LIMITS_DOC_URL = "https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan"
USAGE_API_URL = "https://chatgpt.com/backend-api/wham/usage"
EPD_WIDTH = 400
EPD_HEIGHT = 300
EPD_BIT_BYTES = (EPD_WIDTH * EPD_HEIGHT) >> 3
THEME = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "cyan": "\033[36m",
    "blue": "\033[34m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "gray": "\033[90m",
}

FONT_5X7 = {
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "%": ("11001", "11010", "00100", "01000", "10110", "00110", "00000"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    "/": ("00001", "00010", "00100", "01000", "10000", "00000", "00000"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    "@": ("01110", "10001", "10111", "10101", "10111", "10000", "01110"),
    "_": ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
    "?": ("01110", "10001", "00001", "00010", "00100", "00000", "00100"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01110"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00001", "00001", "00001", "00001", "10001", "10001", "01110"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
}

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


def format_short_duration(seconds) -> str:
    try:
        seconds = max(0, int(seconds))
    except Exception:
        return "-"

    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days:
        return f"{days}d{hours}h"
    if hours:
        return f"{hours}h{minutes}m"
    return f"{minutes}m"


def visible_len(value: str) -> int:
    return len(ANSI_RE.sub("", value))


def color(text: str, name: str) -> str:
    if not sys.stdout.isatty() or os.getenv("NO_COLOR"):
        return text
    return f"{THEME[name]}{text}{THEME['reset']}"


def trim_text(value: str, width: int) -> str:
    if width <= 0:
        return ""
    value = str(value)
    if len(value) <= width:
        return value
    if width == 1:
        return "…"
    return value[: width - 1] + "…"


def fit_line(left: str, right: str, width: int) -> str:
    gap = width - visible_len(left) - visible_len(right)
    if gap < 1:
        return trim_text(left, max(0, width - visible_len(right) - 1)) + " " + right
    return left + (" " * gap) + right


def percent_int(value) -> int | None:
    try:
        return max(0, min(100, int(value)))
    except Exception:
        return None


def percent_color(percent: int | None) -> str:
    if percent is None:
        return "gray"
    if percent >= 85:
        return "red"
    if percent >= 65:
        return "yellow"
    return "green"


def compact_progress(percent, width: int) -> str:
    percent = percent_int(percent)
    if percent is None:
        return color("?" * width, "gray")
    filled = round(width * percent / 100)
    bar = ("█" * filled) + ("░" * (width - filled))
    return color(bar, percent_color(percent))


def format_clock(value) -> str:
    if not value:
        return "-"
    try:
        return datetime.fromtimestamp(int(value)).astimezone().strftime("%H:%M")
    except Exception:
        return "-"


def text_pixel_width(value: str, scale: int = 2, spacing: int = 1) -> int:
    if not value:
        return 0
    return len(value) * (5 * scale + spacing) - spacing


def trim_for_pixels(value: str, max_width: int, scale: int = 2, spacing: int = 1) -> str:
    value = str(value).upper()
    if text_pixel_width(value, scale, spacing) <= max_width:
        return value
    suffix = "."
    while value and text_pixel_width(value + suffix, scale, spacing) > max_width:
        value = value[:-1]
    return value + suffix if value else suffix


class EpdCanvas:
    WHITE = 0
    BLACK = 1
    RED = 2

    def __init__(self, width: int = EPD_WIDTH, height: int = EPD_HEIGHT) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray([self.WHITE]) * (width * height)

    def rect(self, x: int, y: int, w: int, h: int, color_id: int) -> None:
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.width, x + w)
        y1 = min(self.height, y + h)
        for yy in range(y0, y1):
            offset = yy * self.width
            self.pixels[offset + x0 : offset + x1] = bytes([color_id]) * (x1 - x0)

    def border(self, x: int, y: int, w: int, h: int, color_id: int) -> None:
        self.rect(x, y, w, 1, color_id)
        self.rect(x, y + h - 1, w, 1, color_id)
        self.rect(x, y, 1, h, color_id)
        self.rect(x + w - 1, y, 1, h, color_id)

    def text(self, x: int, y: int, value: str, color_id: int, scale: int = 2, spacing: int = 1) -> None:
        cx = x
        for ch in str(value).upper():
            glyph = FONT_5X7.get(ch, FONT_5X7["?"])
            for row, bits in enumerate(glyph):
                for col, bit in enumerate(bits):
                    if bit == "1":
                        self.rect(cx + col * scale, y + row * scale, scale, scale, color_id)
            cx += 5 * scale + spacing

    def pack(self) -> bytes:
        black = bytearray([0xFF]) * EPD_BIT_BYTES
        red = bytearray([0xFF]) * EPD_BIT_BYTES
        for idx, color_id in enumerate(self.pixels):
            if color_id == self.WHITE:
                continue
            byte_i = idx >> 3
            bit = 7 - (idx & 7)
            mask = (~(1 << bit)) & 0xFF
            if color_id == self.BLACK:
                black[byte_i] &= mask
            elif color_id == self.RED:
                red[byte_i] &= mask
        return bytes(black + red)


def push_epd_payload(epd_url: str, payload: bytes) -> tuple[bool, str]:
    url = epd_url.rstrip("/") + "/push"
    boundary = "----codexaccounts"
    head = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="image.bin"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("ascii")
    tail = f"\r\n--{boundary}--\r\n".encode("ascii")
    body = head + payload + tail
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            text = response.read().decode("utf-8", "replace").strip()
            return 200 <= response.status < 300, f"HTTP {response.status} {text}"
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", "replace").strip()
        return False, f"HTTP {exc.code} {text}"
    except urllib.error.URLError as exc:
        return False, str(exc)


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


def safe_fetch_live_usage(auth: dict) -> tuple[dict | None, str | None]:
    try:
        return fetch_live_usage(auth), None
    except SystemExit as exc:
        code = exc.code if hasattr(exc, "code") else exc
        return None, f"获取失败 ({code})"


def render_dashboard_once(paths: list[Path], live_account_id: str) -> None:
    print("账号用量面板")
    print("")
    for path in paths:
        auth = load_json(path)
        meta = parse_auth_metadata(auth)
        marker = "*" if meta["account_id"] == live_account_id and live_account_id else " "
        print(f"{marker} {path.stem}")
        print(f"  邮箱    {meta['email']}")
        usage, error = safe_fetch_live_usage(auth)
        if usage is not None:
            print_live_usage_block(usage, prefix="  ")
        else:
            print(f"  用量    {error}")
        print("")


def pick_refresh_seconds(is_live: bool) -> int:
    if is_live:
        return random.randint(1, 5) * 60
    return random.randint(5, 10) * 60


def usage_window(usage: dict | None, key: str) -> dict:
    if not usage:
        return {}
    rate_limit = usage.get("rate_limit") or {}
    return rate_limit.get(key) or {}


def render_usage_pair(usage: dict | None, width: int) -> str:
    primary = usage_window(usage, "primary_window")
    secondary = usage_window(usage, "secondary_window")
    p5h = percent_int(primary.get("used_percent"))
    pweek = percent_int(secondary.get("used_percent"))
    bar_width = 8 if width < 70 else 10
    left = (
        f"5h {compact_progress(p5h, bar_width)} "
        f"{p5h if p5h is not None else '-':>3}% "
        f"{format_short_duration(primary.get('reset_after_seconds'))}"
    )
    right = (
        f"W {compact_progress(pweek, bar_width)} "
        f"{pweek if pweek is not None else '-':>3}% "
        f"{format_short_duration(secondary.get('reset_after_seconds'))}"
    )
    return fit_line(left, right, width)


def sorted_dashboard_rows(
    rows: list[tuple[Path, dict, dict]], live_account_id: str
) -> list[tuple[Path, dict, dict]]:
    def is_live_row(row: tuple[Path, dict, dict]) -> bool:
        return bool(live_account_id and row[2]["account_id"] == live_account_id)

    return sorted(rows, key=lambda row: (not is_live_row(row), row[0].stem))


def draw_epd_progress(
    canvas: EpdCanvas,
    x: int,
    y: int,
    w: int,
    h: int,
    percent: int | None,
    fill_color: int = EpdCanvas.BLACK,
) -> None:
    canvas.border(x, y, w, h, EpdCanvas.BLACK)
    if percent is None:
        canvas.text(x + 3, y + 2, "?", EpdCanvas.RED, scale=1)
        return
    fill = max(0, min(w - 2, round((w - 2) * percent / 100)))
    if percent >= 85:
        fill_color = EpdCanvas.RED
    if fill:
        canvas.rect(x + 1, y + 1, fill, h - 2, fill_color)


def usage_percentages(usage: dict | None) -> tuple[int | None, int | None, dict, dict]:
    primary = usage_window(usage, "primary_window")
    secondary = usage_window(usage, "secondary_window")
    return (
        percent_int(primary.get("used_percent")),
        percent_int(secondary.get("used_percent")),
        primary,
        secondary,
    )


def draw_metric(
    canvas: EpdCanvas,
    x: int,
    y: int,
    label: str,
    percent: int | None,
    remaining,
    accent_color: int,
    width: int = 220,
) -> None:
    canvas.text(x, y + 3, label, accent_color, scale=2)
    draw_epd_progress(canvas, x + 40, y + 2, width, 17, percent, accent_color)
    percent_text = f"{percent if percent is not None else '-'}%"
    canvas.text(x + width + 52, y + 1, percent_text, accent_color, scale=2)
    canvas.text(x + width + 100, y + 6, format_short_duration(remaining), EpdCanvas.BLACK, scale=1)


def draw_small_metric(
    canvas: EpdCanvas,
    x: int,
    y: int,
    label: str,
    percent: int | None,
    accent_color: int,
) -> None:
    canvas.text(x, y + 3, label, accent_color, scale=1)
    draw_epd_progress(canvas, x + 18, y + 1, 95, 11, percent, accent_color)
    canvas.text(x + 118, y + 3, f"{percent if percent is not None else '-'}%", accent_color, scale=1)


def draw_active_epd_card(
    canvas: EpdCanvas,
    path: Path,
    meta: dict,
    item: dict,
    now: float,
) -> None:
    x, y, w, h = 10, 48, 380, 118
    canvas.border(x, y, w, h, EpdCanvas.BLACK)
    canvas.rect(x, y, 8, h, EpdCanvas.RED)
    canvas.rect(x + 12, y + 10, 54, 17, EpdCanvas.RED)
    canvas.text(x + 18, y + 15, "ACTIVE", EpdCanvas.WHITE, scale=1)

    name = trim_for_pixels(path.stem, 205, scale=3)
    canvas.text(x + 76, y + 9, name, EpdCanvas.BLACK, scale=3)
    canvas.text(x + 300, y + 13, "NEXT", EpdCanvas.BLACK, scale=1)
    canvas.text(x + 334, y + 13, format_short_duration(int(item["next_refresh_at"] - now)), EpdCanvas.RED, scale=1)

    email = trim_for_pixels(meta["email"], 250, scale=1)
    canvas.text(x + 20, y + 39, email, EpdCanvas.BLACK, scale=1)
    canvas.text(x + 300, y + 39, "UPD " + format_clock(item["last_updated_at"]), EpdCanvas.BLACK, scale=1)

    if item["usage"] is None:
        canvas.text(x + 20, y + 70, trim_for_pixels(item["error"], 330, scale=2), EpdCanvas.RED, scale=2)
        return

    p5h, pweek, primary, secondary = usage_percentages(item["usage"])
    draw_metric(canvas, x + 20, y + 62, "5H", p5h, primary.get("reset_after_seconds"), EpdCanvas.BLACK)
    draw_metric(canvas, x + 20, y + 91, "WK", pweek, secondary.get("reset_after_seconds"), EpdCanvas.RED)


def draw_compact_epd_card(
    canvas: EpdCanvas,
    path: Path,
    meta: dict,
    item: dict,
    y: int,
    now: float,
    is_live: bool,
) -> None:
    x, w, h = 10, 380, 50
    canvas.border(x, y, w, h, EpdCanvas.RED if is_live else EpdCanvas.BLACK)
    canvas.rect(x, y, 5, h, EpdCanvas.RED if is_live else EpdCanvas.BLACK)
    chip = "ACT" if is_live else "IDLE"
    canvas.text(x + 14, y + 8, chip, EpdCanvas.RED if is_live else EpdCanvas.BLACK, scale=1)
    name = trim_for_pixels(path.stem, 170, scale=2)
    canvas.text(x + 58, y + 5, name, EpdCanvas.RED if is_live else EpdCanvas.BLACK, scale=2)
    canvas.text(x + 292, y + 8, "N " + format_short_duration(int(item["next_refresh_at"] - now)), EpdCanvas.BLACK, scale=1)

    if item["usage"] is None:
        canvas.text(x + 58, y + 30, trim_for_pixels(item["error"], 260, scale=1), EpdCanvas.RED, scale=1)
        return

    p5h, pweek, _, _ = usage_percentages(item["usage"])
    draw_small_metric(canvas, x + 20, y + 29, "5H", p5h, EpdCanvas.BLACK)
    draw_small_metric(canvas, x + 204, y + 29, "WK", pweek, EpdCanvas.RED)


def build_epd_dashboard_payload(
    rows: list[tuple[Path, dict, dict]],
    state: dict[str, dict],
    live_account_id: str,
    epd_status: dict | None = None,
) -> bytes:
    canvas = EpdCanvas()
    now = time.time()
    canvas.rect(0, 0, EPD_WIDTH, EPD_HEIGHT, EpdCanvas.WHITE)
    canvas.rect(0, 0, EPD_WIDTH, 38, EpdCanvas.RED)
    canvas.text(14, 10, "CODEX WATCH", EpdCanvas.WHITE, scale=3)
    canvas.text(292, 12, datetime.now().strftime("%H:%M"), EpdCanvas.WHITE, scale=2)
    canvas.rect(0, 38, EPD_WIDTH, 2, EpdCanvas.BLACK)

    visible_rows = sorted_dashboard_rows(rows, live_account_id)[:3]
    if visible_rows:
        path, _, meta = visible_rows[0]
        item = state[path.stem]
        draw_active_epd_card(canvas, path, meta, item, now)

    for idx, (path, _, meta) in enumerate(visible_rows[1:3]):
        item = state[path.stem]
        is_live = bool(live_account_id and meta["account_id"] == live_account_id)
        draw_compact_epd_card(canvas, path, meta, item, 176 + (idx * 55), now, is_live)

    if epd_status:
        status_text = epd_status.get("message") or "EPD READY"
        status_color = EpdCanvas.BLACK if epd_status.get("ok", True) else EpdCanvas.RED
        canvas.text(10, 286, trim_for_pixels(status_text, 330, scale=1), status_color, scale=1)

    return canvas.pack()


def render_watch_panel(
    rows: list[tuple[Path, dict, dict]],
    state: dict[str, dict],
    live_account_id: str,
    epd_status: dict | None = None,
) -> None:
    terminal = shutil.get_terminal_size((80, 24))
    width = max(36, min(terminal.columns, 96))
    now = time.time()
    ordered_rows = sorted_dashboard_rows(rows, live_account_id)
    max_visible = min(len(ordered_rows), max(3, (terminal.lines - 4) // 3))
    visible_rows = ordered_rows[:max_visible]

    print("\033[2J\033[H", end="")
    title = color("Codex Accounts Live", "bold")
    count = color(str(len(rows)), "cyan")
    print(fit_line(title, f"{count} accounts", width))
    print(color("─" * width, "gray"))
    epd_note = ""
    if epd_status:
        epd_note = "EPD OK" if epd_status.get("ok") else "EPD ERR"
    print(fit_line("active 1-5m · idle 5-10m · Ctrl+C exit", epd_note, width))

    for path, _, meta in visible_rows:
        item = state[path.stem]
        is_live = bool(live_account_id and meta["account_id"] == live_account_id)
        status = color("ACTIVE", "green") if is_live else color("idle  ", "gray")
        dot = color("●", "green" if is_live else "blue")
        name_width = 18 if width >= 70 else 12
        name = trim_text(path.stem, name_width)
        next_in = format_short_duration(int(item["next_refresh_at"] - now))
        line1 = f"{dot} {status} {color(name, 'cyan' if is_live else 'blue')}"
        print(fit_line(line1, f"next {next_in}", width))

        email_width = max(12, width - 17)
        email = color(trim_text(meta["email"], email_width), "dim")
        last = format_clock(item["last_updated_at"])
        print(fit_line(f"  {email}", color(f"upd {last}", "gray"), width))

        if item["usage"] is not None:
            print("  " + render_usage_pair(item["usage"], width - 2))
        else:
            print("  " + color(trim_text(item["error"], width - 2), "red"))

    hidden = len(ordered_rows) - len(visible_rows)
    if hidden and terminal.lines >= 3 + (len(visible_rows) * 3) + 2:
        print(color("─" * width, "gray"))
        print(color(trim_text(f"+{hidden} more hidden by terminal height", width), "dim"))


def cmd_dashboard_watch(paths: list[Path], epd_url: str | None = None) -> None:
    state: dict[str, dict] = {}
    for path in paths:
        state[path.stem] = {
            "usage": None,
            "error": "等待首次刷新",
            "last_updated_at": None,
            "next_refresh_at": 0.0,
            "was_live": False,
        }
    epd_status = {"ok": True, "message": "EPD WAITING"} if epd_url else None

    while True:
        now = time.time()
        live_account_id = current_account_id()
        rows: list[tuple[Path, dict, dict]] = []
        for path in paths:
            auth = load_json(path)
            meta = parse_auth_metadata(auth)
            rows.append((path, auth, meta))

        refreshed = False
        for path, auth, meta in rows:
            is_live = bool(live_account_id and meta["account_id"] == live_account_id)
            item = state[path.stem]
            role_changed_to_live = is_live and not item["was_live"]
            due = now >= item["next_refresh_at"] or role_changed_to_live
            if due:
                usage, error = safe_fetch_live_usage(auth)
                item["usage"] = usage
                item["error"] = error
                item["last_updated_at"] = now
                item["next_refresh_at"] = now + pick_refresh_seconds(is_live)
                refreshed = True
            item["was_live"] = is_live

        if epd_url and refreshed:
            payload = build_epd_dashboard_payload(rows, state, live_account_id, epd_status)
            ok, message = push_epd_payload(epd_url, payload)
            epd_status = {
                "ok": ok,
                "message": f"EPD {format_clock(time.time())} {message}",
            }

        render_watch_panel(rows, state, live_account_id, epd_status)
        soonest = min(state[path.stem]["next_refresh_at"] for path in paths)
        wait_seconds = max(1, min(10, int(soonest - time.time())))
        time.sleep(wait_seconds)


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


def cmd_dashboard(args: argparse.Namespace) -> None:
    ensure_accounts_dir()
    files = sorted(ACCOUNTS_DIR.glob("*.json"))
    if not files:
        print("还没有保存的账号")
        print("先执行: codex-accounts save <名字>")
        return

    if args.watch:
        try:
            cmd_dashboard_watch(files, args.epd_url)
        except KeyboardInterrupt:
            print("\n已退出实时面板")
        return

    live_account_id = current_account_id()
    render_dashboard_once(files, live_account_id)


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
    dashboard.add_argument(
        "--watch",
        action="store_true",
        help="持续动态刷新: 当前账号 1-5 分钟, 其他账号 5-10 分钟",
    )
    dashboard.add_argument(
        "--epd-url",
        default=os.getenv("CODEX_ACCOUNTS_EPD_URL"),
        help="watch 模式下每次数据刷新后推送 400x300 三色画面到 ESP32，例如 http://192.168.0.106",
    )
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
