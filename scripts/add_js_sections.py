#!/usr/bin/env python3
"""
JS按板块添加目录和分隔标记（安全版）
不实际移动函数，只添加清晰的板块目录和分隔标记
"""
import re

def add_js_sections(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    content = ''.join(lines)
    print(f"原始文件: {len(lines)}行")

    # 找到主script标签的开始和结束（最后一个script标签）
    script_start = None
    script_end = None
    for i, line in enumerate(lines):
        if line.strip() == '<script>':
            script_start = i
        elif line.strip() == '</script>' and script_start is not None:
            script_end = i

    if script_start is None or script_end is None:
        print("ERROR: 未找到主script标签")
        return False

    print(f"主script标签: 第{script_start+1}行 到 第{script_end+1}行")

    # 提取JS内容
    js_lines = lines[script_start+1:script_end]
    print(f"JS内容: {len(js_lines)}行")

    # 定义板块和对应的函数关键词
    sections = [
        ("00_全局状态与初始化", ["strategiesData", "currentChart", "initData"]),
        ("01_数据渲染总控", ["renderAll"]),
        ("02_策略卡板块", ["renderActionItems", "getTargetCols", "distributeToCols", "calcGridCols", "activeStrategies", "renderStrategyCards", "buildCardHtml", "enhanceCardsForResponsive", "renderCards"]),
        ("03_收益曲线板块", ["fetchLiveCurvesOnce", "toggleCardCurve", "openCardCurve", "closeCardCurve", "renderNavCurves", "renderMultiChart", "initChart", "loadNavCurves", "switchChart"]),
        ("04_今日交易板块", ["renderTradeDetails"]),
        ("05_投资组合板块", ["updatePortfolio", "updateBrandText"]),
        ("06_每日盈亏趋势", ["loadDailyPnlTrend", "renderDailyPnlTrendChart", "switchDailyPnlView"]),
        ("07_WFA分析板块", ["loadWfaSummary", "renderWfaSummaryCards", "loadWfaOosCurve", "renderWfaOosCurveChart"]),
        ("08_参数稳定性板块", ["loadParamStability", "renderParamStabilityCards"]),
        ("09_AB对比板块", ["loadAbComparison", "renderAbComparisonKpi", "renderAbComparisonCards", "renderAbDiffTrendChart"]),
        ("10_策略日志板块", ["renderLogs", "getLogsForDate"]),
        ("11_弹窗面板", ["executeAction", "openStrategyDetail", "closeModal", "openDrawer", "closeDrawer"]),
        ("12_复盘功能", ["initReviewDateSelect", "loadReviewByDate"]),
        ("13_工具函数", ["getTodayStr", "updateClock", "refreshData"]),
    ]

    # 找到每个函数的行号
    function_lines = {}
    for i, line in enumerate(js_lines):
        for section_name, keywords in sections:
            for keyword in keywords:
                if f'function {keyword}' in line or f'async function {keyword}' in line:
                    if keyword not in function_lines:
                        function_lines[keyword] = i

    print(f"\n找到 {len(function_lines)} 个函数")

    # 构建新的JS内容
    new_js_lines = []

    # 添加板块目录
    new_js_lines.append("\n")
    new_js_lines.append("/* ============================================================\n")
    new_js_lines.append("   JS板块目录（按功能模块组织）\n")
    new_js_lines.append("   ============================================================ */\n")
    new_js_lines.append("/*\n")
    for section_name, keywords in sections:
        new_js_lines.append(f"   {section_name}\n")
    new_js_lines.append("   ============================================================ */\n")
    new_js_lines.append("\n")

    # 遍历原始JS行，在每个板块的第一个函数前添加分隔标记
    current_section = None
    section_started = set()

    for i, line in enumerate(js_lines):
        # 检查这一行是否是某个板块的第一个函数
        for section_name, keywords in sections:
            for keyword in keywords:
                if keyword in function_lines and function_lines[keyword] == i:
                    if section_name not in section_started:
                        # 添加板块分隔标记
                        new_js_lines.append("\n")
                        new_js_lines.append(f"/* ============================================================\n")
                        new_js_lines.append(f"   板块: {section_name}\n")
                        new_js_lines.append(f"   ============================================================ */\n")
                        new_js_lines.append("\n")
                        section_started.add(section_name)
                        current_section = section_name

        new_js_lines.append(line)

    print(f"新JS: {len(new_js_lines)}行")
    print(f"已标记板块: {len(section_started)}")

    # 构建新的文件内容
    new_lines = []
    new_lines.extend(lines[:script_start+1])  # 包括<script>
    new_lines.extend(new_js_lines)
    new_lines.extend(lines[script_end:])  # 包括</script>及之后

    print(f"新文件: {len(new_lines)}行")

    # 写入临时文件
    temp_file = output_file + '.tmp'
    with open(temp_file, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print(f"\n✅ 已写入临时文件: {temp_file}")
    return True

if __name__ == '__main__':
    input_file = '/Users/junze/quant-monitor-local/index.html'
    output_file = '/Users/junze/quant-monitor-local/index.html'
    add_js_sections(input_file, output_file)
