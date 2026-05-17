# Royal Antwerp FC — Squad Audit & Recruitment Analysis

**Belgian Pro League · Season 2024-2025 · Attacking Unit Underperformance & Scouting**

---

## Project Overview

This notebook audits the attacking unit of Royal Antwerp FC against the rest of the Belgian Pro League. It identifies which forwards are underperforming relative to the league median, ranks them by how expendable they are to the club, and then scouts the best available young replacement using a composite performance score.

The pipeline runs entirely on CSV exports from a relational football database (FBRef match-level stats + Transfermarkt player valuations). All data loading is done via `pandas.read_csv()`, with an in-memory SQLite instance loaded for any ad-hoc SQL queries. The code is structured so that every `pd.read_csv()` call can be swapped for `pd.read_sql_query()` once a live PostgreSQL connection is available.

---

## Data Sources

| Table | Description |
|---|---|
| `player` | One row per player-season. Contains PlayerID, TeamID, name, position, age, minutes. |
| `player_stat` | Match-level statistics: xAG, xG, SCA, progressive carries/passes, dribbles. One row per player per match. |
| `squad` | Maps TeamID to club name by season. |
| `match` | Maps MatchID to season string (e.g. `2024-2025`). Used to attach a season label to every row in `player_stat`. |
| `tm_player` | Transfermarkt data: player name, position, club, market value, age by season. |

---

## Cell-by-Cell Walkthrough

### Cell 1 — Environment Setup, Data Loading & Validation

**What it does:**
Loads all five tables from CSV, creates an in-memory SQLite database, and validates that all critical columns are present and sufficiently populated.

**Key technical decisions:**

- **Season join**: `player_stat` has no Season column. The notebook joins it to the `match` table on `MatchID` to attach a season label to every stat row. In SQL this would be: `JOIN match m ON ps."MatchID" = m."MatchID"`.

- **PlayerID rotation fix**: The source data assigns players a new PlayerID each season. A naive `JOIN player_stat ON PlayerID` would silently drop most players when filtering to the current season, because the current-season PlayerID rarely matches the historical player record. The fix is to build a `pid_to_name` lookup from the full multi-season `player` table, resolve every stat row to a player name, and then aggregate by name. This is captured in `stat_by_name`.

- **`stat_by_name`**: A pre-aggregated table with one row per player for the 2024-2025 season. Metrics included are those with ≥99% non-null coverage in the current season data: xAG, xG, SCA, progressive carries, progressive passes, dribbles, shots, interceptions.

**Core aggregation (equivalent SQL):**
```sql
SELECT
    p.Player,
    SUM(ps.Min)                AS Min_played,
    SUM(ps."Expected_xAG")     AS xAG_total,
    SUM(ps."Expected_xG")      AS xG_total,
    SUM(ps."SCA_SCA")          AS SCA_total,
    SUM(ps."Carries_PrgC")     AS PrgC_total,
    SUM(ps."Passes_PrgP")      AS PrgP_total,
    SUM(ps."Take-Ons_Succ")    AS Drib_total
FROM player_stat ps
JOIN match m ON ps."MatchID" = m."MatchID"
JOIN player p ON ps."PlayerID" = p."PlayerID"
WHERE m."Season" = '2024-2025'
GROUP BY p.Player;
```
Per-90 values are then derived by dividing each total by `MIN_played / 90`.

---

### Cell 2 — Helper Functions

Defines four shared utilities used throughout:

- **`classify_pos(pos)`** — maps an FBRef position string to ATT / MID / DEF / GK. Only players with `FW` in their position string are classified as ATT. Pure midfielders (CM, DM, AM without FW) are excluded from all attacking comparisons.

- **`parse_age(age_str)`** — FBRef stores age as `23-272` (years-days). This strips the days component and returns an integer.

- **`agg_match_stats(player_ids, season)`** — aggregates `player_stat` for a given list of PlayerIDs and season. Equivalent to the SQL above but scoped to a specific subset of players.

- **`parse_value(v)`** — converts Transfermarkt value strings (`€3.50m`, `€500k`) to a numeric EUR float.

---

### Cell 3 — League-Wide ATT Underperformance Scan

**What it does:**
Computes an Underperformance Index (UI) for every club in the league, then locks onto Royal Antwerp and flags individual players who fall below acceptable thresholds.

**Step 1 — League medians:**
For all forward-tagged players with more than 300 minutes in 2024-2025, compute the median xAG/90, PrgC/90, and Drib/90 across the entire league.

**Step 2 — Team-level Underperformance Index:**
For each club, take the mean of its forwards' per-90 values and compare to the league medians:

```
UI = mean(
    (team_xAG  - median_xAG)  / median_xAG,
    (team_PrgC - median_PrgC) / median_PrgC,
    (team_Drib - median_Drib) / median_Drib
)
```

A UI of -0.15 means the club's forwards are, on average, 15% below the league median across those three metrics. Clubs with fewer than 3 forwards with stat coverage are excluded.

**Step 3 — Player-level flagging (Antwerp):**
A player is flagged if any of the following are true:
- xAG/90 < 85% of league median
- PrgC/90 < 85% of league median
- Age > 30

The 85% threshold is a deliberate buffer. It avoids flagging players who are marginally below median but still broadly acceptable, and focuses the audit on genuine underperformers.

---

### Cell 4 — Visualizations

Three charts built from the Cell 3 output:

- **Chart A**: Horizontal bar chart of all clubs ranked by UI. Antwerp is highlighted. Shows at a glance where Antwerp sits in the league.

- **Chart B**: Three side-by-side panels showing each Antwerp forward individually on xAG/90, PrgC/90, and Drib/90 with the league median as a reference line.

- **Chart C**: League-wide scatter plot of xAG/90 vs PrgC/90 for all forwards, with an OLS trendline. Antwerp's flagged players are annotated by name. This places the Antwerp forwards in the context of every forward in the league on one chart.

---

### Cell 5 — Expendability Ranking + Janssen Replacement Scouting

This cell produces two outputs.

#### Graph 1 — Expendability Score

Takes the flagged Antwerp forwards from Cell 3 and ranks them by how beneficial it would be for the club to sell them.

**Formula:**
```
Expendability = (xAG_deficit × 0.40)
              + (PrgC_deficit × 0.30)
              + (age_score   × 0.20)
              + (value_score × 0.10)
```

Each component is scaled to 0–10:
- `xAG_deficit` = how far the player is below the league median xAG/90, as a proportion, clipped to [0, 1] and scaled to 10.
- `PrgC_deficit` = same for progressive carries.
- `age_score` = `(age - 25) / 15`, clipped to [0, 1] and scaled to 10. A 25-year-old scores 0, a 40-year-old scores 10.
- `value_score` = the player's Transfermarkt value relative to the highest-valued flagged player, scaled to 10. Higher value = higher score, because the club recovers more money by selling them.

**Why these weights — and why they are assumptions, not facts:**

The weights (0.40, 0.30, 0.20, 0.10) are assumption-driven, not empirically derived. They represent a reasonable priority ordering for a mid-table Belgian club, explained as follows:

- **xAG deficit (0.40) — highest weight** because chance creation and assists are the most direct measure of an attacking player's output. An Antwerp forward who generates significantly fewer expected assists than the league median is the clearest case for replacement.

- **PrgC deficit (0.30) — second highest** because progressive carries measure how much a forward drives the team forward in possession. It is the best single-stat proxy for a forward's contribution outside of direct goal involvement, and strongly correlated with how dangerous a team becomes in transition.

- **Age (0.20)** because age affects both the resale window and the player's trajectory. An underperforming 32-year-old is a worse asset than an underperforming 26-year-old — the older player is less likely to improve and harder to sell at a reasonable fee.

- **Market value (0.10) — lowest weight** because it is included as a financial consideration (sell while the value is there), not a performance consideration. It is deliberately weighted low because a high-value underperformer is not more expendable on footballing grounds — they are just a better sell financially. Overweighting this would distort the ranking toward expensive players regardless of performance.

A production system at a professional club would derive these weights through regression analysis on historical transfer data — for example, training a model to predict which player sales led to measurable squad improvement, and letting the model learn the relative importance of each factor. The weights used here are a reasonable starting point for a portfolio project but should not be treated as validated.

#### Graph 2 — Janssen Replacement Scouting

Builds a scouting pool and ranks candidates by a composite scout score.

**Scouting pool filters:**
- Position: FW or attacking midfield in Transfermarkt (Left/Right Winger, Attacking Mid, Centre-Forward, Second Striker)
- Age: 18–24 (from Transfermarkt)
- Season: 2024-2025
- Club: outside Royal Antwerp
- Minutes: ≥450 (enough data to be meaningful)
- Club status: not "Without Club" (no free agents — realistic transfer targets only)
- Must appear in both the FBRef stats data and Transfermarkt (inner join)

**Composite Scout Score formula:**
```
Scout_Score = xAG_p90_norm × 0.40
            + PrgC_p90_norm × 0.35
            + Drib_p90_norm × 0.25
```

**Why these metrics and weights:**

- **xAG/90 (0.40)** is the primary metric because it directly measures what Janssen lacks most — chance creation and goal involvement. It is the most predictive single stat for whether a forward improves the team's attacking output.

- **PrgC/90 (0.35)** is nearly as important because Antwerp's flagged forwards are below median on both creativity and ball progression. A replacement who is creative but static in possession would leave the same gap.

- **Drib/90 (0.25)** is included to add a dimension that captures directness and 1v1 ability. A forward who can beat defenders creates opportunities beyond what xAG captures. It is weighted lower because it is more position-specific (wingers dribble more than strikers) and xAG already captures the downstream effect of good dribbling.

**Normalisation — why the full league pool matters:**

Each metric is min-max normalised against the full league population of forwards with ≥450 minutes (approximately 39 players), not against the filtered scouting candidates. This is important because if you normalise against only 2 or 3 candidates, the weakest candidate always scores 0.000 regardless of how good they actually are in the league context. Using the full league as the reference frame means a score of 0.5 genuinely means "middle of the league", and a score of 0.8 genuinely means "near the top".

---

### Cell 6 — Radar Chart (3-Panel Dashboard)

Visualises the gap between Antwerp's identified weak spot and the top scouting recommendation.

**Metrics used (all from `player_stat`, ≥99% non-null coverage in 2024-2025):**

| Metric | Source column | What it measures |
|---|---|---|
| xAG/90 | `Expected_xAG` | Expected goal assists — chance creation |
| SCA/90 | `SCA_SCA` | Shot-creating actions — all attacking threat |
| PrgC/90 | `Carries_PrgC` | Progressive carries — ball advancement |
| PrgP/90 | `Passes_PrgP` | Progressive passes — build-up involvement |
| xG/90 | `Expected_xG` | Expected goals — finishing / goal threat |
| Drib/90 | `Take-Ons_Succ` | Successful dribbles — 1v1 ability |

**Normalisation:** Each metric is divided by a fixed maximum calibrated to Belgian Pro League top performers (e.g. xAG/90 max = 0.50, PrgC/90 max = 6.00), then multiplied by 10. This gives a 0–10 scale where 10 represents elite-level performance in the league context. Fixed maxima are used instead of relative normalisation so that the radar axes are stable and comparable across players.

**Three panels:**
1. **Head-to-head** — Vincent Janssen vs. the top scouting candidate overlaid on the same radar.
2. **Weak spot** — Janssen alone, to clearly show his profile gaps.
3. **Proposed target** — The recommended replacement alone, showing their strengths.

---

## Key Assumptions Summary

| Assumption | Where used | Justification |
|---|---|---|
| 300 min minimum for league scan | Cell 3 | Avoids noise from players with very few appearances |
| 450 min minimum for scouting pool | Cell 5 | Slightly higher threshold because we need confidence in per-90 metrics for comparison |
| 85% of median as flagging threshold | Cell 3 | Buffer to avoid flagging borderline players; focuses on clear underperformers |
| Age 18–24 for scouting | Cell 5 | Targets players with resale potential and room to develop; aligns with Antwerp's realistic budget tier |
| xAG weight 0.40 in Scout Score | Cell 5 | Assumption: chance creation is the primary gap Janssen leaves |
| Age curve 25–40 in Expendability | Cell 5 | Assumption: peak is ~25, steep decline after 30; not empirically validated |
| Fixed radar maxima | Cell 6 | Ensures radar is stable and not distorted by a single outlier in the current dataset |
| Normalise against full league pool | Cell 5 | Prevents min-max collapse when only 2–3 candidates pass the scouting filters |

---

## Limitations

- **Composite scores are assumption-driven.** The weights in both the expendability and scout scores are not derived from regression analysis on historical transfer outcomes. They are reasonable starting points based on football logic, but a production system would validate them against real data.
- **No defensive metrics.** The audit focuses entirely on attacking output. A complete squad audit would need to incorporate pressing intensity, defensive contribution, and positional fit.
- **Transfermarkt coverage.** The scouting pool is limited to players who appear in both the FBRef stats export and the Transfermarkt data. Players missing from either source are excluded, which can create blind spots.
- **Single-season snapshot.** All comparisons are cross-sectional (2024-2025 only). A longitudinal view (e.g. declining xAG over multiple seasons) would strengthen the expendability argument.
