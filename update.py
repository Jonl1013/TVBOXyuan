#!/usr/bin/env python3
"""
TVBox 聚合源自动更新脚本
- 从 tvbox.clbug.com 获取所有源
- 测速（源URL延迟 + 采集站播放速度）
- 合并为一个 JSON，按延迟排序
- 采集站额外标注播放速度
"""
import json, sys, re, subprocess, os, time

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(WORK_DIR, "tvbox.json")

def curl(url, timeout=10, extra_args=None):
    cmd = ["curl", "-s", "-L", "--connect-timeout", str(timeout),
           "--max-time", str(timeout * 2), "-A", "Mozilla/5.0"]
    if extra_args:
        cmd.extend(extra_args)
    cmd.append(url)
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout * 2 + 5)
        return r.stdout.decode("utf-8", errors="replace")
    except:
        return ""

def fetch_source_list():
    html = curl("https://tvbox.clbug.com/user.php", timeout=20)
    urls = re.findall(r'data-url="([^"]+)"', html)
    names = re.findall(r'<td class="td-name">([^<]+)</td>', html)
    sources = []
    for name, url in zip(names, urls):
        url = url.strip().replace("&amp;", "&")
        if url and not url.startswith("#"):
            sources.append((name.strip(), url))
    return sources

def test_url_latency(url, timeout=8):
    try:
        start = time.time()
        r = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
             "--connect-timeout", str(timeout), "--max-time", str(timeout * 2),
             "-L", "-A", "Mozilla/5.0", url],
            capture_output=True, timeout=timeout * 2 + 5
        )
        elapsed = int((time.time() - start) * 1000)
        code = r.stdout.decode().strip()
        if code.startswith(("2", "3")):
            return elapsed, code
        return 99999, code
    except:
        return 99999, "timeout"

def test_play_speed(api, stype):
    """测试采集站的实际播放速度，返回 (播放延迟ms, 状态)"""
    api = api.rstrip("/")
    
    # 获取列表
    list_url = api + "/?ac=list" if "ac=" not in api else api
    body = curl(list_url, timeout=8)
    if not body:
        return 99999, "列表失败"
    
    # 解析第一个视频ID
    vod_id = None
    if stype == 0:  # XML
        m = re.findall(r'<vod>(\d+)', body) or re.findall(r'id="(\d+)"', body)
        if m:
            vod_id = m[0]
    else:  # JSON
        try:
            j = json.loads(body, strict=False)
            vl = j.get("list", [])
            if vl:
                vod_id = str(vl[0].get("vod_id", ""))
        except:
            return 99999, "解析失败"
    
    if not vod_id:
        return 99999, "无视频"
    
    # 获取详情
    detail_url = f"{api}/?ac=detail&ids={vod_id}"
    t0 = time.time()
    detail = curl(detail_url, timeout=8)
    detail_ms = int((time.time() - t0) * 1000)
    
    # 提取播放URL
    play_urls = re.findall(r'(https?://[^\$\s#<>]+?\.(?:m3u8|mp4)[^\$\s#<>]*)', detail)
    if not play_urls:
        return detail_ms, "无播放URL"
    
    # 测试播放URL速度
    play_url = play_urls[0]
    t0 = time.time()
    r = subprocess.run(
        ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code},%{time_total}",
         "--connect-timeout", "5", "--max-time", "8", "-r", "0-102400", play_url],
        capture_output=True, timeout=12
    )
    play_ms = int((time.time() - t0) * 1000)
    info = r.stdout.decode().strip()
    code = info.split(",")[0] if "," in info else "000"
    
    if code.startswith("2"):
        return play_ms, f"✅{code}"
    return play_ms, f"⚠️{code}"

def parse_json(raw):
    raw = raw.lstrip('﻿')
    raw = re.sub(r',(\s*[}\]])', r'\1', raw)
    try:
        return json.loads(raw, strict=False)
    except:
        pass
    start = raw.find('{')
    end = raw.rfind('}')
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start:end+1], strict=False)
        except:
            pass
    return None

def main():
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts}] 开始更新...")

    # 1. 获取源列表
    sources = fetch_source_list()
    print(f"  获取到 {len(sources)} 个源")

    # 2. 测URL延迟
    tested = []
    for name, url in sources:
        latency, code = test_url_latency(url)
        tested.append((name, url, latency))
        sys.stdout.write(f"\r  测速: {len(tested)}/{len(sources)}")
        sys.stdout.flush()
    print()

    available = [(n, u, l) for n, u, l in tested if l < 99999]
    available.sort(key=lambda x: x[2])
    print(f"  可用源: {len(available)}/{len(sources)}")

    # 3. 抓取合并 + 测采集站播放速度
    all_sites, all_lives, all_parses = [], [], []
    spider = ""
    site_keys, live_keys, parse_keys = set(), set(), set()
    play_speeds = {}  # api -> (ms, status)

    for name, url, latency in available:
        raw = curl(url, timeout=15)
        if not raw.strip() or raw.strip().startswith("<"):
            continue
        data = parse_json(raw)
        if not data:
            continue
        if not spider and data.get("spider"):
            spider = data["spider"]
        
        for s in (data.get("sites") or []):
            key = s.get("key", "")
            if not key or key in site_keys:
                continue
            site_keys.add(key)
            
            stype = s.get("type", -1)
            api = s.get("api", "")
            
            # 对 type=0/1 采集站测播放速度
            if stype in (0, 1) and api.startswith("http") and api not in play_speeds:
                pms, pstatus = test_play_speed(api, stype)
                play_speeds[api] = (pms, pstatus)
                s["name"] = f"[播放{pms}ms] {s.get('name', key)}"
            else:
                s["name"] = f"[{latency}ms] {s.get('name', key)}"
            
            s["_latency"] = play_speeds.get(api, (latency,))[0] if stype in (0, 1) else latency
            all_sites.append(s)

        for l in (data.get("lives") or []):
            lurl = l.get("url", "")
            if not lurl or lurl in live_keys:
                continue
            live_keys.add(lurl)
            l["name"] = f"[{name}] {l.get('name', '直播')}"
            all_lives.append(l)

        for p in (data.get("parses") or []):
            purl = p.get("url", "")
            if not purl or purl in parse_keys:
                continue
            parse_keys.add(purl)
            p["name"] = f"[{name}] {p.get('name', '解析')}"
            all_parses.append(p)

    # 按延迟排序：采集站按播放速度排，爬虫源按URL延迟排
    all_sites.sort(key=lambda x: x.get("_latency", 99999))
    for s in all_sites:
        s.pop("_latency", None)

    result = {"spider": spider, "sites": all_sites, "lives": all_lives, "parses": all_parses}
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 打印采集站播放速度报告
    print(f"\n  === 采集站播放测速 ===")
    for api, (ms, status) in sorted(play_speeds.items(), key=lambda x: x[1][0]):
        print(f"    {status} {ms:>5}ms  {api}")
    
    print(f"\n  sites:{len(all_sites)} lives:{len(all_lives)} parses:{len(all_parses)}")
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 完成!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
