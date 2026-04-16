import os
import re
from pathlib import Path

BASE_URL = "https://gaokao.chsi.com.cn/zyk/zybk/"
OUTPUT_DIR = Path("output")

LEVEL_NAMES = [
    "本科（普通教育）",
    "本科（职业教育）",
    "高职（专科）",
]

SAVE_DEBUG = os.getenv("SAVE_DEBUG", "0") == "1"
SCRAPE_DETAILS = os.getenv("SCRAPE_DETAILS", "1") == "1"
SCRAPE_SCHOOLS = os.getenv("SCRAPE_SCHOOLS", "1") == "1"

NAV_BLACKLIST = {
    "首页", "高考资讯", "阳光志愿", "高招咨询", "招生动态", "试题评析", "院校库", "专业库",
    "院校满意度", "专业满意度", "专业推荐", "更多", "招生政策", "选科参考", "云咨询周",
    "成绩查询", "招生章程", "名单公示", "志愿参考", "咨询室", "录取结果", "高职招生",
    "工作动态", "心理测评", "直播安排", "批次线", "专业解读", "各地网站", "职业前景",
    "特殊类型招生", "志愿填报时间", "招办访谈", "登录", "注册", "搜索", "查看", "取消",
    "基本信息", "开设院校", "开设课程", "图解专业", "选科要求", "更多>"
}

SECTION_ORDER = [
    "专业介绍",
    "统计信息",
    "相近专业",
    "本专业推荐人数较多的高校",
    "该专业学生考研方向",
    "已毕业人员从业方向",
    "薪酬指数",
]

SATISFACTION_LABELS = [
    "综合满意度",
    "办学条件满意度",
    "教学质量满意度",
    "就业满意度",
]

SCHOOL_NAME_RE = re.compile(
    r"(大学|学院|学校|职业大学|职业学院|高等专科学校|师范大学|师范学院|医学院|中医药大学)$"
)
