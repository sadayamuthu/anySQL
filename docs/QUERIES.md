# anySQL Canonical SQL Query Library

## UC1 — Model Cost/Quality Tradeoff

```sql
SELECT model,
       COUNT(*)                                              AS calls,
       ROUND(AVG(cost_usd), 6)                              AS avg_cost_usd,
       ROUND(AVG(latency_ms), 0)                            AS avg_latency_ms,
       ROUND(AVG(score), 3)                                 AS avg_quality,
       ROUND(AVG(score) / NULLIF(AVG(cost_usd), 0), 2)     AS quality_per_dollar
FROM llm_responses r
LEFT JOIN eval_results e ON r.response_id = e.response_id
GROUP BY model
ORDER BY quality_per_dollar DESC;
```

## UC2 — Prompt Regression Detection

```sql
WITH version_scores AS (
    SELECT prompt_id, prompt_version,
           AVG(score) AS avg_score, evaluated_at
    FROM eval_results
    WHERE prompt_id IS NOT NULL
    GROUP BY prompt_id, prompt_version, evaluated_at
),
with_prev AS (
    SELECT *,
        LAG(avg_score) OVER (PARTITION BY prompt_id ORDER BY evaluated_at) AS prev_score
    FROM version_scores
)
SELECT prompt_id, prompt_version,
       ROUND(avg_score, 3), ROUND(prev_score, 3),
       ROUND(avg_score - prev_score, 3) AS delta
FROM with_prev
WHERE (avg_score - prev_score) < -0.10
ORDER BY delta ASC;
```

## UC3 — Cost Attribution by Feature

```sql
SELECT feature_flag, user_segment,
       COUNT(*) AS runs,
       ROUND(SUM(total_cost_usd), 4) AS total_cost_usd,
       ROUND(SUM(revenue_attributed) / NULLIF(SUM(total_cost_usd), 0), 2) AS roi
FROM pipeline_runs
GROUP BY feature_flag, user_segment
ORDER BY total_cost_usd DESC;
```

## UC4 — Tool Failure Analysis

```sql
SELECT tool_name,
       COUNT(*) AS calls,
       SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS failures,
       ROUND(100.0 * SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) / COUNT(*), 2) AS failure_pct,
       ROUND(AVG(latency_ms), 0) AS avg_ms
FROM agent_tool_calls
GROUP BY tool_name
ORDER BY failure_pct DESC;
```

## UC5 — RAG Failure Mode Classification

```sql
SELECT failure_mode, COUNT(*) AS queries, ROUND(AVG(answer_quality), 3) AS avg_quality
FROM (
    SELECT r.query_id,
           MAX(r.similarity_score) AS best_retrieval,
           e.score AS answer_quality,
           CASE
             WHEN MAX(r.similarity_score) < 0.7 AND e.score < 0.6 THEN 'retrieval_failure'
             WHEN MAX(r.similarity_score) >= 0.7 AND e.score < 0.6 THEN 'generation_failure'
             WHEN MAX(r.similarity_score) < 0.7 AND e.score >= 0.8 THEN 'lucky_generation'
             ELSE 'success'
           END AS failure_mode
    FROM rag_chunks r
    JOIN eval_results e ON r.query_id = e.query_id
    GROUP BY r.query_id, e.score
)
GROUP BY failure_mode ORDER BY queries DESC;
```
