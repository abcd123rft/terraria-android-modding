#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JsHook MCP 客户端（供泰拉瑞亚控制面板 / 命令行使用）
=====================================================
功能：列出目标、下发 Frida 脚本、读脚本日志、卸载脚本。

用法：
  python3 jshook.py targets
  python3 jshook.py log --tail 120 [--offset 0]
  python3 jshook.py unload --package com.xd.terraria
  python3 jshook.py exec --package com.xd.terraria --stdin  [--sub "旧||新"]... [--wait 1.5] [--tail 200] [--no-unload]
  python3 jshook.py exec --package com.xd.terraria --file /path/script.js [...]
  python3 jshook.py call --name frida_list_targets --args '{}'

输出：单行 JSON（便于面板解析）。KEY 优先读 /root/.dsh/jshook_key。
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

URL = os.environ.get("JSHOOK_URL", "http://127.0.0.1:19820/mcp")
KEY_FILE = os.environ.get("JSHOOK_KEY_FILE", "/root/.dsh/jshook_key")
SID_FILE = "/tmp/jshook_sid"
DEFAULT_KEY = "6447733a9f81ec0f7d98269e446502f9305903332700311b129b69f5354b1a4f"


def api_key():
    try:
        k = open(KEY_FILE, encoding="utf-8").read().strip()
        if k:
            return k
    except OSError:
        pass
    return DEFAULT_KEY


def _post(payload, sid=None, timeout=180):
    body = json.dumps(payload).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "X-Api-Key": api_key(),
    }
    if sid:
        headers["Mcp-Session-Id"] = sid
    req = urllib.request.Request(URL, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        new_sid = r.headers.get("Mcp-Session-Id")
        raw = r.read().decode("utf-8", "replace")
    # 兼容 SSE 响应（data: {...}）
    text = raw.strip()
    if text.startswith("data:"):
        for line in text.splitlines():
            if line.startswith("data:"):
                text = line[5:].strip()
                break
    return (json.loads(text) if text else {}), new_sid


def new_session():
    d, sid = _post({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                   "clientInfo": {"name": "dsh-terraria-panel", "version": "1"}},
    })
    if sid:
        try:
            open(SID_FILE, "w").write(sid)
        except OSError:
            pass
    return sid


def session_id(force=False):
    if not force:
        try:
            s = open(SID_FILE, encoding="utf-8").read().strip()
            if s:
                return s
        except OSError:
            pass
    return new_session()


def rpc(method, params, rid=1, retry=True):
    try:
        sid = session_id()
        d, new_sid = _post({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}, sid)
        if new_sid:
            try:
                open(SID_FILE, "w").write(new_sid)
            except OSError:
                pass
        return d
    except urllib.error.HTTPError as e:
        if retry and e.code in (400, 401, 404):
            new_session()
            return rpc(method, params, rid, retry=False)
        raise


def call(name, args):
    d = rpc("tools/call", {"name": name, "arguments": args})
    if "error" in d:
        return {"ok": False, "error": d["error"]}
    res = d.get("result", {})
    blocks = res.get("content") or [{}]
    text = blocks[0].get("text", "")
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            parsed.setdefault("ok", True)
            return parsed
        return {"ok": True, "value": parsed}
    except Exception:
        return {"ok": True, "raw": text}


def apply_subs(text, subs):
    for s in subs or []:
        if "||" not in s:
            continue
        old, new = s.split("||", 1)
        if old not in text:
            return None, old
        text = text.replace(old, new, 1)
    return text, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("op", choices=["targets", "log", "unload", "exec", "call", "ping"])
    ap.add_argument("--package", default="com.xd.terraria")
    ap.add_argument("--file")
    ap.add_argument("--stdin", action="store_true")
    ap.add_argument("--sub", action="append", default=[])
    ap.add_argument("--wait", type=float, default=1.5)
    ap.add_argument("--tail", type=int, default=200)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--no-unload", action="store_true")
    ap.add_argument("--name")
    ap.add_argument("--args", default="{}")
    a = ap.parse_args()

    try:
        if a.op == "ping":
            print(json.dumps({"ok": True, "url": URL, "targets": call("frida_list_targets", {})}, ensure_ascii=False))
            return
        if a.op == "targets":
            print(json.dumps(call("frida_list_targets", {}), ensure_ascii=False)); return
        if a.op == "log":
            print(json.dumps(call("frida_read_log", {"package": a.package, "tail": a.tail, "offset": a.offset}), ensure_ascii=False)); return
        if a.op == "unload":
            print(json.dumps(call("frida_unload", {"package": a.package}), ensure_ascii=False)); return
        if a.op == "call":
            print(json.dumps(call(a.name, json.loads(a.args)), ensure_ascii=False)); return

        # exec
        if a.file:
            code = open(a.file, encoding="utf-8").read()
        elif a.stdin:
            code = sys.stdin.read()
        else:
            print(json.dumps({"ok": False, "error": "需要 --file 或 --stdin"}, ensure_ascii=False)); return

        code, missing = apply_subs(code, a.sub)
        if code is None:
            print(json.dumps({"ok": False, "error": "补丁锚点未找到: " + missing}, ensure_ascii=False)); return

        unloaded = None
        if not a.no_unload:
            unloaded = call("frida_unload", {"package": a.package})
        ex = call("frida_execute", {"package": a.package, "code": code})
        if a.wait:
            time.sleep(a.wait)
        lg = call("frida_read_log", {"package": a.package, "tail": a.tail, "offset": 0})
        print(json.dumps({
            "ok": bool(ex.get("ok", True) and ex.get("success", True)),
            "exec": ex,
            "unload": unloaded,
            "log": lg,
        }, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"ok": False, "error": "%s: %s" % (type(e).__name__, e)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
