# Initial source baseline

Recorded: 2026-09-28. These six files were already present in the project root.
Original and destination paths are identical; no files were renamed or replaced.
No earlier repository history was available. Original working-file bytes are
preserved. Git normalizes CRLF to LF in stored text; both SHA-256 values are shown.
Ownership and third-party license provenance remain unverified.

The existing workspace value-suppressing scanner (version 1) reported zero
findings across these six files. This is a heuristic review aid, not proof that
secrets are absent. Static inventory found four Pine v6 indicator declarations;
no Pine code was executed and no full compile-safety review is claimed.

| Path | Original SHA-256 | LF-normalized SHA-256 |
| --- | --- | --- |
| `630 First Candle Marker.pine` | `15264f5cb7d8ae2f98ed16492a240608fbdf430efe12ed88d560d80812425f48` | `59c88201390399052e40a5a0abf2822395839dc96309b2c06e1cfb5e2a710039` |
| `CCIEMA_percentile_extremes.pine` | `ef3dbbe7b5e89b03adde8c38edaaaccf9bad70bd4d51ea088c07a76f4c3e2aea` | `ef3dbbe7b5e89b03adde8c38edaaaccf9bad70bd4d51ea088c07a76f4c3e2aea` |
| `ChatGPT_TradingView_Project_Prompt.md` | `e281c83bbea536b66f5a145f98203da08856deabe2e6fe728618075c26fb3a44` | `512be0e3131539a04995ac65d8625c2374b0b2a720579598bed5126ffc044e17` |
| `ChatGPT_Trading_Project_Prompt.md` | `e281c83bbea536b66f5a145f98203da08856deabe2e6fe728618075c26fb3a44` | `512be0e3131539a04995ac65d8625c2374b0b2a720579598bed5126ffc044e17` |
| `Price_Response_To_Colume.pine` | `58dc9b39e3faaa51626ec4e28ad57ed2cecce4c4d24092ae95f04b37371b3e21` | `7a33f6ba7f9578d1f21bcddbebc8144903d095c288d7ad19a43de5c474a37f29` |
| `Volume_Outlier_Profile.pine` | `7b8471799e514f957556c4fba6ea07972f1b5e7e97908bee7482a7ac1cb10552` | `7b8471799e514f957556c4fba6ea07972f1b5e7e97908bee7482a7ac1cb10552` |

The two prompt templates are byte-identical and intentionally retained. This
bootstrap adds repository metadata/documentation only; indicator behavior is unchanged.
