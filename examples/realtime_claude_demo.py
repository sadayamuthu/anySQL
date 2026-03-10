"""
examples/realtime_claude_demo.py
AG News dataset — Claude (sonnet-4-6 vs haiku-4-5), all 5 use cases.
Runs in mock mode automatically if ANTHROPIC_API_KEY is not set.
"""
import os
import uuid
import time
import random
from unittest.mock import MagicMock
import anysql

AG_ARTICLES = [
    {"id": "ag_001", "topic": "technology", "title": "Tech giants report record profits",
     "text": "The largest technology companies reported combined quarterly profits exceeding $100 billion for the first time, driven by cloud computing and advertising revenue growth that outpaced analyst expectations significantly."},
    {"id": "ag_002", "topic": "sports", "title": "World Cup host city announced",
     "text": "FIFA announced the host cities for the upcoming World Cup, with the tournament to be spread across three continents for the first time. The decision follows years of bidding competition and infrastructure assessments by the governing body."},
    {"id": "ag_003", "topic": "business", "title": "Oil prices hit six-month high",
     "text": "Crude oil prices climbed to a six-month high after OPEC+ announced an unexpected extension of production cuts. Brent crude rose 4% to $94 per barrel as traders priced in tighter supply through the end of the year."},
    {"id": "ag_004", "topic": "science", "title": "Mars water discovery confirmed",
     "text": "NASA scientists confirmed the discovery of large underground water ice deposits near the Martian equator, a finding that significantly changes the calculus for future human missions and potential in-situ resource utilization."},
    {"id": "ag_005", "topic": "technology", "title": "Open source LLM matches GPT-4",
     "text": "A research team released an open-source large language model that matches GPT-4 performance on standard benchmarks while requiring significantly less compute to run. The release has sparked debate about the pace of AI democratization."},
    {"id": "ag_006", "topic": "business", "title": "Merger creates largest bank in Asia",
     "text": "Two of Asia's largest financial institutions completed their merger, creating the continent's biggest bank by assets. The combined entity will have over $4 trillion in assets and operations across 40 countries."},
    {"id": "ag_007", "topic": "sports", "title": "Olympic records broken in swimming",
     "text": "Three world records were broken on a single day at the World Swimming Championships, with athletes crediting improved training methods, advanced swimsuit technology, and high-altitude preparation camps for the unprecedented performances."},
    {"id": "ag_008", "topic": "science", "title": "Antibiotic resistance breakthrough",
     "text": "Researchers discovered a novel compound that kills antibiotic-resistant bacteria through a previously unknown mechanism, offering hope in the fight against superbugs that currently kill over a million people annually worldwide."},
    {"id": "ag_009", "topic": "technology", "title": "Self-driving trucks begin highway routes",
     "text": "The first fully autonomous commercial freight trucks began operating on a major interstate highway corridor, marking a milestone for the logistics industry. The trucks operate without safety drivers during daytime hours on approved routes."},
    {"id": "ag_010", "topic": "business", "title": "Luxury goods demand surges in Southeast Asia",
     "text": "Sales of luxury goods in Southeast Asia grew 35% year-over-year, outpacing all other global regions. Analysts attribute the boom to a growing affluent middle class and increased spending among younger consumers under 35."},
    {"id": "ag_011", "topic": "sports", "title": "Historic tennis comeback at Wimbledon",
     "text": "A player staged the most remarkable comeback in Wimbledon history, winning from two sets down and a match point deficit to claim the championship in a five-set final that lasted over four hours."},
    {"id": "ag_012", "topic": "technology", "title": "Cybersecurity breach affects millions",
     "text": "A major data breach at a US healthcare provider exposed the personal and medical records of 47 million patients, making it one of the largest healthcare data breaches in history and prompting congressional hearings."},
    {"id": "ag_013", "topic": "science", "title": "Brain-computer interface allows speech",
     "text": "A paralyzed patient spoke using a brain-computer interface that decoded neural signals and converted them to synthesized speech at near-natural rates. The clinical trial results represent a major advance for assistive communication technology."},
    {"id": "ag_014", "topic": "business", "title": "Shipping costs return to pre-pandemic levels",
     "text": "Global container shipping rates have fallen back to 2019 levels after three years of extraordinary volatility, providing relief to manufacturers and retailers who pass on lower logistics costs to consumers."},
    {"id": "ag_015", "topic": "sports", "title": "Football league expands to new markets",
     "text": "A major professional football league announced expansion franchises in two new cities, bringing total league membership to 36 teams. The expansion fees of $2 billion each set a new record for professional sports franchise valuations."},
]

MODELS = ["claude-sonnet-4-6", "claude-haiku-4-5"]
MOCK_SUMMARIES = {
    "claude-sonnet-4-6": "A thorough and nuanced summary capturing key context and implications.",
    "claude-haiku-4-5": "A focused, efficient summary of the core facts.",
}


def build_mock_client(model: str):
    mock = MagicMock()
    def create(**kwargs):
        r = MagicMock()
        r.id = f"msg_{uuid.uuid4().hex[:8]}"
        r.stop_reason = "end_turn"
        block = MagicMock()
        block.text = MOCK_SUMMARIES[model]
        r.content = [block]
        r.usage.input_tokens = random.randint(80, 150)
        r.usage.output_tokens = random.randint(40, 80)
        time.sleep(random.uniform(0.01, 0.05))
        return r
    mock.messages.create.side_effect = create
    return mock


def run_demo():
    print("=" * 60)
    print("anySQL — AG News Claude Demo")
    print("=" * 60)

    use_real = bool(os.environ.get("ANTHROPIC_API_KEY"))
    mode = "LIVE API" if use_real else "MOCK MODE"
    print(f"\nRunning in {mode}\n")

    db = anysql.init(":memory:")

    topic_scores = {"technology": 0.90, "science": 0.87, "business": 0.82, "sports": 0.78}

    for model in MODELS:
        if use_real:
            import anthropic
            raw_client = anthropic.Anthropic()
        else:
            raw_client = build_mock_client(model)

        client = anysql.claude(db, task_type="summarization").wrap(raw_client)

        @anysql.context(feature="ag_summarizer", segment="demo")
        def summarize_batch(articles, model_name):
            for article in articles:
                response = client.messages.create(
                    model=model_name,
                    max_tokens=200,
                    messages=[{"role": "user", "content": f"Summarize: {article['text']}"}]
                )
                score = topic_scores.get(article["topic"], 0.80)
                if "haiku" in model_name:
                    score *= 0.93
                score += random.uniform(-0.04, 0.04)

                rag = anysql.rag_tracer(db)
                qid = rag.before_retrieval(article["title"])
                rag.after_retrieval(qid, [
                    {"id": f"{article['id']}_c1", "text": article["text"][:200],
                     "score": random.uniform(0.72, 0.96), "source": f"{article['topic']}_news.txt"},
                ])
                rag.record_eval(
                    query_id=qid,
                    score=round(min(max(score, 0.0), 1.0), 3),
                    actual=response.content[0].text,
                    model=model_name,
                    prompt_id=f"summarizer_{article['topic']}",
                    prompt_version="v1",
                )

        summarize_batch(AG_ARTICLES, model)
        print(f"Processed {len(AG_ARTICLES)} articles with {model}")

    print("\n" + "=" * 60)
    print("UC1: Multi-Model Comparison (Sonnet vs Haiku)")
    print("=" * 60)
    print(db.model_comparison().to_string(index=False))

    print("\n" + "=" * 60)
    print("UC2: Prompt Regressions (none expected — single version)")
    print("=" * 60)
    print(db.eval_debt().to_string(index=False))

    print("\n" + "=" * 60)
    print("UC3: Cost by Feature")
    print("=" * 60)
    print(db.cost_by_feature().to_string(index=False))

    print("\n" + "=" * 60)
    print("UC5: RAG Failure Modes")
    print("=" * 60)
    print(db.rag_failure_modes().to_string(index=False))

    print("\n" + "=" * 60)
    print("UC5: Similarity Calibration")
    print("=" * 60)
    print(db.similarity_calibration().to_string(index=False))

    print("\nDemo complete.")


if __name__ == "__main__":
    run_demo()
