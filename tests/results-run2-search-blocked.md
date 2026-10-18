# Local eval (2026-10-18 13:14 UTC, LLM=none, CPU box)

**31/40 = 78%**, p50 0.4 s, max 7.2 s, whole run 54.7 s (dev 25/32, holdout 6/8)

| set | id | ok | sec | expected | got | source | last step |
|---|---|---|---|---|---|---|---|
| dev | v01 | ✅ | 0.1 | 2.34.2 | 2.34.2 | https://pypi.org/project/requests/ | direct:pypi |
| dev | v02 | ✅ | 0.2 | 2.5.4 | 2.5.4 | https://pypi.org/project/numpy/ | direct:pypi |
| dev | v03 | ✅ | 0.3 | 19.3.1 | 19.3.1 | https://www.npmjs.com/package/react | direct:npm |
| dev | v04 | ✅ | 0.2 | 5.3.0 | 5.3.0 | https://www.npmjs.com/package/express | direct:npm |
| dev | v05 | ✅ | 0.4 | 1.0.229 | 1.0.229 | https://crates.io/crates/serde | direct:crates |
| dev | v06 | ✅ | 0.3 | 0.40.6 | 0.40.6 | https://github.com/ollama/ollama/releases/tag/v0.40.6 | direct:github |
| dev | v07 | ✅ | 0.2 | 24.22.0 | 24.22.0 | https://endoflife.date/nodejs | direct:endoflife |
| dev | v08 | ✅ | 0.1 | 3.15.0 | 3.15.0 | https://endoflife.date/python | direct:endoflife |
| dev | v09 | ✅ | 0.3 | 6.1.2 | 6.1.2 | https://endoflife.date/django | direct:endoflife |
| dev | v10 | ✅ | 0.3 | 1.37.1 | 1.37.1 | https://endoflife.date/kubernetes | direct:endoflife |
| dev | d01 | ✅ | 0.2 | 2028-11-09 | 2028-11-09 | https://endoflife.date/postgresql | direct:endoflife |
| dev | d02 | ✅ | 0.1 | 2023-10-02 | 2023-10-02 | https://endoflife.date/python | direct:endoflife |
| dev | d03 | ✅ | 0.2 | 2026-04-23 | 2026-04-23 | https://endoflife.date/ubuntu | direct:endoflife |
| dev | u01 | ✅ | 0.9 | 3.54.1 | 3.54.1 | https://www.sqlite.org/releaselog/3_54_1.html | rule-pick |
| dev | u02 | ✅ | 0.9 | 2.56.0 | 2.56.0 | https://git-scm.com/ | rule-pick |
| dev | u03 | ✅ | 0.6 | 1.99.1 | 1.99.1 | https://rust-lang.org/ | rule-pick |
| dev | u04 | ✅ | 2.6 | 1.27.2 | 1.27.2 | https://go.dev/dl/ | rule-pick |
| dev | u05 | ✅ | 0.7 | 800-829-1040 | 800-829-1040 | https://www.irs.gov/help/report-fraud/tax-return-preparer-misconduct | rule-pick |
| dev | p01 | ❌ | 2.4 | 800-221-1212 |  |  | pages:8 |
| dev | p02 | ❌ | 7.2 | 800-433-7300 |  |  | pages:2 |
| dev | p03 | ❌ | 6.2 | 800-864-8331 | +1-800-864-8331 | https://www.wikidata.org/wiki/Q174769 | direct-lowconf:wikidata |
| dev | p04 | ❌ | 3.1 | 800-275-2273 | 877-255-5923 | https://www.apple.com/ | rule-pick |
| dev | p05 | ❌ | 2.4 | 800-435-9792 | +1-800-435-9792 | https://www.wikidata.org/wiki/Q503308 | direct-lowconf:wikidata |
| dev | p06 | ❌ | 6.7 | 800-872-7245 | 877-255-5923 | https://www.apple.com/iphone/ | rule-pick |
| dev | f01 | ✅ | 0.1 | Lisa Su | Lisa Su | https://www.wikidata.org/wiki/Q128896 | direct:wikidata |
| dev | f02 | ✅ | 1.0 | 1993 | 1993 | https://www.wikidata.org/wiki/Q182477 | direct:wikidata |
| dev | f03 | ✅ | 0.3 | Santa Clara | Santa Clara | https://www.wikidata.org/wiki/Q128896 | direct:wikidata |
| dev | f04 | ✅ | 1.4 | Canberra | Canberra | https://www.wikidata.org/wiki/Q408 | direct:wikidata |
| dev | f05 | ✅ | 1.1 | Christopher Nolan | Christopher Nolan | https://www.wikidata.org/wiki/Q25188 | direct:wikidata |
| dev | f06 | ✅ | 1.0 | 1991 | 1991 | https://www.wikidata.org/wiki/Q28865 | direct:wikidata |
| dev | n01 | ❌ | 6.2 |  | 877-255-5923 | https://www.apple.com/iphone/ | rule-pick |
| dev | n02 | ✅ | 0.3 |  |  |  | direct:registry-miss |
| holdout | h01 | ✅ | 0.2 | 3.0.6 | 3.0.6 | https://pypi.org/project/pandas/ | direct:pypi |
| holdout | h02 | ✅ | 0.2 | 4.18.1 | 4.18.1 | https://www.npmjs.com/package/lodash | direct:npm |
| holdout | h03 | ✅ | 0.3 | 0.32.0 | 0.32.0 | https://github.com/vllm-project/vllm/releases/tag/v0.32.0 | direct:github |
| holdout | h04 | ✅ | 0.3 | 8.5.11 | 8.5.11 | https://endoflife.date/php | direct:endoflife |
| holdout | h05 | ✅ | 1.2 | Satya Nadella | Satya Nadella | https://www.wikidata.org/wiki/Q2283 | direct:wikidata |
| holdout | h06 | ✅ | 0.9 | 2003 | 2003 | https://www.wikidata.org/wiki/Q478214 | direct:wikidata |
| holdout | h07 | ❌ | 3.6 | 800-937-8997 | 844-392-3495 | https://www.t-mobile.com/?msockid=151f91c2bf3f64551ba18634be936590 | rule-pick |
| holdout | h08 | ❌ | 0.4 | 7.2.11 | 7.2 | https://cdn.kernel.org/pub/linux/kernel/v7.x/ChangeLog-7.2.11 | rule-pick |
