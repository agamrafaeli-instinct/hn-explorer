# Honor: quality criteria and score rules

Spec for issue #134, epic #133. Decision (2026-10-10): quality means sharp, interesting, fresh, relevant, insightful or novel. Scoring is automatic and runs daily with the daily run. A bad score flags and queues. It never blocks a deploy, a card or other work. Card files, thresholds and verdicts are never changed by a score; an upgrade is a new card with a new ID. Decision (2026-10-10): at most 5 new "needs upgrade" issues per day.

Inputs are only `hypotheses/*.json`, the data files the cards name, `stories/index.json` and `data/verdicts/log.csv`. No criterion uses a manual rating. Each criterion gives pass, fail or n/a. n/a never counts as a fail.

## Criteria

**1. Sharp.** Pass when all of these hold:
- `check.group_a` and `check.group_b` each have a label and a non-empty `indices` list.
- `check.source` is a file in the repo and `check.path` resolves to a list in it.
- `verdicts` has a supported rule and a refuted rule that each carry a numeric `when.value`, and the last rule is `else`.

**2. Interesting.** Pass when both hold:
- The card has an `audience` tag.
- A story exists for the card (listed in `stories/index.json`) with a non-empty `why`. This part is n/a until every card has a story, so it switches on when the Throughline rollout (#131) is done. Until then the criterion tests the audience tag only.

**3. Fresh.** Uses the verdict log, one row per card per day. Fail when the verdict and the confidence were identical in the last 14 logged days and the confidence is "strong". Fixed-window cards are n/a: cards whose source is `data/engineers_history.json`, `data/vcs_history.json` or `data/curious_round2.json`, and cards h135 to h149. With fewer than 14 logged days the criterion is n/a. The log began on 2026-10-09, so this is first scored on 2026-10-23.

**4. Relevant.** Pass when the card has an `audience` tag from the site's three audiences and the group A count over its rows is at least 30. The count is the sum of group A's `field`, or of its `per` field when the field name contains "points" (so points do not pass for counts).

**5. Insightful.** Pass when all of these hold:
- Group B is a different group from group A (different rows or a different field).
- The `expect` text states a number.
- The card lists at least one caveat.

**6. Novel.** Fail when an older card (a lower ID) has the same source, path, labels, fields and rows for both groups and the same verdict rules, or a title that shares 70 percent or more of its words (Jaccard, lower case, common words removed). The newer card fails, so frozen old cards never fail on this rule. Decision (2026-10-18): the same comparison with different verdict rules is a distinct test.

## Score and queue

- Score = passes divided by scored criteria (pass and fail only).
- A card needs an upgrade when any scored criterion fails.
- Queue order when more than 5 are waiting: most failing criteria first, then lowest ID. At most 5 new issues a day. A card with an open "needs upgrade" issue gets no second one.
- The issue title is `Upgrade card <card id>: <failing criteria>` and it lists the failing criteria and the rule for each.

## Check by hand on the current cards (2026-10-10)

Prototype run of the rules above on the current card files. `+` is pass and `-` is fail. Fresh is n/a for all of them today and interesting is scored on the audience tag only.

| Card | Title | sharp interesting relevant insightful novel | Group A count |
|---|---|---|---|
| h002 | HN never sleeps | sharp- interesting- relevant- insightful+ novel+ | 165843.0 |
| h013 | Engineers moved from chatbots to agents | sharp+ interesting+ relevant+ insightful+ novel+ | 15886.0 |
| h016 | React's grip is loosening | sharp+ interesting+ relevant+ insightful+ novel+ | 1181.0 |
| h105 | Neural biology: points premium | sharp+ interesting+ relevant- insightful+ novel+ | 22.0 |
| h138 | Music starts more conversations | sharp+ interesting+ relevant+ insightful+ novel+ | 2567.0 |

Over all 80 cards the same run gives these fails: interesting 8 (no audience tag), relevant 11 (those 8 plus h104, h105, h126, whose group A counts are 22, 22 and 10), sharp 1 (h002), novel 0.

## Replaced cards
Decision (2026-10-12): a new card can set `"replaces": "hNNN"`. The old card stays on the site unchanged but the scorecard no longer lists it as failing and no upgrade issue is opened for it.
