"""
轻量级 HTTP 服务器 — 远程配置刷视频参数
基于 MicroPython socket，无第三方依赖
"""
import socket
import config

try:
    import json
except ImportError:
    json = None

_server_sock = None


def _get_config_dict():
    return {
        "interval_min": config.SWIPE_INTERVAL_MIN,
        "interval_max": config.SWIPE_INTERVAL_MAX,
        "screen_w": config.PHONE_SCREEN_W,
        "screen_h": config.PHONE_SCREEN_H,
    }


def _apply_config(d):
    """将 JSON dict 应用到 config 模块"""
    changed = False
    if "interval_min" in d:
        v = int(d["interval_min"])
        if 1 <= v <= 120:
            config.SWIPE_INTERVAL_MIN = v
            changed = True
    if "interval_max" in d:
        v = int(d["interval_max"])
        if 5 <= v <= 300:
            config.SWIPE_INTERVAL_MAX = v
            changed = True
    if "screen_w" in d:
        v = int(d["screen_w"])
        if 100 <= v <= 4000:
            config.PHONE_SCREEN_W = v
            changed = True
    if "screen_h" in d:
        v = int(d["screen_h"])
        if 100 <= v <= 6000:
            config.PHONE_SCREEN_H = v
            changed = True
    # 保证 min <= max，非法组合自动交换
    if config.SWIPE_INTERVAL_MIN > config.SWIPE_INTERVAL_MAX:
        config.SWIPE_INTERVAL_MIN, config.SWIPE_INTERVAL_MAX = \
            config.SWIPE_INTERVAL_MAX, config.SWIPE_INTERVAL_MIN
        changed = True
    if changed:
        try:
            from app.setting import save_settings
            save_settings()
        except Exception:
            pass
    return changed


_HTML_PAGE = """\
<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ESP32 Swipe Config</title>
<style>
body{font-family:sans-serif;max-width:420px;margin:20px auto;padding:0 12px;
     background:#1a1a2e;color:#e0e0e0}
h1{color:#00d4ff;font-size:1.3em}
label{display:block;margin:12px 0 4px;font-size:.9em;color:#aaa}
input,select{width:100%%;padding:8px;border:1px solid #333;border-radius:6px;
             background:#16213e;color:#fff;font-size:1em;box-sizing:border-box}
button{margin-top:18px;width:100%%;padding:12px;border:none;border-radius:6px;
       background:#00d4ff;color:#000;font-weight:bold;font-size:1em;cursor:pointer}
button:active{background:#00a0cc}
.msg{margin-top:12px;padding:8px;border-radius:4px;text-align:center}
.ok{background:#0a3d0a;color:#4caf50}
.info{background:#1a1a2e;color:#888;font-size:.8em;margin-top:20px}
.error{background:#3d0a0a;color:#f44}
</style></head><body>
<h1>ESP32 Swipe Config</h1>
<form id="f">
<label>Min Interval (s)</label>
<input type="number" id="imin" min="1" max="120" value="%d">
<label>Max Interval (s)</label>
<input type="number" id="imax" min="5" max="300" value="%d">
<label>Phone Resolution</label>
<select id="res">
<option value="1080,1920"%s>1080 x 1920</option>
<option value="720,1280"%s>720 x 1280</option>
<option value="1080,2340"%s>1080 x 2340</option>
<option value="1080,2400"%s>1080 x 2400</option>
<option value="1440,2560"%s>1440 x 2560</option>
<option value="1440,3200"%s>1440 x 3200</option>
</select>
<button type="button" onclick="save()">Save</button>
</form>
<div id="m"></div>
<div class="info">Device: esp32-xm | BLE HID Touch Screen</div>
<script>
function save(){
 var r=document.getElementById('res').value.split(',');
 var d={interval_min:document.getElementById('imin').value,
        interval_max:document.getElementById('imax').value,
        screen_w:r[0],screen_h:r[1]};
 var btn=document.querySelector('button');
 btn.disabled=true;btn.textContent='Saving...';
 fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify(d)}).then(r=>r.json()).then(j=>{
  btn.disabled=false;btn.textContent='Save';
  var m=document.getElementById('m');
  m.className='msg ok';
  m.style.cssText='margin-top:12px;padding:12px;border-radius:6px;text-align:center;font-size:1.1em;font-weight:bold;background:#0a3d0a;color:#4caf50';
  m.textContent='✓ '+(j.msg||'Saved!');
  setTimeout(function(){m.textContent='';m.style.cssText='';},3000);
 }).catch(e=>{
  btn.disabled=false;btn.textContent='Save';
  var m=document.getElementById('m');
  m.style.cssText='margin-top:12px;padding:12px;border-radius:6px;text-align:center;font-size:1.1em;background:#3d0a0a;color:#f44';
  m.textContent='✗ Error: '+e;
 });
}
</script></body></html>"""


def _build_html():
    """构建 HTML 页面，填入当前配置值"""
    sw = str(config.PHONE_SCREEN_W)
    sh = str(config.PHONE_SCREEN_H)
    sel = " selected"
    # 标记当前分辨率
    presets = ["1080,1920", "720,1280", "1080,2340",
               "1080,2400", "1440,2560", "1440,3200"]
    marks = []
    current = "%s,%s" % (sw, sh)
    for p in presets:
        marks.append(sel if p == current else "")
    return _HTML_PAGE % (
        config.SWIPE_INTERVAL_MIN,
        config.SWIPE_INTERVAL_MAX,
        marks[0], marks[1], marks[2],
        marks[3], marks[4], marks[5])


def _parse_request(data):
    """极简 HTTP 请求解析"""
    try:
        text = data.decode("utf-8", "ignore")
        lines = text.split("\r\n")
        if not lines:
            return None, None, None
        parts = lines[0].split(" ")
        if len(parts) < 2:
            return None, None, None
        method = parts[0]
        path = parts[1]
        body = ""
        if "\r\n\r\n" in text:
            body = text.split("\r\n\r\n", 1)[1]
        return method, path, body
    except Exception:
        return None, None, None


def _response(code, content_type, body):
    """构建 HTTP 响应"""
    if isinstance(body, str):
        body = body.encode("utf-8")
    header = "HTTP/1.1 %d OK\r\nContent-Type: %s\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % (
        code, content_type, len(body))
    return header.encode("utf-8") + body


def _parse_content_length(header_bytes):
    """从请求头字节串中解析 Content-Length，无则返回 0"""
    for line in header_bytes.split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            try:
                return int(line.split(b":", 1)[1].strip())
            except ValueError:
                return 0
    return 0


def _handle_client(cl_sock):
    """处理单个 HTTP 请求"""
    try:
        cl_sock.settimeout(3)
        data = b""
        # 收完请求头后，按 Content-Length 继续收满 body（POST body 可能晚于头部到达）
        while True:
            try:
                chunk = cl_sock.recv(1024)
            except OSError:
                break
            if not chunk:
                break
            data += chunk
            if b"\r\n\r\n" not in data:
                continue
            header, body = data.split(b"\r\n\r\n", 1)
            if len(body) >= _parse_content_length(header):
                break
        if not data:
            return
        method, path, body = _parse_request(data)
        if method is None:
            cl_sock.send(_response(400, "text/plain", "Bad Request"))
            return

        if path == "/" and method == "GET":
            html = _build_html()
            cl_sock.send(_response(200, "text/html; charset=utf-8", html))

        elif path == "/api/config" and method == "GET":
            if json:
                j = json.dumps(_get_config_dict())
                cl_sock.send(_response(200, "application/json", j))
            else:
                cl_sock.send(_response(500, "text/plain", "no json"))

        elif path == "/api/config" and method == "POST":
            if json and body:
                try:
                    d = json.loads(body)
                    changed = _apply_config(d)
                    resp = json.dumps({
                        "ok": True,
                        "changed": changed,
                        "msg": "Saved!" if changed else "No change",
                        "config": _get_config_dict(),
                    })
                    cl_sock.send(_response(200, "application/json", resp))
                except Exception as e:
                    resp = json.dumps({"ok": False, "error": str(e)})
                    cl_sock.send(_response(400, "application/json", resp))
            else:
                cl_sock.send(_response(400, "text/plain", "no body"))
        else:
            cl_sock.send(_response(404, "text/plain", "Not Found"))
    except Exception as e:
        import sys
        print("HTTP handle error:", e)
        sys.print_exception(e)
    finally:
        try:
            cl_sock.close()
        except Exception:
            pass


def poll():
    """非阻塞轮询，处理一个待处理的 HTTP 请求（若有）"""
    global _server_sock
    if _server_sock is None:
        return
    try:
        cl, addr = _server_sock.accept()
        _handle_client(cl)
    except OSError:
        pass  # 超时，无请求


def start():
    """启动 HTTP 服务器（非阻塞）"""
    global _server_sock
    if _server_sock is not None:
        return
    try:
        addr = socket.getaddrinfo("0.0.0.0", config.HTTP_PORT)[0][-1]
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(addr)
        s.listen(2)
        s.settimeout(0.05)  # 50ms 超时，非阻塞
        _server_sock = s
        print("HTTP server on port", config.HTTP_PORT)
    except Exception as e:
        print("HTTP start failed:", e)
        _server_sock = None


def stop():
    """停止 HTTP 服务器"""
    global _server_sock
    if _server_sock is not None:
        try:
            _server_sock.close()
        except Exception:
            pass
        _server_sock = None
