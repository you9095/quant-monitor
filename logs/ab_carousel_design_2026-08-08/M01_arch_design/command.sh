#!/bin/bash
# M01_arch_design — evidence commands
# 用途: 为陈以深 5 张策略卡轮播架构方案生成 evidence 三件套
# 日期: 2026-08-08

set -e

WORKDIR=~/quant-monitor-local
EVID_DIR=~/quant-monitor-local/logs/ab_carousel_design_2026-08-08/M01_arch_design

mkdir -p "$EVID_DIR"

cd "$WORKDIR"

echo "=== [1] git status + 当前分支 ==="
git status --short
git branch --show-current
git log --oneline -3

echo ""
echo "=== [2] 45109b2 A 版 commit 改动 stat ==="
git show --stat 45109b2

echo ""
echo "=== [3] 45109b2 完整 diff (index.html 前 200 行) ==="
git show 45109b2 -- index.html | head -200

echo ""
echo "=== [4] panel-ab-test-B 与 master 关系 ==="
git diff master..panel-ab-test-B -- index.html | wc -l
git log master..panel-ab-test-B --oneline

echo ""
echo "=== [5] 现有策略渲染逻辑 (index.html 1240-1303) ==="
sed -n '1240,1303p' index.html

echo ""
echo "=== [6] buildCardHtml 头部 (1305-1320) ==="
sed -n '1305,1320p' index.html

echo ""
echo "=== [7] 5 策略 class 颜色定义 (29-45) + card-header 渐变 (300-310) ==="
sed -n '29,45p' index.html
echo "---"
sed -n '300,310p' index.html

echo ""
echo "=== [8] B 版 opacity 0.8 验证 (294-296) ==="
sed -n '294,296p' index.html

echo ""
echo "=== [9] 容器与栅格 (88-115) ==="
sed -n '88,115p' index.html

echo ""
echo "=== [10] 5 策略键盘快捷键 (2456-2460) ==="
sed -n '2456,2460p' index.html

echo ""
echo "=== [11] 确认无 carousel 依赖 ==="
grep -nE "carousel|swiper|pagination" index.html || echo "[OK] 无 carousel/swiper/pagination 命中"

echo ""
echo "=== [12] 5 策略 sid 列表(从 CSS 颜色变量提取) ==="
grep -nE "^  --(qixing|r32|zhuidian|sanhe|lightning)" index.html

echo ""
echo "=== [EVID] 完成 ==="
echo "raw_output 已生成到 $EVID_DIR/raw_output.txt"