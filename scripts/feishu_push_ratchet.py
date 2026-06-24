#!/usr/bin
import json
import sys
from pathlib import Path

# 飞书推送函数 (需配置 webhook)
def send_to_feishu(message, chat_id="oc_3d849313ac8459925e8acbd0adcf1ec4"):
    """飞书消息推送"""
    import urllib.request
    import json as json_mod
    
    webhook = "https://open.feishu.cn/open-apis/bot/v2/hook/your-webhook"  # 需替换实际 webhook
    
    payload = {
        "chat_id": chat_id,
        "msg_type": "text",
        "content": {"text": message}
    }
    
    try:
        req = urllib.request.Request(
            webhook,
            data=json_mod.dumps(payload).encode(),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json_mod.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def push_ratchet_complete(strategy_id, result_file):
    """棘轮迭代完成后飞书推送"""
    with open(result_file) as f:
        data = json.load(f)
    
    # 找到最新ACCEPT结果
    final = None
    for r in reversed(data.get('results', [])):
        if r.get('verdict') == 'ACCEPT':
            final = r
            break
    
    if not final:
        final = data.get('baseline', {})
    
    msg = f"""AI量化策略棘轮迭代完成

策略: {strategy_id}
版本: {final.get('round', 'unknown')}
年化: {final.get('annualized_return_pct', 'N/A')}%
回撤: {final.get('max_drawdown_pct', 'N/A')}%
夏普: {final.get('sharpe_ratio', 'N/A')}
交易: {final.get('trades', 'N/A')}笔

状态: ✅ 已自动同步监控面板
链接: https://you9095.github.io/quant-monitor/"""
    
    return send_to_feishu(msg)

if __name__ == '__main__':
    if len(sys.argv) == 3:
        result = push_ratchet_complete(sys.argv[1], sys.argv[2])
        print(f"✓ Feishu push: {result}")