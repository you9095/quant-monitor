#!/usr/bin/env python3
"""
CSS按板块重新组织脚本
读取index.html的CSS部分，按板块重新组织，保持CSS规则的相对顺序不变
"""
import re
import sys

def reorganize_css(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 提取第一个style标签的内容
    style_match = re.search(r'(<style>\n)(.*?)(\n</style>)', content, re.DOTALL)
    if not style_match:
        print("ERROR: 未找到style标签")
        return False

    style_open = style_match.group(1)
    css_content = style_match.group(2)
    style_close = style_match.group(3)

    # 按现有的分隔符拆分CSS块
    # 现有的分隔符模式：/* ========== XXX ========== */
    blocks = re.split(r'(/\* ={5,} .*? ={5,} \*/\n)', css_content)

    # blocks[0]是第一个分隔符之前的内容（通常为空）
    # 然后是分隔符+内容的交替
    sections = []
    current_header = None
    current_content = []

    for block in blocks:
        if re.match(r'/\* ={5,} .*? ={5,} \*/', block):
            if current_header:
                sections.append((current_header, ''.join(current_content)))
            current_header = block.strip()
            current_content = []
        else:
            current_content.append(block)

    if current_header:
        sections.append((current_header, ''.join(current_content)))

    print(f"找到 {len(sections)} 个CSS板块")
    for i, (header, content) in enumerate(sections):
        lines = content.strip().split('\n')
        print(f"  {i+1}. {header[:50]}... ({len(lines)}行)")

    # 定义板块分组
    groups = {
        "00_基础系统": [
            "CSS变量设计系统",
            "基础重置",
            "12列栅格",
            "自适应栅格",
        ],
        "01_响应式布局": [
            "6 级响应式布局",
            "5 端精简版",
        ],
        "02_全局组件": [
            "顶部栏",
            "工具类",
        ],
        "03_策略卡板块": [
            "策略卡片",
            "回测策略卡片",
            "数据告警就地标注",
            "v1.1 (2026-06-26) 顶部总览条",
            "v1.1 (2026-06-26) 卡片顶部：今日交易条",
            "v1.1 (2026-06-26) 卡片中央：总盈亏大字",
        ],
        "04_收益曲线板块": [
            "收益对比区",
        ],
        "05_风险监控板块": [
            "风险监控区",
        ],
        "06_策略日志板块": [
            "策略日志区",
        ],
        "07_弹窗面板": [
            "模态面板",
            "侧滑面板",
        ],
        "08_对比模式": [
            "对比模式",
        ],
        "09_响应式覆盖": [
            "响应式",
        ],
    }

    # 构建新的CSS内容
    new_css_parts = []
    new_css_parts.append("/* ============================================================")
    new_css_parts.append("   CSS板块目录（按功能模块组织）")
    new_css_parts.append("   ============================================================")
    new_css_parts.append("   00_基础系统: CSS变量 + 基础重置 + 栅格系统")
    new_css_parts.append("   01_响应式布局: 6级响应式 + 5端精简版")
    new_css_parts.append("   02_全局组件: 顶部栏 + 工具类")
    new_css_parts.append("   03_策略卡板块: 策略卡 + 回测卡 + 告警标注 + 今日交易 + 总盈亏")
    new_css_parts.append("   04_收益曲线板块: 收益对比区")
    new_css_parts.append("   05_风险监控板块: 风险监控区")
    new_css_parts.append("   06_策略日志板块: 策略日志区")
    new_css_parts.append("   07_弹窗面板: 模态面板 + 侧滑面板")
    new_css_parts.append("   08_对比模式: 对比模式")
    new_css_parts.append("   09_响应式覆盖: 响应式媒体查询")
    new_css_parts.append("   ============================================================ */")
    new_css_parts.append("")

    # 建立header到content的映射
    section_map = {}
    for header, content in sections:
        # 提取关键名称
        name_match = re.search(r'/\* ={5,} (.*?) ={5,} \*/', header)
        if name_match:
            name = name_match.group(1).strip()
            section_map[name] = (header, content)

    # 按分组输出
    used_sections = set()
    for group_name, keywords in groups.items():
        group_sections = []
        for keyword in keywords:
            for name, (header, content) in section_map.items():
                if keyword in name and name not in used_sections:
                    group_sections.append((header, content))
                    used_sections.add(name)

        if group_sections:
            new_css_parts.append("")
            new_css_parts.append(f"/* ============================================================")
            new_css_parts.append(f"   板块: {group_name}")
            new_css_parts.append(f"   ============================================================ */")
            new_css_parts.append("")
            for header, content in group_sections:
                new_css_parts.append(header)
                new_css_parts.append(content.rstrip())
                new_css_parts.append("")

    # 输出未分组的板块
    ungrouped = []
    for name, (header, content) in section_map.items():
        if name not in used_sections:
            ungrouped.append((header, content))

    if ungrouped:
        new_css_parts.append("")
        new_css_parts.append("/* ============================================================")
        new_css_parts.append("   板块: 99_其他（未分组）")
        new_css_parts.append("   ============================================================ */")
        new_css_parts.append("")
        for header, content in ungrouped:
            new_css_parts.append(header)
            new_css_parts.append(content.rstrip())
            new_css_parts.append("")

    new_css = '\n'.join(new_css_parts)

    # 替换原有的CSS
    new_content = content.replace(style_open + css_content + style_close, style_open + new_css + style_close)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"\n✅ CSS重新组织完成")
    print(f"   原始CSS: {len(css_content.split(chr(10)))}行")
    print(f"   新CSS: {len(new_css.split(chr(10)))}行")
    print(f"   分组数: {len(groups)}")
    print(f"   已分组板块: {len(used_sections)}")
    print(f"   未分组板块: {len(ungrouped)}")
    return True

if __name__ == '__main__':
    input_file = '/Users/junze/quant-monitor-local/index.html'
    output_file = '/Users/junze/quant-monitor-local/index.html'
    reorganize_css(input_file, output_file)
