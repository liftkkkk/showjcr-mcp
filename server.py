# -*- coding: utf-8 -*-
"""
ShowJCR MCP Server
读取 ShowJCR 项目（https://github.com/hitfyd/ShowJCR）附带的数据 CSV，
提供中科院分区、JCR 影响因子、新锐分区、CCF 推荐目录、CCF-T 高质量期刊、
国际预警期刊名单等查询能力。

数据目录默认指向本仓库：
  .../2026-10-14-09-24-35/ShowJCR/中科院分区表及JCR原始数据文件
可通过环境变量 SHOWJCR_DATA_DIR 覆盖。
"""

import csv
import difflib
import os
import re
import sys
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# 数据文件配置
# ---------------------------------------------------------------------------

# 数据目录解析顺序：
#   1) 环境变量 SHOWJCR_DATA_DIR
#   2) 本仓库内 ./data 目录（先运行 scripts/fetch_data.py 下载）
# 数据文件本身不随本仓库分发，版权归中科院文献情报中心 / CCF 等原始机构所有，
# 请通过 scripts/fetch_data.py 从 hitfyd/ShowJCR 项目获取。
DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DATA_DIR = os.environ.get("SHOWJCR_DATA_DIR") or DEFAULT_DATA_DIR

# name -> (文件名, 说明)
CAS_FILES = {
    2021: ("FQBJCR2021-UTF8.csv", "中科院分区表 2021（基础版/升级版格式由表内列区分）"),
    2022: ("FQBJCR2022-UTF8.csv", "中科院分区表 2022"),
    2023: ("FQBJCR2023-UTF8.csv", "中科院分区表 2023（升级版）"),
    2025: ("FQBJCR2025-UTF8.csv", "中科院分区表 2025（升级版）"),
}
JCR_FILES = {
    2020: ("JCR2020-UTF8.csv", "JCR 2020 影响因子与分区"),
    2021: ("JCR2021-UTF8.csv", "JCR 2021 影响因子与分区"),
    2022: ("JCR2022-UTF8.csv", "JCR 2022 影响因子与分区"),
    2023: ("JCR2023-UTF8.csv", "JCR 2023 影响因子与分区"),
    2024: ("JCR2024-UTF8.csv", "JCR 2024 影响因子与分区"),
    2025: ("JCR2025-UTF8.csv", "JCR 2025 影响因子与分区"),
}
WARNING_FILES = {
    2020: ("GJQKYJMD2020.csv", "国际期刊预警名单 2020（含预警等级）"),
    2021: ("GJQKYJMD2021.csv", "国际期刊预警名单 2021（含预警等级）"),
    2023: ("GJQKYJMD2023.csv", "国际期刊预警名单 2023（含预警等级）"),
    2024: ("GJQKYJMD2024.csv", "国际期刊预警名单 2024（预警原因）"),
    2025: ("GJQKYJMD2025.csv", "国际期刊预警名单 2025（预警原因）"),
}
XR_FILE = ("XR2026-UTF8.csv", "新锐期刊分区表 2026")
XR_CONF_FILE = ("XR2026Conferences-UTF8.csv", "新锐分区 2026 会议版")
CCF_FILE = ("CCF2026-UTF8.csv", "CCF 推荐国际学术会议和期刊目录 2026")
CCFT_FILE = ("CCFT2025-UTF8.csv", "计算领域高质量科技期刊分级目录 2025（T1/T2/T3）")

# ---------------------------------------------------------------------------
# 加载与索引
# ---------------------------------------------------------------------------

_tables: dict[str, list[dict[str, str]]] = {}


def _load(name: str) -> list[dict[str, str]]:
    """按表名懒加载 CSV，全部行以 dict 形式缓存。"""
    if name in _tables:
        return _tables[name]
    mapping = {}
    for y, (fn, _) in CAS_FILES.items():
        mapping[f"cas{y}"] = fn
    for y, (fn, _) in JCR_FILES.items():
        mapping[f"jcr{y}"] = fn
    for y, (fn, _) in WARNING_FILES.items():
        mapping[f"warn{y}"] = fn
    mapping["xr"] = XR_FILE[0]
    mapping["xrconf"] = XR_CONF_FILE[0]
    mapping["ccf"] = CCF_FILE[0]
    mapping["ccft"] = CCFT_FILE[0]
    fn = mapping.get(name)
    if fn is None:
        raise ValueError(f"未知数据表: {name}")
    path = os.path.join(DATA_DIR, fn)
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    _tables[name] = rows
    return rows


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


def _issn_set(s: str) -> set[str]:
    """从 '0007-9235/1542-4863' 或单 ISSN 字段提取去掉连字符的 ISSN 集合。"""
    out = set()
    for part in (s or "").replace(",", "/").split("/"):
        p = re.sub(r"[^0-9Xx]", "", part)
        if len(p) == 8:
            out.add(p.upper())
    return out


def _row_issns(row: dict[str, str]) -> set[str]:
    out = set()
    for k, v in row.items():
        if v and ("ISSN" in k.upper()):
            out |= _issn_set(v)
    return out


# 可参与「精确匹配」的刊名类字段（避免出版社/网址等字段造成误命中）
_NAME_FIELDS = ("Journal", "刊物名称", "刊名", "中文刊名", "会议缩写")


def find_rows(table: str, query: str, limit: int = 20, strict: bool = False) -> list[dict[str, str]]:
    """在指定表中查找期刊：精确名 → ISSN → 刊名类字段精确（→ 子串 → 模糊）。
    strict=True 时不做子串与模糊匹配，只返回确定性命中（供跨表全库查询使用）。"""
    rows = _load(table)
    q = query.strip()
    qn = _norm(q)
    q_issn = _issn_set(q)

    def _nameval(r: dict[str, str]) -> str:
        for f in _NAME_FIELDS:
            v = (r.get(f) or "").strip()
            if v:
                return v
        return ""

    # 1) 精确匹配（刊名类字段，不区分大小写）
    exact = [r for r in rows if _norm(_nameval(r)) == qn]
    if exact:
        return exact
    # 2) ISSN 精确匹配
    if q_issn:
        hits = [r for r in rows if _row_issns(r) & q_issn]
        if hits:
            return hits
    # 3) 刊名类字段逐一精确（如中文刊名）
    alt = [r for r in rows
           if any(_norm(v) == qn for k, v in r.items()
                  if v and k in _NAME_FIELDS and k != _nameval(r))]
    if alt:
        return alt
    if strict:
        return []
    # 4) 子串匹配（大小写不敏感）
    sub = [r for r in rows if qn in _norm(r.get("Journal") or r.get("刊物名称") or "")]
    # 中文刊名也参与子串
    sub += [r for r in rows
            if qn and any(k in ("刊名", "中文刊名") and qn in _norm(v)
                          for k, v in r.items() if v)]
    # 去重保序
    seen, uniq = set(), []
    for r in sub:
        key = id(r)
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    if uniq:
        return uniq[:limit]
    # 5) difflib 模糊匹配
    names = [(i, _norm(r.get("Journal") or r.get("刊物名称") or "")) for i, r in enumerate(rows)]
    close = difflib.get_close_matches(qn, [n for _, n in names if n], n=limit, cutoff=0.75)
    close_set = set(close)
    return [r for i, r in enumerate(rows) if names[i][1] in close_set][:limit]


def _fmt_row(row: dict[str, str], fields: list[tuple[str, str]]) -> str:
    lines = []
    for key, label in fields:
        v = (row.get(key) or "").strip()
        if v:
            lines.append(f"- {label}: {v}")
    return "\n".join(lines)


def _cas_fields() -> list[tuple[str, str]]:
    # 两代格式字段略不同，取并集展示
    base = [("Journal", "期刊名"), ("年份", "年份"), ("ISSN/EISSN", "ISSN/EISSN"),
            ("ISSN", "ISSN"), ("Web of Science", "数据库"),
            ("大类", "大类学科"), ("大类分区", "大类分区"), ("Top", "Top 期刊")]
    for i in range(1, 7):
        base.append((f"小类{i}", f"小类{i}"))
        base.append((f"小类{i}分区", f"小类{i}分区"))
    base += [("Review", "综述期刊"), ("Open Access", "OA 期刊"),
             ("标注", "标注"), ("OA Journal Index（OAJ）", "OAJ 收录")]
    return base


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP("showjcr")


@mcp.tool()
def list_data_sources() -> str:
    """列出所有可查询的数据表：名称、年份、行数、内容说明。"""
    lines = ["# ShowJCR 数据源一览\n"]
    for y, (_, desc) in sorted(CAS_FILES.items()):
        lines.append(f"- cas{y}（中科院分区{y}）: {len(_load(f'cas{y}'))} 行 — {desc}")
    for y, (_, desc) in sorted(JCR_FILES.items()):
        lines.append(f"- jcr{y}（JCR{y}）: {len(_load(f'jcr{y}'))} 行 — {desc}")
    for y, (_, desc) in sorted(WARNING_FILES.items()):
        lines.append(f"- warn{y}（国际预警{y}）: {len(_load(f'warn{y}'))} 行 — {desc}")
    lines.append(f"- xr（新锐2026）: {len(_load('xr'))} 行 — {XR_FILE[1]}")
    lines.append(f"- xrconf（新锐2026会议）: {len(_load('xrconf'))} 行 — {XR_CONF_FILE[1]}")
    lines.append(f"- ccf（CCF2026）: {len(_load('ccf'))} 行 — {CCF_FILE[1]}")
    lines.append(f"- ccft（CCF-T 2025）: {len(_load('ccft'))} 行 — {CCFT_FILE[1]}")
    lines.append(f"\n数据目录: {DATA_DIR}")
    return "\n".join(lines)


@mcp.tool()
def query_cas_partition(journal: str, year: int = 2025) -> str:
    """查询中科院分区表。journal 支持英文刊名（不区分大小写）、ISSN（可含/分隔双 ISSN）、
    中文刊名或模糊关键词。year 可选 2021/2022/2023/2025。返回大类分区、Top 标记、小类分区等。"""
    if year not in CAS_FILES:
        return f"暂无 {year} 年中科院分区数据。可用年份: {sorted(CAS_FILES)}"
    hits = find_rows(f"cas{year}", journal)
    if not hits:
        return f"在中科院分区表 {year} 中未找到「{journal}」。可先用 search_journal 模糊检索。"
    out = [f"## 中科院分区表 {year}：命中 {len(hits)} 条\n"]
    for r in hits[:5]:
        out.append(_fmt_row(r, _cas_fields()))
        out.append("")
    return "\n".join(out)


@mcp.tool()
def query_jcr(journal: str, year: int = 2025) -> str:
    """查询 JCR 影响因子数据（2020–2025）。返回 IF、JCI 学科分类、各学科 Q 分区与排名。"""
    if year not in JCR_FILES:
        return f"暂无 {year} 年 JCR 数据。可用年份: {sorted(JCR_FILES)}"
    hits = find_rows(f"jcr{year}", journal)
    if not hits:
        return f"在 JCR {year} 中未找到「{journal}」。"
    out = [f"## JCR {year}：命中 {len(hits)} 条\n"]
    for r in hits[:5]:
        lines = [f"### {r.get('Journal', '')}"]
        lines.append(f"- ISSN: {r.get('ISSN', '')} / EISSN: {r.get('EISSN', '')}")
        lines.append(f"- 数据库: {r.get('Web of Science', '')}")
        lines.append(f"- 影响因子 IF({year}): {r.get(f'IF({year})', '')}")
        for i in range(1, 7):
            cat = (r.get(f"Category_{i}") or "").strip()
            if not cat:
                continue
            q = r.get(f"IF Quartile({year})_{i}", "")
            rank = r.get(f"IF Rank({year})_{i}", "")
            lines.append(f"- 学科 {i}: {cat} | 分区 {q} | 排名 {rank}")
        out.append("\n".join(lines))
        out.append("")
    return "\n".join(out)


@mcp.tool()
def query_xinrui(journal: str) -> str:
    """查询新锐期刊分区表 2026（期刊版）。返回大类新锐分区、Top 标记、预警标记、
    出版机构、数据库等。若需会议版请用 query_xinrui_conference。"""
    hits = find_rows("xr", journal)
    if not hits:
        return f"在新锐分区表 2026 中未找到「{journal}」。"
    out = [f"## 新锐期刊分区表 2026：命中 {len(hits)} 条\n"]
    for r in hits[:5]:
        lines = [f"### {r.get('Journal', '')}（{r.get('刊名', '')}）"]
        for key, label in [("年份", "年份"), ("预警标记", "预警标记"), ("ISSN", "ISSN"),
                           ("EISSN", "EISSN"), ("CN", "CN 号"), ("出版机构", "出版机构"),
                           ("语种", "语种"), ("数据库", "数据库"), ("标注", "标注"),
                           ("大类中文名", "大类学科"), ("大类新锐分区", "大类新锐分区"),
                           ("Top", "Top"), ("大类2中文名", "大类2学科"),
                           ("大类2新锐分区", "大类2新锐分区"), ("小类1中文名", "小类1"),
                           ("小类1新锐分区", "小类1新锐分区")]:
            v = (r.get(key) or "").strip()
            if v and v != "—":
                lines.append(f"- {label}: {v}")
        out.append("\n".join(lines))
        out.append("")
    return "\n".join(out)


@mcp.tool()
def query_xinrui_conference(abbrev: str = "") -> str:
    """查询新锐分区 2026 会议版。abbrev 传会议缩写或名称关键词（如 ACL、NeurIPS）；
    留空返回全部会议列表（量小）。"""
    rows = _load("xrconf")
    if abbrev.strip():
        q = _norm(abbrev)
        hits = [r for r in rows
                if q in _norm(r.get("会议缩写", "")) or q in _norm(r.get("Journal", ""))]
    else:
        hits = rows
    if not hits:
        return f"未找到会议「{abbrev}」。"
    out = [f"## 新锐分区 2026 会议版：命中 {len(hits)} 条\n"]
    for r in hits[:30]:
        out.append(f"- **{r.get('会议缩写', '')}** {r.get('Journal', '')} | 分区 {r.get('分区', '')} | Top: {r.get('Top', '')} | {r.get('会议网站', '')}")
    return "\n".join(out)


@mcp.tool()
def query_ccf(query: str) -> str:
    """查询 CCF 推荐国际学术会议和期刊目录 2026。query 支持刊物简称（如 JACM、ACL）、
    全称、领域关键词（如 人工智能）。返回领域、推荐类型（A/B/C 类）、刊物/会议、网址。"""
    hits = find_rows("ccf", query)
    if not hits:
        # 回退：按领域 / 出版社子串匹配（如「人工智能」「ACM」）
        qn = _norm(query)
        rows = _load("ccf")
        hits = [r for r in rows
                if qn in _norm(r.get("领域", "")) or qn in _norm(r.get("出版社", ""))]
    if not hits:
        return f"在 CCF 2026 推荐目录中未找到「{query}」。可按领域检索，如：人工智能、网络与信息安全、体系结构。"
    out = [f"## CCF 推荐目录 2026：命中 {len(hits)} 条\n"]
    for r in hits[:10]:
        lines = [f"### {r.get('刊物名称', '')} — {r.get('Journal', '')}"]
        for key, label in [("年份", "年份"), ("出版社", "出版社"), ("领域", "领域"),
                           ("CCF推荐类别（国际学术刊物/会议）", "类别"),
                           ("CCF推荐类型", "推荐等级"), ("网址", "网址")]:
            v = (r.get(key) or "").strip()
            if v:
                lines.append(f"- {label}: {v}")
        out.append("\n".join(lines))
        out.append("")
    return "\n".join(out)


@mcp.tool()
def query_ccft(journal: str = "") -> str:
    """查询计算领域高质量科技期刊分级目录 2025（T1/T2/T3）。
    journal 传中文刊名或英文刊名；留空返回按 T 分区分组的全部期刊（共 60+ 本）。"""
    rows = _load("ccft")
    if journal.strip():
        hits = find_rows("ccft", journal)
    else:
        hits = rows
    if not hits:
        return f"在 CCF-T 2025 目录中未找到「{journal}」。"
    out = [f"## 计算领域高质量科技期刊分级目录 2025：命中 {len(hits)} 条\n"]
    for r in hits[:80]:
        out.append(f"- **{r.get('中文刊名', '')}** / {r.get('Journal', '')} | "
                   f"CN: {r.get('CN号', '')} | {r.get('CCF推荐类别', '')} | "
                   f"T 分区: {r.get('T分区', '')} | 主办: {r.get('主办单位', '')}")
    return "\n".join(out)


@mcp.tool()
def query_warning_list(journal: str = "", year: int = 2025) -> str:
    """查询国际期刊预警名单。journal 传刊名或 ISSN 可查具体期刊是否被预警；
    留空返回该年度全部预警期刊（每年几十条）。year 可选 2020/2021/2023/2024/2025。
    注意：2024 年起不再分预警等级，改为预警原因（如「论文工厂」「引用操纵」）。"""
    if year not in WARNING_FILES:
        return f"暂无 {year} 年预警名单。可用年份: {sorted(WARNING_FILES)}"
    rows = _load(f"warn{year}")
    reason_col = [c for c in rows[0] if c != "Journal"][0] if rows else ""
    if journal.strip():
        hits = find_rows(f"warn{year}", journal)
    else:
        hits = rows
    if not hits:
        return f"「{journal}」不在 {year} 年国际预警名单中（该名单共 {len(rows)} 条）。"
    out = [f"## 国际预警期刊名单 {year}：命中 {len(hits)} 条（全表 {len(rows)} 条）\n"]
    for r in hits[:50]:
        out.append(f"- {r.get('Journal', '')} | {reason_col}: {r.get(reason_col, '')}")
    return "\n".join(out)


@mcp.tool()
def query_all(journal: str) -> str:
    """一键查询某期刊在全部数据源中的记录：中科院分区（各年份）、JCR 影响因子（各年份）、
    新锐分区 2026、CCF 2026、CCF-T 2025、历年国际预警名单。适合对一本期刊做全面体检。
    全库体检只做严格匹配（刊名精确/ISSN/中文刊名），避免关键词误命中无关期刊。"""
    sections = []

    for y in sorted(CAS_FILES):
        hits = find_rows(f"cas{y}", journal, strict=True)
        if hits:
            r = hits[0]
            small = "; ".join(f"{r.get(f'小类{i}','').strip()} {r.get(f'小类{i}分区','').strip()}"
                              for i in range(1, 7) if (r.get(f"小类{i}") or "").strip())
            sections.append(f"**中科院分区 {y}**：大类 {r.get('大类','')} {r.get('大类分区','')}，"
                            f"Top: {r.get('Top','') or '—'}" + (f"；小类：{small}" if small else ""))
    for y in sorted(JCR_FILES):
        hits = find_rows(f"jcr{y}", journal, strict=True)
        if hits:
            r = hits[0]
            ifv = (r.get(f"IF({y})") or "").strip()
            if not ifv:
                continue
            cat1 = (r.get("Category_1") or "").strip()
            q1 = (r.get(f"IF Quartile({y})_1") or "").strip()
            part = f"IF {ifv}"
            if cat1 or q1:
                part += f"，学科 {cat1} 分区 {q1}".replace("学科  分区 ", "")
            sections.append(f"**JCR {y}**：{part}")
    hits = find_rows("xr", journal, strict=True)
    if hits:
        r = hits[0]
        warn = (r.get("预警标记") or "").strip()
        sections.append(f"**新锐分区 2026**：大类 {r.get('大类中文名','')} "
                        f"{r.get('大类新锐分区','')}，Top: {r.get('Top','')}"
                        + (f"，⚠ 预警标记: {warn}" if warn and warn != "—" else ""))
    hits = find_rows("ccf", journal, strict=True)
    if hits:
        r = hits[0]
        sections.append(f"**CCF 2026**：{r.get('刊物名称','')} {r.get('Journal','')}，"
                        f"领域 {r.get('领域','')}，{r.get('CCF推荐类型','')}")
    hits = find_rows("ccft", journal, strict=True)
    if hits:
        r = hits[0]
        sections.append(f"**CCF-T 2025**：{r.get('中文刊名','')}，T 分区 {r.get('T分区','')}")
    for y in sorted(WARNING_FILES):
        hits = find_rows(f"warn{y}", journal, strict=True)
        if hits:
            r = hits[0]
            reason_col = [c for c in r if c != "Journal"][0]
            sections.append(f"**国际预警 {y}**：在名单中，{reason_col}: {r.get(reason_col,'')}")

    if not sections:
        return f"「{journal}」在所有数据源中均未命中。可先用 search_journal 模糊检索确认刊名。"
    return f"# 「{journal}」全库体检结果\n\n" + "\n\n".join(sections)


@mcp.tool()
def search_journal(keyword: str, source: str = "cas2025", limit: int = 20) -> str:
    """模糊检索期刊名，返回候选列表（刊名 + 关键分区/等级字段），用于确认准确刊名后再细查。
    source 可选：cas2021/2022/2023/2025、jcr2020–2025、xr、ccf、ccft、warn2020–2025。"""
    valid = ([f"cas{y}" for y in CAS_FILES] + [f"jcr{y}" for y in JCR_FILES]
             + [f"warn{y}" for y in WARNING_FILES] + ["xr", "xrconf", "ccf", "ccft"])
    if source not in valid:
        return f"source 应为以下之一: {', '.join(valid)}"
    rows = _load(source)
    qn = _norm(keyword.strip())
    if not qn:
        return "请提供检索关键词。"

    def _all_names(r: dict[str, str]) -> str:
        return " ".join(_norm(v) for k, v in r.items() if k in _NAME_FIELDS and v)

    # 搜索场景直接做子串匹配（刊名类字段），精确命中也算子串的特例
    hits = [r for r in rows if qn in _all_names(r)]
    if not hits:
        names = [_all_names(r) for r in rows]
        close = difflib.get_close_matches(qn, names, n=limit, cutoff=0.75)
        close_set = set(close)
        hits = [r for r in rows if _all_names(r) in close_set]
    if not hits:
        return f"在 {source} 中未找到与「{keyword}」相近的条目。"
    out = [f"## 在 {source} 中检索「{keyword}」：{len(hits)} 条候选\n"]
    for r in hits[:limit]:
        name = r.get("Journal") or r.get("刊物名称") or ""
        extra = ""
        if "大类分区" in r:
            extra = f" | {r.get('大类','')} {r.get('大类分区','')}"
        elif "T分区" in r:
            extra = f" | T{r.get('T分区','')}"
        elif "CCF推荐类型" in r:
            extra = f" | {r.get('CCF推荐类型','')} {r.get('领域','')}"
        elif source == "xr":
            extra = f" | {r.get('大类中文名','')} {r.get('大类新锐分区','')}"
        elif source.startswith("warn"):
            rc = [c for c in r if c != "Journal"][0]
            extra = f" | {r.get(rc,'')}"
        elif source.startswith("jcr"):
            y = source[3:]
            extra = f" | IF {r.get(f'IF({y})','')} {r.get(f'IF Quartile({y})_1','')}"
        zh = r.get("刊名", "") or r.get("中文刊名", "")
        out.append(f"- **{name}**" + (f"（{zh}）" if zh else "") + extra)
    return "\n".join(out)


if __name__ == "__main__":
    mcp.run(transport="stdio")
