import json
import anthropic

import config

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


SYSTEM_PROMPT = """You are an expert email classifier. Classify each email into exactly one category.

Categories:
- Newsletters: marketing emails, digests, subscriptions, blog updates, promotional content
- Receipts: order confirmations, invoices, payment confirmations, shipping notices, purchase records
- Work: work-related communication, meetings, tasks, colleagues, clients, job applications
- Social: personal messages, social network notifications (Facebook, LinkedIn, Twitter, Instagram), dating apps
- Notifications: automated alerts, account notifications, security alerts, system messages, app updates
- Spam: unsolicited, suspicious, phishing attempts, or clearly unwanted email
- Uncategorized: anything that does not fit the above categories

Return a JSON array — one object per email — with this exact structure:
[
  {
    "id": "<email id from input>",
    "category": "<one of the 7 categories>",
    "confidence": <float 0.0 to 1.0>,
    "reasoning": "<one sentence explanation>"
  }
]
Return ONLY the JSON array, no other text, no markdown code fences."""

USER_PROMPT_TEMPLATE = """Classify these {count} emails:

{emails_json}"""

VALID_CATEGORIES = set(config.CATEGORIES)


def classify_emails(emails: list[dict]) -> list[dict]:
    """Classify a list of email metadata dicts using Claude. Returns classification results."""
    results = []
    batch_size = config.CLASSIFIER_BATCH_SIZE
    for i in range(0, len(emails), batch_size):
        batch = emails[i : i + batch_size]
        batch_results = _classify_batch(batch)
        results.extend(batch_results)
    return results


def _classify_batch(emails: list[dict]) -> list[dict]:
    """Send one batch of emails to Claude for classification."""
    client = _get_client()

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
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
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

        raw = response.content[0].text.strip()
        # Strip markdown code fences if Claude adds them despite instructions
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        parsed = json.loads(raw)

    except json.JSONDecodeError:
        # Fallback: mark all as Uncategorized
        return _fallback_results(emails)
    except Exception:
        return _fallback_results(emails)

    # Validate and sanitize
    result_map = {item["id"]: item for item in parsed if isinstance(item, dict)}
    results = []
    for e in emails:
        item = result_map.get(e["id"], {})
        category = item.get("category", "Uncategorized")
        if category not in VALID_CATEGORIES:
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
    return results


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
