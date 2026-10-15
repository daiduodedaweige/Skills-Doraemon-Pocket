# Protocol search

Run `python3 tools/search_kb.py "query" --json --top-k 8` from this skill directory. Use repeatable `--section ID` to filter or `--list-sections` to list sections. JSON results include `text`, `source_file`, `source_page`, `matched_rules`, `matched_flows`, and `score`. Scores rank candidate evidence, not protocol truth; verify normative claims in `source/`.
