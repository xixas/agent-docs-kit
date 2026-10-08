# agent-docs-kit
Small stdlib+PyYAML tools that let coding agents keep docs honest. Local only, no remote.
`skills/docs-check/check_docs_map.py` lists docs that may be stale for a git diff (rule map + stale-value pass).
Run: `python3 skills/docs-check/check_docs_map.py --repo REPO --config REPO/.docs-map.yaml [--commit SHA] [--json]`
Tests: `python3 -m pytest -q`. Example config: `examples/aws-cdk-service.docs-map.yaml`.
`skills/agent-docs-slim/slim_check.py FILE [--repo .] [--level 2] [--json]`: section sizes, agent budgets, dead links, broken inbound anchors; exit 1 on any problem.
`skills/agent-ab-eval/run_eval.py --prompts P.yaml --a DIR --b DIR [--dry-run|--measure-one]`: A/B behaviour eval of two instruction-file versions.
