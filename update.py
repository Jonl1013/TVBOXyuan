#!/usr/bin/env python3
"""
TVBox 聚合源自动更新脚本
- 从 tvbox.clbug.com 获取所有源
- 测速（源URL延迟 + 采集站实际播放速度）
- 按播放速度排序：首帧快、不卡顿的排前面
"""
import json, sys, re, subprocess, os, time

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(WORK_DIR, "tvbox.json")

def fetch(url, timeout=10):
    try:
        r = subprocess.run(["curl", "-s", "-L", "--connect-timeout", str(timeout),
                           "--max-time", str(timeout*2), "-A", "Mozilla/5.0", url],
                          capture_output=True, timeout=timeout*2+5)
        return r.stdout.decode("utf-8", errors="replace")
    except:
        return ""

def build_url(base, params):
    sep = "&" if "?" in base else "?"
    return base.rstrip("/") + sep + params

def fetch_source_list():
    html = fetch("https://tvbox.clbug.com/user.php", timeout=20)
    urls = re.findall(r'data-url="([^"]+)"', html)
    names = re.findall(r'<td class="td-name">([^<]+)</td>', html)
    return [(n.strip(), u.strip().replace("&amp;", "&")) for n, u in zip(names, urls) if u.strip() and not u.strip().startswith("#")]

def test_url_latency(url, timeout=8):
    try:
        start = time.time()
        r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                           "--connect-timeout", str(timeout), "--max-time", str(timeout*2),
                           "-L", "-A", "Mozilla/5.0", url],
                          capture_output=True, timeout=timeout*2+5)
        code = r.stdout.decode().strip()
        elapsed = int((time.time() - start) * 1000)
        return elapsed if code.startswith(("2", "3")) else 99999
    except:
        return 99999

def test_play_speed(api, stype):
    """返回 (首帧ms, 下载速度KB/s, HTTP码)"""
    base_api = re.sub(r'[?&]ac=list.*', '', api.rstrip("/"))
    list_body = fetch(build_url(base_api, "ac=list"), timeout=10)
    if not list_body or len(list_body) < 50:
        return 99999, 0, "list_fail"
    
    vod_id = None
    if stype == 0:
        m = re.findall(r'<id>(\d+)</id>', list_body)
        vod_id = m[0] if m else None
    else:
        try:
            j = json.loads(list_body, strict=False)
            vl = j.get("list", [])
            vod_id = str(vl[0]["vod_id"]) if vl else None
        except:
            return 99999, 0, "parse_fail"
    
    if not vod_id:
        return 99999, 0, "no_id"
    
    detail_body = fetch(build_url(base_api, f"ac=detail&ids={vod_id}"), timeout=10)
    if not detail_body:
        return 99999, 0, "detail_fail"
    
    play_url = None
    if stype == 0:
        urls = re.findall(r'(https?://[^\s<>]+?\.m3u8[^\s<>]*)', detail_body)
        play_url = urls[0] if urls else None
    else:
        try:
            dj = json.loads(detail_body, strict=False)
            vl = dj.get("list", [])
            if vl:
                play_raw = vl[0].get("vod_play_url", "")
                urls = re.findall(r'(https?://[^\$\s#<>]+?\.m3u8[^\$\s#<>]*)', play_raw)
                if not urls:
                    urls = re.findall(r'(https?://[^\$\s#<>]+?\.mp4[^\$\s#<>]*)', play_raw)
                play_url = urls[0] if urls else None
        except:
            return 99999, 0, "parse_fail"
    
    if not play_url:
        return 99999, 0, "no_url"
    
    t0 = time.time()
    r = subprocess.run(["curl", "-s", "-o", "/dev/null",
                       "-w", "%{http_code},%{time_starttransfer},%{speed_download}",
                       "--connect-timeout", "5", "--max-time", "10",
                       "-r", "0-512000", play_url],
                      capture_output=True, timeout=15)
    info = r.stdout.decode().strip().split(",")
    code = info[0] if info else "000"
    ttfb = float(info[1]) if len(info) > 1 and info[1] else 99.0
    speed = float(info[2]) if len(info) > 2 and info[2] else 0
    
    if not code.startswith("2"):
        return 99999, 0, code
    return int(ttfb * 1000), int(speed / 1024), code

def fetch_and_parse(url):
    raw = fetch(url, timeout=15)
    if not raw.strip() or raw.strip().startswith("<"):
        return None
    raw = raw.lstrip('﻿')
    raw = re.sub(r',(\s*[}\]])', r'\1', raw)
    try:
        return json.loads(raw, strict=False)
    except:
        start = raw.find('{')
        end = raw.rfind('}')
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end+1], strict=False)
            except:
                pass
    return None

def main():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 开始更新...")

    # 1. 获取源列表
    sources = fetch_source_list()
    print(f"  获取到 {len(sources)} 个源")

    # 2. 测URL延迟 + 抓取源配置
    source_configs = []
    for name, url in sources:
        latency = test_url_latency(url)
        if latency >= 99999:
            continue
        data = fetch_and_parse(url)
        if data:
            source_configs.append((name, url, latency, data))
        sys.stdout.write(f"\r  测试: {len(source_configs)}/{len(sources)}")
        sys.stdout.flush()
    print()
    source_configs.sort(key=lambda x: x[2])
    print(f"  可用源: {len(source_configs)}/{len(sources)}")

    # 3. 收集 type=0/1 采集站 + 测播放速度
    collect_apis = {}  # api -> (name, stype)
    all_lives = []
    all_parses = []
    live_keys = set()
    parse_keys = set()
    
    for name, url, latency, data in source_configs:
        for s in (data.get("sites") or []):
            stype = s.get("type", -1)
            api = s.get("api", "")
            if stype in (0, 1) and api.startswith("http") and api not in collect_apis:
                collect_apis[api] = (s.get("name", ""), stype)
        
        for l in (data.get("lives") or []):
            lurl = l.get("url", "")
            if lurl and lurl not in live_keys:
                live_keys.add(lurl)
                l["name"] = f"[{name}] {l.get('name', '直播')}"
                all_lives.append(l)
        
        for p in (data.get("parses") or []):
            purl = p.get("url", "")
            if purl and purl not in parse_keys:
                parse_keys.add(purl)
                p["name"] = f"[{name}] {p.get('name', '解析')}"
                all_parses.append(p)

    print(f"  发现 {len(collect_apis)} 个采集站，开始测播放速度...")
    
    # 4. 测播放速度
    play_results = []
    for api, (orig_name, stype) in collect_apis.items():
        ttfb, speed, code = test_play_speed(api, stype)
        play_results.append((ttfb, speed, code, orig_name, api, stype))
        status = "ok" if code.startswith("2") else "fail"
        sys.stdout.write(f"\r  测速: {len(play_results)}/{len(collect_apis)} [{status}]")
        sys.stdout.flush()
    print()

    # 5. 排序：可用 → 首帧快 → 速度快
    ok = sorted([(t,s,c,n,a,st) for t,s,c,n,a,st in play_results if c.startswith("2")], key=lambda x:(x[0],-x[1]))
    print(f"  可用采集站: {len(ok)}/{len(collect_apis)}")
    
    for ttfb, speed, code, name, api, stype in ok:
        print(f"    ✅ {ttfb:>5}ms  {speed:>5}KB/s  {name}")

    # 6. 构建JSON
    sites = []
    for ttfb, speed, code, name, api, stype in ok:
        clean_name = re.sub(r'^\[.*?\]\s*', '', name)
        sites.append({
            "key": clean_name or name,
            "name": f"[{ttfb}ms|{speed}KB/s] {clean_name or name}",
            "type": stype,
            "api": api,
            "searchable": 1,
            "quickSearch": 1,
            "filterable": 0
        })

    result = {"spider": "", "sites": sites, "lives": all_lives, "parses": all_parses}
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 源URL列表
    with open(os.path.join(WORK_DIR, "sources.txt"), "w") as f:
        f.write(f"# 更新: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        for name, url, latency, _ in source_configs:
            f.write(f"[{latency}ms] {name}\n{url}\n\n")

    print(f"\n  sites:{len(sites)} lives:{len(all_lives)} parses:{len(all_parses)}")
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 完成!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
