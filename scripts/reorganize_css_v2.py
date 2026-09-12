#!/usr/bin/env python3
"""
CSS按板块重新组织脚本 v2（安全版）
先读取，处理，输出到临时文件，验证后再替换
"""
import re

def reorganize_css(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    content = ''.join(lines)
    print(f"原始文件: {len(lines)}行")

    # 找到第一个style标签的开始和结束
    style_start = None
    style_end = None
    for i, line in enumerate(lines):
        if line.strip() == '<style>':
            style_start = i
        elif line.strip() == '</style>' and style_start is not None:
            style_end = i
            break

    if style_start is None or style_end is None:
        print("ERROR: 未找到style标签")
        return False

    print(f"style标签: 第{style_start+1}行 到 第{style_end+1}行")

    # 提取CSS内容（不包括style标签本身）
    css_lines = lines[style_start+1:style_end]
    css_content = ''.join(css_lines)
    print(f"CSS内容: {len(css_lines)}行")

    # 按分隔符拆分
    # 分隔符模式：/* ========== XXX ========== */ 或 /* ===== XXX ===== */
    separator_pattern = re.compile(r'(/\* ={5,} .*? ={5,} \*/\n?)')

    parts = separator_pattern.split(css_content)

    # parts[0]是第一个分隔符之前的内容
    # 然后是分隔符+内容的交替
    sections = []
    i = 1  # 跳过parts[0]（第一个分隔符之前的内容）
    while i < len(parts):
        header = parts[i].strip()
        content_block = parts[i+1] if i+1 < len(parts) else ''
        sections.append((header, content_block))
        i += 2

    print(f"找到 {len(sections)} 个CSS板块")
    for idx, (header, content_block) in enumerate(sections):
        line_count = len(content_block.strip().split('\n'))
        print(f"  {idx+1}. {header[:60]} ({line_count}行)")

    # 定义板块分组（按关键词匹配）
    groups = [
        ("00_基础系统", ["CSS变量", "基础重置", "12列栅格", "自适应栅格"]),
        ("01_响应式布局", ["6 级响应式", "5 端精简版"]),
        ("02_全局组件", ["顶部栏", "工具类"]),
        ("03_策略卡板块", ["策略卡片", "回测策略卡片", "数据告警", "顶部总览条", "今日交易条", "总盈亏大字"]),
        ("04_收益曲线板块", ["收益对比区"]),
        ("05_风险监控板块", ["风险监控区"]),
        ("06_策略日志板块", ["策略日志区"]),
        ("07_弹窗面板", ["模态面板", "侧滑面板"]),
        ("08_对比模式", ["对比模式"]),
        ("09_响应式覆盖", ["响应式"]),
    ]

    # 建立header到content的映射，并标记是否已使用
    section_map = {}
    for header, content_block in sections:
        section_map[header] = content_block

    used_headers = set()
    new_css_lines = []

    # 添加板块目录
    new_css_lines.append("/* ============================================================\n")
    new_css_lines.append("   CSS板块目录（按功能模块组织）\n")
    new_css_lines.append("   ============================================================ */\n")
    new_css_lines.append("\n")

    # 按分组输出
    for group_name, keywords in groups:
        group_sections = []
        for keyword in keywords:
            for header, content_block in section_map.items():
                if header not in used_headers and keyword in header:
                    group_sections.append((header, content_block))
                    used_headers.add(header)

        if group_sections:
            new_css_lines.append("\n")
            new_css_lines.append(f"/* ============================================================\n")
            new_css_lines.append(f"   板块: {group_name}\n")
            new_css_lines.append(f"   ============================================================ */\n")
            new_css_lines.append("\n")
            for header, content_block in group_sections:
                new_css_lines.append(header + "\n")
                new_css_lines.append(content_block.rstrip() + "\n")
                new_css_lines.append("\n")

    # 输出未分组的板块
    ungrouped = []
    for header, content_block in section_map.items():
        if header not in used_headers:
            ungrouped.append((header, content_block))

    if ungrouped:
        new_css_lines.append("\n")
        new_css_lines.append("/* ============================================================\n")
        new_css_lines.append("   板块: 99_其他（未分组）\n")
        new_css_lines.append("   ============================================================ */\n")
        new_css_lines.append("\n")
        for header, content_block in ungrouped:
            new_css_lines.append(header + "\n")
            new_css_lines.append(content_block.rstrip() + "\n")
            new_css_lines.append("\n")

    print(f"\n新CSS: {len(new_css_lines)}行")
    print(f"已分组板块: {len(used_headers)}")
    print(f"未分组板块: {len(ungrouped)}")

    # 构建新的文件内容
    new_lines = []
    new_lines.extend(lines[:style_start+1])  # 包括<style>
    new_lines.extend(new_css_lines)
    new_lines.extend(lines[style_end:])  # 包括</style>及之后

    print(f"新文件: {len(new_lines)}行")

    # 写入临时文件
    temp_file = output_file + '.tmp'
    with open(temp_file, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print(f"\n✅ 已写入临时文件: {temp_file}")
    print(f"   请验证后再替换原文件")
    return True

if __name__ == '__main__':
    input_file = '/Users/junze/quant-monitor-local/index.html'
    output_file = '/Users/junze/quant-monitor-local/index.html'
    reorganize_css(input_file, output_file)
