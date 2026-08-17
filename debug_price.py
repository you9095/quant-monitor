#!/usr/bin/env python3
import urllib.request

# 网易财经 API
urls = [
    "https://api.money.126.net/data/feed/159915",  # 网易
    "https://quotes.sina.cn/api/json_v2.php?q=sh513100",  # 新浪另一种
]

for url in urls:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read().decode('utf-8')
        print(f"URL: {url}\n数据: {data[:300]}\n")
    except Exception as e:
        print(f"URL: {url} 错误: {e}\n")