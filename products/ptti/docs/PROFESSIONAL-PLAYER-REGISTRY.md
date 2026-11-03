# Professional player registry — verification snapshot

**Checked:** 2026-10-05 UTC 18:30
**Ranking:** ITTF men's singles, 2026 week 41, published 2026-10-05
**Registry seed:** `data/professional/registry.json` (`professional-foundation-3`)

This is a sourced initial registry, not a complete player database. Ranking is a dated snapshot, not a live value. ITTF IDs below came from the official WTT player search/profile data where available. Chinese display names are editorial translations/transliterations; the canonical identity field is the official English name. Missing information is left blank.

## Current elite snapshot

| Rank | Athlete | Association | ITTF ID | Points | Profile |
|---:|---|---|---:|---:|---|
| 1 | 松岛辉空 · Sora MATSUSHIMA | JPN | 135996 | 6,930 | [WTT](https://www.worldtabletennis.com/player/135996/Sora-MATSUSHIMA) |
| 2 | 菲利克斯·勒布伦 · Felix LEBRUN | FRA | 135977 | 6,379 | [WTT](https://www.worldtabletennis.com/player/135977/Felix-LEBRUN) |
| 3 | 张本智和 · Tomokazu HARIMOTO | JPN | 123980 | 6,363 | [WTT](https://www.worldtabletennis.com/player/123980/Tomokazu-HARIMOTO) |
| 4 | 王楚钦 · WANG Chuqin | CHN | 121558 | 6,157 | [WTT](https://www.worldtabletennis.com/player/121558/WANG-Chuqin) |
| 5 | 特鲁斯·莫雷加德 · Truls MOREGARD | SWE | 122044 | 5,805 | [WTT](https://www.worldtabletennis.com/player/122044/Truls-MOREGARD) |
| 6 | 林昀儒 · LIN Yun-Ju | TPE | 121582 | 4,405 | [WTT](https://www.worldtabletennis.com/player/121582/LIN-Yun-Ju) |
| 7 | 雨果·卡尔德拉诺 · Hugo CALDERANO | BRA | 115641 | 4,240 | [WTT](https://www.worldtabletennis.com/player/115641/Hugo-CALDERANO) |
| 8 | 艾利克西·勒布伦 · Alexis LEBRUN | FRA | 132992 | 3,720 | [WTT](https://www.worldtabletennis.com/player/132992/Alexis-LEBRUN) |
| 9 | 林诗栋 · LIN Shidong | CHN | 137237 | 3,642 | [WTT](https://www.worldtabletennis.com/player/137237/LIN-Shidong) |
| 10 | 邱党 · Dang QIU | GER | 114715 | 3,450 | [WTT](https://www.worldtabletennis.com/player/114715/Dang-QIU) |

The ranking source is the [official WTT mobile API snapshot](https://mobileappapi.worldtabletennis.com/api/cms/GetRankingIndividuals?TopN=200&RankingYear=2026&RankingMonth=10&RankingWeek=41&SubEventCode=MS), filtered to senior men's singles. The official [ITTF ranking archive](https://www.ittf.com/ittf-table-tennis-world-ranking/) identifies week 41 as published October 5. A same-day [ITTF report](https://www.ittf.com/2026/10/05/sora-matsushima-becomes-first-non-chinese-world-no-1-since-2018/) independently reports Matsushima's move to world number one.

## Priority and historical references

`TTI_PRIORITY` is a user-editable data group. Its initial membership is Wang Chuqin, Tomokazu Harimoto, Sora Matsushima, Felix Lebrun, Truls Moregard, Lin Shidong, Fan Zhendong, Ma Long, and Zhang Jike. Lin Yun-Ju is in the current elite snapshot but is not in the initial priority set.

Fan Zhendong and Ma Long are included as historical/champion references. ITTF reports that both withdrew from the ITTF World Rankings; the registry therefore leaves current ranking, official profile ID, and profile URL null. Their Chinese names are the familiar athlete names supplied for this reference list; no unsupported profile details are inferred. Zhang Jike's WTT profile returns ITTF ID 110553 and birth date 1988-02-16; no current ranking is asserted.

The registry also contains Jonathan Groth, Dimitrij Ovtcharov, and Yukiya Uda because they are opponents in the seeded match records. This brings the complete initial directory to 16 distinct stable athlete IDs. Each available profile has its own official WTT profile URL and retrieval timestamp in the manifest. The legacy references cite official [ITTF ranking withdrawal coverage](https://www.ittf.com/2025/01/01/ma-long-fan-zhendong-and-chen-meng-withdraw-from-ittf-world-rankings/). Ranking rows link to the official WTT ranking API source.

## Fields still unavailable

Playing hand and grip are null for every seeded athlete. WTT player IDs were not separately returned by the API response used for this pass and remain null. Height, club, and coach were not seeded. Fan Zhendong and Ma Long are not assigned unsupported IDs, dates of birth, current status, or ranking. Event dates are null when the result source used for a match did not establish an exact date.

## Refresh policy

Add a new ranking week as a new source and new immutable history rows. Never rewrite an earlier week to reflect a later ranking. The frontend reads the repository API and labels the week/date; it does not embed ranking numbers.

The official ITTF results page records the WANG Chuqin–Sora Matsushima men's singles final at the Macao 2026 World Cup on **2026-04-05**. This date was added as an append-only verified enrichment; the original seeded match payload remains unchanged. [Official ITTF results](https://worldcupresults.ittf.com/eventInfo?eventId=3379&selectedTab=Draws&subEvt=MSINGLES)
