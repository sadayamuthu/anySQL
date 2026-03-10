"""
examples/realtime_openai_demo.py
BBC News dataset — OpenAI (gpt-4o vs gpt-4o-mini), all 5 use cases.
Runs in mock mode automatically if OPENAI_API_KEY is not set.
"""
import os
import uuid
import time
import random
from datetime import datetime, timezone
from unittest.mock import MagicMock
import anysql

# ── Embedded BBC News articles (no download required) ─────────────────────
BBC_ARTICLES = [
    {"id": "bbc_001", "topic": "technology", "title": "AI advances in 2024",
     "text": "Artificial intelligence systems have made remarkable progress this year, with large language models demonstrating capabilities that were previously considered years away. Researchers at major labs report breakthrough results in reasoning, coding, and multimodal understanding."},
    {"id": "bbc_002", "topic": "politics", "title": "Election results reshape parliament",
     "text": "The general election produced a hung parliament for the first time in over a decade, with the leading party falling short of an outright majority. Coalition negotiations are expected to last several weeks as party leaders weigh their options."},
    {"id": "bbc_003", "topic": "business", "title": "Markets rally on rate cut hopes",
     "text": "Stock markets surged to record highs after the central bank signaled it may begin cutting interest rates sooner than expected. The FTSE 100 rose 2.3% while the S&P 500 hit a new all-time high in early trading."},
    {"id": "bbc_004", "topic": "science", "title": "New exoplanet discovered in habitable zone",
     "text": "Astronomers have announced the discovery of an Earth-sized exoplanet orbiting within the habitable zone of a nearby star. The planet, located just 12 light-years away, shows signs of a rocky surface and is considered a prime candidate for further study."},
    {"id": "bbc_005", "topic": "health", "title": "Study links sleep patterns to longevity",
     "text": "A large-scale study following 500,000 participants over 25 years found strong correlations between consistent sleep schedules and longer lifespans. Researchers recommend seven to nine hours per night for optimal health outcomes."},
    {"id": "bbc_006", "topic": "technology", "title": "Chip shortages ease as new fabs come online",
     "text": "The global semiconductor shortage that plagued industries from automotive to consumer electronics is finally easing, as new fabrication plants in the United States and Europe reach production capacity."},
    {"id": "bbc_007", "topic": "environment", "title": "Arctic ice reaches record low",
     "text": "Sea ice extent in the Arctic reached a new record minimum this September, scientists confirmed. The decline is consistent with climate model projections and raises concerns about accelerating feedback loops in the global climate system."},
    {"id": "bbc_008", "topic": "sports", "title": "England wins cricket series",
     "text": "England secured the test cricket series with a dominant final-match performance, completing a dramatic comeback after losing the first two matches. The victory is celebrated as one of the greatest series reversals in modern cricket history."},
    {"id": "bbc_009", "topic": "business", "title": "Startup raises record seed round",
     "text": "A London-based fintech startup raised £45 million in what analysts are calling the largest seed round in European fintech history. The company plans to use the funds to expand its payment infrastructure to 15 new markets."},
    {"id": "bbc_010", "topic": "health", "title": "New cancer therapy shows promise",
     "text": "Clinical trials for a novel CAR-T cell therapy targeting solid tumors have shown a 60% response rate in patients who had exhausted other treatment options. The therapy is expected to seek regulatory approval within 18 months."},
    {"id": "bbc_011", "topic": "politics", "title": "Trade deal signed after years of talks",
     "text": "After three years of negotiations, a comprehensive trade agreement was signed between the UK and India. The deal covers goods, services, and investment, and is expected to add £28 billion to bilateral trade within a decade."},
    {"id": "bbc_012", "topic": "science", "title": "Quantum computer breaks encryption record",
     "text": "A quantum computer has factored a 2048-bit RSA key for the first time, a milestone that cryptographers had long anticipated. Security experts are urging organizations to accelerate the transition to post-quantum cryptography standards."},
]

MODELS = ["gpt-4o", "gpt-4o-mini"]
MOCK_SUMMARIES = {
    "gpt-4o": "A comprehensive and accurate summary covering all key points with appropriate nuance.",
    "gpt-4o-mini": "A concise summary covering the main points efficiently.",
}


def build_mock_client(model: str):
    mock = MagicMock()
    def create(**kwargs):
        r = MagicMock()
        r.id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        r.model = model
        r.choices = [MagicMock()]
        r.choices[0].message.content = MOCK_SUMMARIES[model]
        r.choices[0].finish_reason = "stop"
        # Realistic token counts
        r.usage.prompt_tokens = random.randint(80, 150)
        r.usage.completion_tokens = random.randint(40, 80)
        time.sleep(random.uniform(0.01, 0.05))  # simulate latency
        return r
    mock.chat.completions.create.side_effect = create
    return mock


def run_demo():
    print("=" * 60)
    print("anySQL — BBC News OpenAI Demo")
    print("=" * 60)

    use_real = bool(os.environ.get("OPENAI_API_KEY"))
    mode = "LIVE API" if use_real else "MOCK MODE"
    print(f"\nRunning in {mode}\n")

    db = anysql.init(":memory:", echo=False)

    for model in MODELS:
        if use_real:
            from openai import OpenAI
            raw_client = OpenAI()
        else:
            raw_client = build_mock_client(model)

        client = anysql.openai(db, task_type="summarization").wrap(raw_client)

        @anysql.context(feature="bbc_summarizer", segment="demo")
        def summarize_batch(articles, model_name):
            for article in articles:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{
                        "role": "user",
                        "content": f"Summarize in 2 sentences: {article['text']}"
                    }]
                )
                # Record eval (mock scoring based on topic)
                topic_scores = {"technology": 0.92, "science": 0.88, "health": 0.85,
                                "business": 0.80, "politics": 0.75, "sports": 0.78,
                                "environment": 0.82}
                score = topic_scores.get(article["topic"], 0.80)
                if model == "gpt-4o-mini":
                    score *= 0.92  # mini slightly lower quality
                score += random.uniform(-0.05, 0.05)

                rag = anysql.rag_tracer(db)
                qid = rag.before_retrieval(article["title"])
                rag.after_retrieval(qid, [
                    {"id": f"{article['id']}_chunk_1", "text": article["text"][:200],
                     "score": random.uniform(0.75, 0.95), "source": f"{article['topic']}_corpus.txt"},
                ])
                rag.record_eval(
                    query_id=qid,
                    score=round(min(max(score, 0.0), 1.0), 3),
                    actual=response.choices[0].message.content,
                    model=model_name,
                    prompt_id=f"summarizer_{article['topic']}",
                    prompt_version="v1",
                )

        summarize_batch(BBC_ARTICLES, model)
        print(f"Processed {len(BBC_ARTICLES)} articles with {model}")

    print("\n" + "=" * 60)
    print("UC1: Multi-Model Comparison")
    print("=" * 60)
    print(db.model_comparison().to_string(index=False))

    print("\n" + "=" * 60)
    print("UC2: Eval Debt (prompts by last evaluation date)")
    print("=" * 60)
    print(db.eval_debt().to_string(index=False))

    print("\n" + "=" * 60)
    print("UC3: Cost by Feature Flag")
    print("=" * 60)
    print(db.cost_by_feature().to_string(index=False))

    print("\n" + "=" * 60)
    print("UC4: Tool Failure Rates (no agent tools in this demo)")
    print("=" * 60)
    print(db.tool_failure_rates().to_string(index=False))

    print("\n" + "=" * 60)
    print("UC5: RAG Failure Mode Classification")
    print("=" * 60)
    print(db.rag_failure_modes().to_string(index=False))

    print("\n" + "=" * 60)
    print("UC5: Chunk Quality Ranking by Source Document")
    print("=" * 60)
    print(db.chunk_quality_ranking().to_string(index=False))

    print("\nDemo complete.")


if __name__ == "__main__":
    run_demo()
