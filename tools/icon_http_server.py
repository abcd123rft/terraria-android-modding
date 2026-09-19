#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""图标静态服务（菜单的 HTTP 回退通道）

菜单取图标的顺序是：
  ① BitmapFactory.decodeFile('/sdcard/Download/DSHA/terraria_icons/atlas_N.png')
  ② 失败才回退到 http://127.0.0.1:8899/atlas_N.png  ← 就是这个服务
所以**只有直接读文件不可用时才需要它**。

用法（容器里，长期跑建议放后台）：
    python3 图标HTTP服务.py          # 默认 8899
    python3 图标HTTP服务.py 8899
"""
import http.server
import os
import sys

DIR = os.environ.get('ICON_DIR', '/sdcard/Download/DSHA/terraria_icons')
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8899


LOG_FILE = os.environ.get('ICON_LOG', '/tmp/dsha_icon_log.txt')


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):      # 静音，别刷屏
        pass

    def do_GET(self):
        """额外提供 /log?m=... ：把游戏进程里的日志落到容器文件里。
        游戏被切到后台时 JsHook 的日志通道会拿不到内容，用它做可靠的测速/调试输出。"""
        if self.path.startswith('/log?'):
            from urllib.parse import parse_qs, urlparse, unquote
            msg = (parse_qs(urlparse(self.path).query).get('m') or [''])[0]
            try:
                with open(LOG_FILE, 'a', encoding='utf-8') as f:
                    f.write(unquote(msg) + '\n')
            except OSError:
                pass
            self.send_response(200)
            self.send_header('Content-Length', '2')
            self.end_headers()
            self.wfile.write(b'ok')
            return
        return http.server.SimpleHTTPRequestHandler.do_GET(self)


if not os.path.isdir(DIR):
    print('目录不存在：%s（先从 图集/ 复制两张 2048 图集过来并改名 atlas_0.png / atlas_1.png）' % DIR)
    sys.exit(1)

os.chdir(DIR)
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
print('图标服务已启动：http://127.0.0.1:%d/atlas_0.png  （目录 %s）' % (PORT, DIR))
print('停止：Ctrl-C')
try:
    srv.serve_forever()
except KeyboardInterrupt:
    print('\n已停止')
