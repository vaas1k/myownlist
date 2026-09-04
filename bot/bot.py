#!/usr/bin/env python3
"""Telegram bot: принимает домены сообщением, дописывает в lists/myownlist.txt, пушит.

Только stdlib. Параметры из env (см. /etc/myownlist-bot.env):
  BOT_TOKEN, ALLOWED_CHAT_ID, REPO_DIR, REPO_SSH, LIST_FILE, GIT_SSH_COMMAND
Запуск: python3 bot.py        Самотест: python3 bot.py --selftest
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
HELP = "Пришли домен (или несколько через пробел/перенос). Добавлю в myownlist и запушу."


def normalize(raw: str) -> str:
    """'HTTPS://Foo.Com:443/path' -> 'foo.com'. Возвращает '' если мусор."""
    s = raw.strip().lower().rstrip(".,;")
    s = re.sub(r"^[a-z]+://", "", s)
    s = s.split("/")[0].split("?")[0].split("#")[0].split("@")[-1].split(":")[0]
    return s if DOMAIN_RE.match(s) else ""


def parse_domains(text: str):
    """-> (valid: list[str] без дублей в порядке появления, invalid: list[str])."""
    valid, invalid, seen = [], [], set()
    for tok in re.split(r"[\s,]+", text):
        if not tok:
            continue
        d = normalize(tok)
        if not d:
            invalid.append(tok)
        elif d not in seen:
            seen.add(d)
            valid.append(d)
    return valid, invalid


def existing_domains(path: str) -> set:
    with open(path) as f:
        return {ln.strip().lower() for ln in f if ln.strip() and not ln.startswith("#")}


def git(repo: str, *args: str) -> str:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, env=env, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"git {args[0]}: {(r.stderr or r.stdout).strip()[-400:]}")
    return r.stdout


def ensure_repo(repo: str, ssh_url: str):
    if not os.path.isdir(os.path.join(repo, ".git")):
        subprocess.run(["git", "clone", "-q", ssh_url, repo], check=True, timeout=120)
        git(repo, "config", "user.name", "myownlist-bot")
        git(repo, "config", "user.email", "myownlist-bot@srv2")


def add_domains(repo: str, list_file: str, domains: list) -> tuple:
    """-> (added, already). Делает pull --rebase, append, commit, push."""
    git(repo, "pull", "-q", "--rebase")
    path = os.path.join(repo, list_file)
    have = existing_domains(path)
    added = [d for d in domains if d not in have]
    already = [d for d in domains if d in have]
    if not added:
        return added, already
    with open(path, "a") as f:
        if os.path.getsize(path) and not open(path, "rb").read()[-1:] == b"\n":
            f.write("\n")
        f.write("\n".join(added) + "\n")
    git(repo, "add", list_file)
    git(repo, "commit", "-q", "-m", "Add " + ", ".join(added))
    git(repo, "push", "-q")
    return added, already


# ---- telegram (stdlib) ----
def tg(token: str, method: str, **params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/{method}", data=data)
    with urllib.request.urlopen(req, timeout=70) as r:
        return json.load(r)


def handle(text: str, cfg: dict) -> str:
    if text.startswith("/"):
        return HELP
    valid, invalid = parse_domains(text)
    if not valid:
        return "Не нашёл валидных доменов. " + HELP
    try:
        ensure_repo(cfg["REPO_DIR"], cfg["REPO_SSH"])
        added, already = add_domains(cfg["REPO_DIR"], cfg["LIST_FILE"], valid)
    except Exception as e:  # git/сеть — сообщаем, файл не тронут
        return f"Ошибка: {e}"
    parts = []
    if added:
        parts.append("Добавил: " + ", ".join(added) + "\nСборка srs пошла, жди уведомление.")
    if already:
        parts.append("Уже было: " + ", ".join(already))
    if invalid:
        parts.append("Пропустил (не домен): " + ", ".join(invalid))
    return "\n".join(parts)


def main():
    cfg = {k: os.environ.get(k, "") for k in ("BOT_TOKEN", "ALLOWED_CHAT_ID", "REPO_DIR", "REPO_SSH", "LIST_FILE")}
    missing = [k for k, v in cfg.items() if not v]
    if missing:
        sys.exit(f"missing env: {', '.join(missing)}")
    allowed = int(cfg["ALLOWED_CHAT_ID"])
    offset = 0
    print("bot started", flush=True)
    while True:
        try:
            upd = tg(cfg["BOT_TOKEN"], "getUpdates", offset=offset, timeout=60, allowed_updates='["message"]')
        except Exception as e:
            print("getUpdates:", e, flush=True)
            time.sleep(5)
            continue
        for u in upd.get("result", []):
            offset = u["update_id"] + 1
            msg = u.get("message") or {}
            chat_id = (msg.get("chat") or {}).get("id")
            text = (msg.get("text") or "").strip()
            if chat_id != allowed or not text:
                continue  # чужих игнорируем молча
            reply = handle(text, cfg)
            try:
                tg(cfg["BOT_TOKEN"], "sendMessage", chat_id=chat_id, text=reply)
            except Exception as e:
                print("sendMessage:", e, flush=True)


def selftest():
    assert normalize("HTTPS://Foo.Com:443/path?x=1") == "foo.com"
    assert normalize("www.example.org.") == "www.example.org"
    assert normalize("user@host.io") == "host.io"
    assert normalize("not a domain") == ""
    assert normalize("localhost") == ""
    assert normalize("a..b.com") == ""
    assert normalize("-bad.com") == ""
    v, i = parse_domains("a.com, B.COM\nhttp://a.com/x  junk  c.d.e.org")
    assert v == ["a.com", "b.com", "c.d.e.org"], v
    assert i == ["junk"], i
    assert handle("/start", {}) == HELP
    assert handle("!!!", {}).startswith("Не нашёл")
    print("selftest OK")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else main()
