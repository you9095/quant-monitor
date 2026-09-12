#!/usr/bin/env python3
"""
后端API按板块添加分隔标记
"""
import re

def add_backend_sections(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    print(f"原始文件: {len(lines)}行")

    # 定义板块和对应的函数名
    sections = [
        ("00_工具函数", ["is_baseline_log", "extract_date_from_filename", "find_main_worklog", "load_strategies", "get_latest_signal", "fetch_realtime_prices", "cors"]),
        ("01_策略卡板块", ["get_strategies", "get_dashboard_overview", "get_positions", "get_today_actions", "get_status"]),
        ("02_收益曲线板块", ["get_nav_curves", "dashboard_live_curves"]),
        ("03_投资组合板块", ["dashboard_portfolio_summary"]),
        ("04_今日交易板块", ["dashboard_today_actions_all", "dashboard_strategies_flow_summary"]),
        ("05_回测分析板块", ["dashboard_monthly_compare", "dashboard_qixing_flow", "dashboard_daily_pnl_trend", "dashboard_wfa_summary", "dashboard_wfa_oos_curve", "dashboard_param_stability", "dashboard_ab_comparison", "dashboard_ratchet_evolution"]),
        ("06_告警板块", ["alerts_check", "alerts_trigger", "alerts_history", "_alert_scheduler", "start_alert_scheduler"]),
        ("07_复盘板块", ["get_review_dates", "get_review_by_date", "get_review_range", "save_review_notes"]),
        ("08_系统路由", ["health", "index", "review", "static_files"]),
    ]

    # 找到每个函数的行号
    function_lines = {}
    for i, line in enumerate(lines):
        for section_name, func_names in sections:
            for func_name in func_names:
                if f'def {func_name}(' in line or f'async def {func_name}(' in line:
                    if func_name not in function_lines:
                        function_lines[func_name] = i

    print(f"找到 {len(function_lines)} 个函数")

    # 构建新的文件内容
    new_lines = []
    section_started = set()

    # 在文件开头添加板块目录
    new_lines.append("\n")
    new_lines.append("# ============================================================\n")
    new_lines.append("# 后端API板块目录（按功能模块组织）\n")
    new_lines.append("# ============================================================\n")
    new_lines.append("#\n")
    for section_name, func_names in sections:
        new_lines.append(f"# {section_name}\n")
    new_lines.append("# ============================================================\n")
    new_lines.append("\n")

    # 遍历原始行，在每个板块的第一个函数前添加分隔标记
    for i, line in enumerate(lines):
        # 检查这一行是否是某个板块的第一个函数
        for section_name, func_names in sections:
            for func_name in func_names:
                if func_name in function_lines and function_lines[func_name] == i:
                    if section_name not in section_started:
                        # 添加板块分隔标记
                        new_lines.append("\n")
                        new_lines.append(f"# ============================================================\n")
                        new_lines.append(f"# 板块: {section_name}\n")
                        new_lines.append(f"# ============================================================\n")
                        new_lines.append("\n")
                        section_started.add(section_name)

        new_lines.append(line)

    print(f"新文件: {len(new_lines)}行")
    print(f"已标记板块: {len(section_started)}")

    # 写入临时文件
    temp_file = output_file + '.tmp'
    with open(temp_file, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print(f"\n✅ 已写入临时文件: {temp_file}")
    return True

if __name__ == '__main__':
    input_file = '/Users/junze/quant-monitor-local/api/real_data_server_v2.py'
    output_file = '/Users/junze/quant-monitor-local/api/real_data_server_v2.py'
    add_backend_sections(input_file, output_file)
