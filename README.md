# ShowJCR MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[中文说明](README.zh-CN.md)

A [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server for querying journal evaluation data:

- **CAS Journal Ranking** (中科院分区表, 2021 / 2022 / 2023 / 2025)
- **JCR Impact Factor** (2020–2025)
- **XinRui Journal Partition 2026** (新锐分区, journal & conference editions)
- **CCF Recommended Catalog of International Conferences and Journals 2026**
- **CCF-T Ranking of High-Quality Sci-Tech Journals in Computing 2025** (T1/T2/T3)
- **International Warning Journal List** (2020 / 2021 / 2023 / 2024 / 2025)

The data files come from the open-source project [hitfyd/ShowJCR](https://github.com/hitfyd/ShowJCR). This server wraps them as MCP tools so that any MCP-capable AI client (WorkBuddy, Claude Desktop, Cursor, etc.) can query them directly.

## Tools

| Tool | Description |
|---|---|
| `query_cas_partition` | CAS partition (major/minor category partition, Top flag, rank) |
| `query_jcr` | JCR impact factor, subject quartiles and ranks |
| `query_xinrui` / `query_xinrui_conference` | XinRui partition 2026 (journals / conferences) |
| `query_ccf` | CCF recommended catalog (by abbreviation, full name, or research area) |
| `query_ccft` | CCF-T high-quality journals T1/T2/T3 |
| `query_warning_list` | International warning journal list (warning reasons since 2024) |
| `query_all` | Full checkup: aggregate a journal's records across all data sources |
| `recommend_journals` | **Reverse journal finder**: recommend journals from paper topic keywords (word-boundary matching for English, substring for Chinese), ranked by keyword hits and partition |
| `search_journal` | Fuzzy search for journal name candidates |
| `list_data_sources` | List all data tables with row counts |

Name matching supports English journal names (case-insensitive), ISSN (including dual ISSN), Chinese journal names, and fuzzy keywords. The full checkup (`query_all`) uses strict matching to avoid false keyword hits.

WoS index type (SCIE / ESCI / SSCI / AHCI, including dual indexing such as `SSCI;SCIE`) is included in CAS partition, JCR, and XinRui outputs wherever the underlying data provides it.

## Installation

```bash
# 1. Install dependencies (Python 3.10+ required)
pip install "mcp>=1.0,<2"

# 2. Download data files into ./data
python scripts/fetch_data.py
```

> Pin to mcp 1.x — version 2.x introduced breaking API changes (FastMCP was renamed).

## Configuration

Add the server to your MCP client's config file (the data directory can also be set via the `SHOWJCR_DATA_DIR` environment variable):

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

## Usage Examples

- "What CAS partition is Nature in? Is it a Top journal?" → `query_cas_partition("Nature", 2025)`
- "Is CANCERS on the warning list?" → `query_warning_list("CANCERS")`
- "What CCF rank does ACL have?" → `query_ccf("ACL")`
- "Full checkup for Nature" → `query_all("Nature")`
- "My abstract is about cancer immunotherapy biomarkers — where should I submit?" → extract keywords from the abstract (e.g. `cancer immunotherapy biomarker`), call `recommend_journals(keywords, "cas2025")` for candidates, then vet the shortlist with `query_all`

## Data Notice & Copyright

This repository does **not** distribute the data files. All data copyrights belong to their respective institutions:

- CAS Journal Ranking: National Science Library, Chinese Academy of Sciences
- JCR: Clarivate Analytics
- CCF Recommended Catalog / CCF-T Ranking: China Computer Federation (CCF)
- International Warning Journal List: Journal Partition Table Team, National Science Library, CAS

`scripts/fetch_data.py` merely mirrors the publicly released CSV files from [hitfyd/ShowJCR](https://github.com/hitfyd/ShowJCR) (GPL-3.0). When using query results produced by this service, please comply with the terms of the respective data institutions; verify authorization yourself before any commercial use.

## License

The code is released under the [MIT License](LICENSE).

---

## Buy me a coffee

ShowJCR MCP Server is an open-source project I develop and maintain in my spare time, free forever.

If it helped you look up journal rankings, pick a venue for your paper, or saved you the trouble of
wrestling the data files yourself - consider buying me a coffee (9.9 CNY is enough). Every bit of
support goes straight into new features and bug fixes.

<p align="center">
  <img src="donate.jpg" alt="Buy me a coffee" width="280">
</p>

<p align="center"><i>Leave a note with your donation about the feature you want most - I prioritize those ;)</i></p>

**Can't donate?** Starring the repo, opening an Issue, or sharing it with someone who needs it helps just as much!
