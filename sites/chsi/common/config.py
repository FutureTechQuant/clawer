from pathlib import Path

BASE_URL = "https://gaokao.chsi.com.cn"

CHSI_DATA_DIR = Path("data/chsi")

MAJORS_BASE_URL = "https://gaokao.chsi.com.cn/zyk/zybk/"
SCHOOLS_LIST_URL = "https://gaokao.chsi.com.cn/sch/search--ss-on,option-qg,searchType-1,start-{start}.dhtml"

MAJORS_OUTPUT_DIR = CHSI_DATA_DIR / "majors"
SCHOOLS_OUTPUT_DIR = CHSI_DATA_DIR / "schools"

SCHOOL_PAGE_SIZE = 20
SCHOOL_MAX_START = 2900
SCHOOL_STARTS = list(range(0, SCHOOL_MAX_START + SCHOOL_PAGE_SIZE, SCHOOL_PAGE_SIZE))