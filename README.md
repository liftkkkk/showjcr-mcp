# ShowJCR MCP Server

一个 [Model Context Protocol](https://modelcontextprotocol.io) (MCP) 服务器，用于查询期刊评价数据：

- **中科院分区表**（2021 / 2022 / 2023 / 2025）
- **JCR 影响因子**（2020–2025）
- **新锐期刊分区表 2026**（期刊版 + 会议版）
- **CCF 推荐国际学术会议和期刊目录 2026**
- **计算领域高质量科技期刊分级目录 2025**（T1/T2/T3）
- **国际期刊预警名单**（2020 / 2021 / 2023 / 2024 / 2025）

数据文件来自开源项目 [hitfyd/ShowJCR](https://github.com/hitfyd/ShowJCR)，本服务将其封装为 MCP 工具，供任意支持 MCP 的 AI 客户端（WorkBuddy、Claude Desktop、Cursor 等）直接查询。

## 功能

| 工具 | 说明 |
|---|---|
| `query_cas_partition` | 查中科院分区（大类/小类分区、Top 标记、排名） |
| `query_jcr` | 查 JCR 影响因子与学科 Q 分区、排名 |
| `query_xinrui` / `query_xinrui_conference` | 查新锐分区 2026（期刊 / 会议） |
| `query_ccf` | 查 CCF 推荐目录（简称、全称、领域均可） |
| `query_ccft` | 查 CCF-T 高质量期刊 T1/T2/T3 |
| `query_warning_list` | 查国际预警期刊名单（2024 起为预警原因） |
| `query_all` | 一键全库体检：一本期刊在全部数据源的记录汇总 |
| `recommend_journals` | **反向选刊**：按论文主题关键词推荐期刊（英文按词边界匹配、中文子串），按命中数与分区排序 |
| `search_journal` | 模糊检索刊名候选 |
| `list_data_sources` | 列出全部数据表及行数 |

刊名匹配支持：英文刊名（不区分大小写）、ISSN（含双 ISSN）、中文刊名、模糊关键词。
全库体检（`query_all`）采用严格匹配，避免关键词误命中。

## 安装

```bash
# 1. 安装依赖（需要 Python 3.10+）
pip install "mcp>=1.0,<2"

# 2. 下载数据文件到 ./data 目录
python scripts/fetch_data.py
```

> mcp 2.x 起接口有破坏性变更（FastMCP 改名），请固定使用 1.x。

## 配置

在 MCP 客户端的配置文件中添加（数据目录也可用环境变量 `SHOWJCR_DATA_DIR` 指定）：

```json
{
  "mcpServers": {
    "showjcr": {
      "command": "python",
      "args": ["/path/to/showjcr-mcp/server.py"],
      "env": {
        "SHOWJCR_DATA_DIR": "/path/to/showjcr-mcp/data"
      }
    }
  }
}
```

## 使用示例

- 「Nature 现在是中科院几区？Top 期刊吗？」→ `query_cas_partition("Nature", 2025)`
- 「CANCERS 是不是预警期刊？」→ `query_warning_list("CANCERS")`
- 「ACL 在 CCF 是什么等级？」→ `query_ccf("ACL")`
- 「给 Nature 做个全面体检」→ `query_all("Nature")`
- 「我的论文摘要讲肿瘤免疫治疗标志物，投什么期刊？」→ 先从摘要提取关键词（如 `cancer immunotherapy biomarker`），再 `recommend_journals(keywords, "cas2025")` 拿候选，最后对入围期刊用 `query_all` 体检

## 数据说明与版权

本仓库**不分发数据文件**。数据版权归各自机构所有：

- 中科院分区表：中国科学院文献情报中心
- JCR：Clarivate Analytics
- CCF 推荐目录 / 高质量期刊分级目录：中国计算机学会
- 国际预警期刊名单：中科院文献情报中心期刊分区表团队

`scripts/fetch_data.py` 仅从 [hitfyd/ShowJCR](https://github.com/hitfyd/ShowJCR)（GPL-3.0）转存其已公开的 CSV 文件，使用本服务产生的查询结果请遵循相应数据机构的使用条款，商业使用请自行确认授权。

## License

代码部分以 [MIT](LICENSE) 协议开源。
