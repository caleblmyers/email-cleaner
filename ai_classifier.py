"""Claude AI email classifier using the Anthropic API."""

import json

import anthropic

import config
import database

log = config.get_logger(__name__)

_client: anthropic.Anthropic | None = None

# Haiku 4.5 pricing (per token)
INPUT_COST_PER_TOKEN = 0.80 / 1_000_000
OUTPUT_COST_PER_TOKEN = 4.00 / 1_000_000


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def _build_system_prompt(categories: list[dict]) -> str:
    """Build the classification system prompt from the categories in the database."""
    lines = ["You are an expert email classifier. Classify each email into exactly one category.", "", "Categories:"]
    for cat in categories:
        desc = cat["description"]
        if desc:
            lines.append(f"- {cat['name']}: {desc}")
        else:
            lines.append(f"- {cat['name']}")
    cat_names = ", ".join(cat["name"] for cat in categories)
    lines.extend([
        "",
        "Return a JSON array — one object per email — with this exact structure:",
        "[",
        "  {",
        '    "id": "<email id from input>",',
        f'    "category": "<one of: {cat_names}>",',
        "    \"confidence\": <float 0.0 to 1.0>,",
        '    "reasoning": "<one sentence explanation>"',
        "  }",
        "]",
        "Return ONLY the JSON array, no other text, no markdown code fences.",
    ])
    return "\n".join(lines)


USER_PROMPT_TEMPLATE = """Classify these {count} emails:

{emails_json}"""


def _get_valid_categories() -> set[str]:
    conn = database.get_connection()
    try:
        return set(database.get_category_names(conn))
    finally:
        conn.close()


def _get_system_prompt() -> str:
    conn = database.get_connection()
    try:
        cats = database.get_categories(conn)
        return _build_system_prompt(cats)
    finally:
        conn.close()


def classify_emails_stream(emails: list[dict]):
    """Yield batch progress dicts as each batch completes.

    Each yield: {"batch": N, "total_batches": N, "classified": N, "results": [...], "usage": {...}}
    """
    system_prompt = _get_system_prompt()
    valid_categories = _get_valid_categories()
    batch_size = config.CLASSIFIER_BATCH_SIZE
    total_batches = (len(emails) + batch_size - 1) // batch_size
    classified_so_far = 0

    for i in range(0, len(emails), batch_size):
        batch_num = i // batch_size + 1
        batch = emails[i : i + batch_size]
        log.info("Classifying batch %d/%d (%d emails)", batch_num, total_batches, len(batch))
        batch_results, usage = _classify_batch(batch, system_prompt, valid_categories)
        classified_so_far += len(batch_results)
        cost = (usage["input_tokens"] * INPUT_COST_PER_TOKEN) + (usage["output_tokens"] * OUTPUT_COST_PER_TOKEN)
        yield {
            "batch": batch_num,
            "total_batches": total_batches,
            "classified": classified_so_far,
            "total_emails": len(emails),
            "results": batch_results,
            "usage": {
                "input_tokens": usage["input_tokens"],
                "output_tokens": usage["output_tokens"],
                "batch_cost": round(cost, 6),
            },
        }


def classify_emails(emails: list[dict]) -> dict:
    """Classify a list of email metadata dicts using Claude.

    Returns dict with keys: results, usage (input_tokens, output_tokens, total_cost).
    """
    results = []
    total_input = 0
    total_output = 0
    for progress in classify_emails_stream(emails):
        results.extend(progress["results"])
        total_input += progress["usage"]["input_tokens"]
        total_output += progress["usage"]["output_tokens"]
    total_cost = (total_input * INPUT_COST_PER_TOKEN) + (total_output * OUTPUT_COST_PER_TOKEN)
    return {
        "results": results,
        "usage": {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total_cost": round(total_cost, 6),
        },
    }


def _classify_batch(emails: list[dict], system_prompt: str, valid_categories: set[str]) -> tuple[list[dict], dict]:
    """Send one batch of emails to Claude for classification.

    Returns (results, usage) where usage has input_tokens and output_tokens.
    """
    client = _get_client()
    zero_usage = {"input_tokens": 0, "output_tokens": 0}

    email_payload = [
        {
            "id": e["id"],
            "from": f"{e.get('sender', '')} <{e.get('sender_email', '')}>".strip(),
            "subject": e.get("subject") or "(no subject)",
            "snippet": (e.get("snippet") or "")[:300],
        }
        for e in emails
    ]

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": USER_PROMPT_TEMPLATE.format(
                        count=len(email_payload),
                        emails_json=json.dumps(email_payload, indent=2),
                    ),
                }
            ],
        )

        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }

        raw = response.content[0].text.strip()
        # Strip markdown code fences if Claude adds them despite instructions
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        parsed = json.loads(raw)

    except json.JSONDecodeError as e:
        log.error("Failed to parse Claude response as JSON: %s", e)
        return _fallback_results(emails), usage
    except Exception as e:
        log.error("Classification API call failed: %s", e)
        return _fallback_results(emails), zero_usage

    # Validate and sanitize
    result_map = {item["id"]: item for item in parsed if isinstance(item, dict)}
    results = []
    for e in emails:
        item = result_map.get(e["id"], {})
        category = item.get("category", "Uncategorized")
        if category not in valid_categories:
            category = "Uncategorized"
        confidence = float(item.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))
        results.append(
            {
                "id": e["id"],
                "category": category,
                "confidence": confidence,
                "reasoning": item.get("reasoning", ""),
            }
        )
    return results, usage


def _fallback_results(emails: list[dict]) -> list[dict]:
    return [
        {
            "id": e["id"],
            "category": "Uncategorized",
            "confidence": 0.0,
            "reasoning": "Classification failed",
        }
        for e in emails
    ]
