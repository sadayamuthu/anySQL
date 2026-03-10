"""
examples/realtime_combined_demo.py
Reuters R8 dataset — All 4 models head-to-head, all 5 use cases.
Runs in mock mode automatically if API keys are not set.
"""
import os
import uuid
import time
import random
from unittest.mock import MagicMock
import anysql

REUTERS_ARTICLES = [
    {"id": "r_001", "topic": "earn", "title": "Company reports strong quarterly earnings",
     "text": "The company posted quarterly earnings of $3.2 billion, beating analyst expectations by 12%. Revenue grew 18% year-over-year to $24.5 billion, driven primarily by subscription services and enterprise software sales. Management raised full-year guidance."},
    {"id": "r_002", "topic": "acq", "title": "Acquisition reshapes pharmaceutical sector",
     "text": "A major pharmaceutical company completed its $68 billion acquisition of a mid-size biotech firm, gaining control of a promising pipeline of oncology drugs. The deal required divestitures in three overlapping therapeutic areas to satisfy regulators."},
    {"id": "r_003", "topic": "money-fx", "title": "Dollar strengthens on Fed signals",
     "text": "The US dollar strengthened against a basket of major currencies after Federal Reserve officials signaled a willingness to keep interest rates higher for longer than previously anticipated, citing persistent services inflation."},
    {"id": "r_004", "topic": "grain", "title": "Drought threatens global wheat harvest",
     "text": "A prolonged drought across key wheat-growing regions in North America and central Asia is expected to reduce global wheat production by 8% this year, pushing prices to a two-year high and raising food security concerns in import-dependent nations."},
    {"id": "r_005", "topic": "crude", "title": "Refinery outages tighten US fuel supply",
     "text": "Unexpected refinery outages across the Gulf Coast have tightened gasoline and diesel supplies in the United States, pushing retail fuel prices up 15 cents per gallon in two weeks and prompting the Department of Energy to monitor inventory levels."},
    {"id": "r_006", "topic": "trade", "title": "Trade deficit narrows unexpectedly",
     "text": "The US trade deficit narrowed more than expected in the latest month, as goods exports hit a record high while imports declined for the third consecutive month. Economists say the trend may be temporary given strong domestic consumption."},
    {"id": "r_007", "topic": "interest", "title": "Central bank holds rates steady",
     "text": "The central bank held its benchmark interest rate steady for the third consecutive meeting, citing balanced risks to inflation and employment. The decision was unanimous and the accompanying statement offered few clues about the timing of future moves."},
    {"id": "r_008", "topic": "ship", "title": "New container shipping route opens",
     "text": "A major shipping alliance announced a new direct container route connecting Southeast Asian manufacturing hubs to European ports, cutting transit times by four days compared to existing routes and offering weekly sailings from day one."},
    {"id": "r_009", "topic": "earn", "title": "Retailer misses profit forecasts",
     "text": "A major retailer reported quarterly profits below analyst estimates after a surprise increase in inventory write-downs and rising labor costs compressed margins. The company warned that full-year earnings would come in at the low end of its guidance range."},
    {"id": "r_010", "topic": "acq", "title": "Tech buyout raises competition concerns",
     "text": "Antitrust regulators in the US and EU opened parallel investigations into a proposed $45 billion technology acquisition, citing concerns about market concentration in cloud infrastructure and potential harm to startup competitors."},
    {"id": "r_011", "topic": "money-fx", "title": "Emerging market currencies under pressure",
     "text": "Several emerging market currencies hit multi-year lows against the US dollar as rising US Treasury yields triggered capital outflows. Central banks in three countries intervened in currency markets while one raised interest rates by 50 basis points."},
    {"id": "r_012", "topic": "grain", "title": "Record corn surplus weighs on prices",
     "text": "US corn production reached a record high this harvest season, with total output 15% above last year's crop. The surplus has pushed corn futures to a three-year low, squeezing farm incomes but benefiting food manufacturers and livestock producers."},
    {"id": "r_013", "topic": "crude", "title": "OPEC output deal extended",
     "text": "OPEC and its allies agreed to extend existing oil production cuts for a further six months, citing uncertain demand growth and high inventories in consuming nations. Several members lobbied unsuccessfully for deeper cuts during the ministerial meeting."},
    {"id": "r_014", "topic": "trade", "title": "Steel tariffs spark retaliation threats",
     "text": "The United States announced new tariffs on imported steel and aluminum, citing national security concerns, prompting immediate retaliation threats from the European Union, Canada, and Mexico. Industry groups warned the tariffs would raise costs for domestic manufacturers."},
    {"id": "r_015", "topic": "interest", "title": "Mortgage rates hit 20-year high",
     "text": "The average 30-year fixed mortgage rate climbed above 8% for the first time in over two decades, dealing a severe blow to housing affordability and pushing existing home sales to their lowest level since 2010 as potential buyers wait on the sidelines."},
    {"id": "r_016", "topic": "ship", "title": "Port congestion eases at major hubs",
     "text": "Congestion at the world's busiest container ports has eased significantly compared to the pandemic peak, with vessel wait times at major Asian hubs returning to pre-2020 norms. Shipping executives credit new berth capacity and improved scheduling coordination."},
    {"id": "r_017", "topic": "earn", "title": "Bank profits rise on interest income",
     "text": "Major US banks reported sharp increases in quarterly profits as rising interest rates boosted net interest income, more than offsetting higher loan loss provisions. Investment banking fees remained subdued amid cautious deal activity."},
    {"id": "r_018", "topic": "acq", "title": "Airline merger approved with conditions",
     "text": "Regulators approved a merger between two major domestic airlines, but required the combined carrier to divest slots at six congested airports and maintain existing service to 52 smaller communities as conditions for clearance."},
    {"id": "r_019", "topic": "grain", "title": "Soybean exports break records",
     "text": "US soybean exports hit a quarterly record, driven by strong demand from China and concerns about crop shortfalls in South America. The surge has helped narrow the agricultural trade deficit and boosted farm income projections for the year."},
    {"id": "r_020", "topic": "crude", "title": "EV adoption slows oil demand growth",
     "text": "The International Energy Agency revised down its long-term oil demand forecast for the fourth consecutive year, citing faster-than-expected electric vehicle adoption in China and Europe as the primary driver of slower demand growth through 2030."},
]

OPENAI_MODELS = ["gpt-4o", "gpt-4o-mini"]
CLAUDE_MODELS = ["claude-sonnet-4-6", "claude-haiku-4-5"]

TOPIC_SCORES = {
    "earn": 0.88, "acq": 0.85, "money-fx": 0.83,
    "grain": 0.80, "crude": 0.82, "trade": 0.81,
    "interest": 0.84, "ship": 0.79,
}
MODEL_QUALITY = {
    "gpt-4o": 1.00, "gpt-4o-mini": 0.91,
    "claude-sonnet-4-6": 0.99, "claude-haiku-4-5": 0.90,
}


def make_openai_mock(model):
    mock = MagicMock()
    def create(**kwargs):
        r = MagicMock()
        r.id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        r.model = model
        r.choices = [MagicMock()]
        r.choices[0].message.content = f"[{model}] Summary of the article content."
        r.choices[0].finish_reason = "stop"
        r.usage.prompt_tokens = random.randint(90, 160)
        r.usage.completion_tokens = random.randint(35, 75)
        time.sleep(random.uniform(0.01, 0.03))
        return r
    mock.chat.completions.create.side_effect = create
    return mock


def make_claude_mock(model):
    mock = MagicMock()
    def create(**kwargs):
        r = MagicMock()
        r.id = f"msg_{uuid.uuid4().hex[:8]}"
        r.stop_reason = "end_turn"
        block = MagicMock()
        block.text = f"[{model}] Concise summary of the Reuters article."
        r.content = [block]
        r.usage.input_tokens = random.randint(90, 160)
        r.usage.output_tokens = random.randint(35, 75)
        time.sleep(random.uniform(0.01, 0.03))
        return r
    mock.messages.create.side_effect = create
    return mock


def run_demo():
    print("=" * 70)
    print("anySQL — Reuters R8 Combined Demo (All 4 Models Head-to-Head)")
    print("=" * 70)

    use_openai = bool(os.environ.get("OPENAI_API_KEY"))
    use_claude = bool(os.environ.get("ANTHROPIC_API_KEY"))
    print(f"\nOpenAI: {'LIVE' if use_openai else 'MOCK'} | Claude: {'LIVE' if use_claude else 'MOCK'}\n")

    db = anysql.init(":memory:")

    # ── Run OpenAI models ───────────────────────────────────────────────────
    for model in OPENAI_MODELS:
        if use_openai:
            from openai import OpenAI
            raw = OpenAI()
        else:
            raw = make_openai_mock(model)

        client = anysql.openai(db, task_type="summarization").wrap(raw)

        @anysql.context(feature=f"reuters_{model.replace('-','_')}", segment="research")
        def run_openai_batch(articles, m):
            for version in ["v1", "v2"]:
                for article in articles[:10]:  # first 10 articles per version
                    response = client.chat.completions.create(
                        model=m,
                        messages=[{"role": "user", "content": f"Summarize: {article['text']}"}]
                    )
                    base_score = TOPIC_SCORES.get(article["topic"], 0.80) * MODEL_QUALITY[m]
                    # v2 has slight quality drop to trigger regression detection
                    if version == "v2":
                        base_score *= 0.88
                    score = base_score + random.uniform(-0.03, 0.03)

                    rag = anysql.rag_tracer(db)
                    qid = rag.before_retrieval(article["title"])
                    rag.after_retrieval(qid, [
                        {"id": f"{article['id']}_c1", "text": article["text"][:200],
                         "score": random.uniform(0.70, 0.95), "source": f"reuters_{article['topic']}.txt"},
                    ])
                    rag.record_eval(
                        query_id=qid,
                        score=round(min(max(score, 0.0), 1.0), 3),
                        actual=response.choices[0].message.content,
                        model=m, prompt_id=f"reuters_{article['topic']}", prompt_version=version,
                    )

        run_openai_batch(REUTERS_ARTICLES, model)
        print(f"OpenAI {model}: {10 * 2} calls (v1+v2)")

    # ── Run Claude models ───────────────────────────────────────────────────
    for model in CLAUDE_MODELS:
        if use_claude:
            import anthropic
            raw = anthropic.Anthropic()
        else:
            raw = make_claude_mock(model)

        client = anysql.claude(db, task_type="summarization").wrap(raw)

        @anysql.context(feature=f"reuters_{model.replace('-','_').replace('.','_')}", segment="research")
        def run_claude_batch(articles, m):
            for version in ["v1", "v2"]:
                for article in articles[10:20]:  # last 10 articles per version
                    response = client.messages.create(
                        model=m, max_tokens=200,
                        messages=[{"role": "user", "content": f"Summarize: {article['text']}"}]
                    )
                    base_score = TOPIC_SCORES.get(article["topic"], 0.80) * MODEL_QUALITY[m]
                    if version == "v2":
                        base_score *= 0.89
                    score = base_score + random.uniform(-0.03, 0.03)

                    rag = anysql.rag_tracer(db)
                    qid = rag.before_retrieval(article["title"])
                    rag.after_retrieval(qid, [
                        {"id": f"{article['id']}_c1", "text": article["text"][:200],
                         "score": random.uniform(0.70, 0.95), "source": f"reuters_{article['topic']}.txt"},
                    ])
                    rag.record_eval(
                        query_id=qid, score=round(min(max(score, 0.0), 1.0), 3),
                        actual=response.content[0].text,
                        model=m, prompt_id=f"reuters_{article['topic']}", prompt_version=version,
                    )

        run_claude_batch(REUTERS_ARTICLES, model)
        print(f"Claude {model}: {10 * 2} calls (v1+v2)")

    # ── UC4: Simulate agent tool calls ──────────────────────────────────────
    print("\nSimulating agent tool calls for UC4...")
    tools = ["web_search", "doc_retrieval", "fact_checker", "summarizer", "citation_finder"]
    for session_num in range(5):
        session_id = f"agent_session_{session_num:03d}"
        tracer = anysql.agent_tracer(db, session_id=session_id)
        for step, tool in enumerate(random.sample(tools, random.randint(3, 5))):
            # Introduce some failures
            status = "error" if (tool == "fact_checker" and random.random() < 0.4) else "success"
            tracer.trace_tool_call(
                tool, input={"query": "Reuters article context"},
                output="tool result" if status == "success" else None,
                status=status,
                error_message="API timeout" if status == "error" else None,
                latency_ms=random.randint(50, 800),
            )
            tracer.trace_step("tool_call", description=f"Execute {tool}")

    print("\n" + "=" * 70)
    print("UC1: Multi-Model Comparison (All 4 Models)")
    print("=" * 70)
    print(db.model_comparison().to_string(index=False))

    print("\n" + "=" * 70)
    print("UC2: Prompt Regressions (v1→v2 score drops)")
    print("=" * 70)
    regressions = db.prompt_regressions(threshold=-0.05)
    print(regressions.to_string(index=False) if len(regressions) > 0 else "(none detected)")

    print("\n" + "=" * 70)
    print("UC3: Cost by Feature Flag (per model/pipeline)")
    print("=" * 70)
    print(db.cost_by_feature().to_string(index=False))

    print("\n" + "=" * 70)
    print("UC4: Tool Failure Rates")
    print("=" * 70)
    print(db.tool_failure_rates().to_string(index=False))

    print("\n" + "=" * 70)
    print("UC5: RAG Failure Modes")
    print("=" * 70)
    print(db.rag_failure_modes().to_string(index=False))

    print("\n" + "=" * 70)
    print("UC5: Similarity Score Calibration")
    print("=" * 70)
    print(db.similarity_calibration().to_string(index=False))

    print(f"\nTotal rows: {repr(db)}")
    print("\nDemo complete.")


if __name__ == "__main__":
    run_demo()
