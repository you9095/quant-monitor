"""rebaseline entry — 重测 sample=300 baseline"""
import sys
sys.path = [p for p in sys.path if 'hermes-agent' not in p]
sys.path.insert(0, '/Users/junze/quant-monitor-local/strategies/goldcombo')
import _ratchet_fast_runner as F
import json

SAMPLE = 300
with open('/Users/junze/quant-monitor-local/strategies/goldcombo/ratchet_baseline_ashare.json') as f:
    baseline = json.load(f)

pool_2y = baseline['data_periods']['2y']['ashare_pool_used'][:SAMPLE]
pool_5y = baseline['data_periods']['5y']['ashare_pool_used'][:SAMPLE]

cfg = F.get_round_config(1)
b2y = F.run_pool_round_fast(pool_2y, cfg, *F.DATA_PERIOD_2Y[:2])
b5y = F.run_pool_round_fast(pool_5y, cfg, *F.DATA_PERIOD_5Y[:2])

baseline['data_periods']['2y']['total_return_pct'] = b2y['total_return_pct']
baseline['data_periods']['2y']['max_drawdown_pct'] = b2y['max_drawdown_pct']
baseline['data_periods']['2y']['sharpe_ratio'] = b2y['sharpe_ratio']
baseline['data_periods']['2y']['trade_count'] = b2y['closed_trades']
baseline['data_periods']['2y']['closed_trades'] = b2y['closed_trades']

baseline['data_periods']['5y']['total_return_pct'] = b5y['total_return_pct']
baseline['data_periods']['5y']['max_drawdown_pct'] = b5y['max_drawdown_pct']
baseline['data_periods']['5y']['sharpe_ratio'] = b5y['sharpe_ratio']
baseline['data_periods']['5y']['trade_count'] = b5y['closed_trades']
baseline['data_periods']['5y']['closed_trades'] = b5y['closed_trades']

baseline['methodology_note'] = f'基线与棘轮迭代同口径 (sample={SAMPLE}, top by 流动性)'

with open('/Users/junze/quant-monitor-local/strategies/goldcombo/ratchet_baseline_ashare.json', 'w', encoding='utf-8') as f:
    json.dump(baseline, f, ensure_ascii=False, indent=2)

print(f'[rebaseline] sample={SAMPLE}')
print(f'  2Y: return={b2y["total_return_pct"]}% dd={b2y["max_drawdown_pct"]}% trades={b2y["closed_trades"]}')
print(f'  5Y: return={b5y["total_return_pct"]}% dd={b5y["max_drawdown_pct"]}% trades={b5y["closed_trades"]}')
