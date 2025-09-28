#!/usr/bin/env python3
"""Generate a daily programming insight post and publish it to GitHub Discussions."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Mapping

import requests
from groq import Groq


GITHUB_GRAPHQL_ENDPOINT = "https://api.github.com/graphql"
MODEL_NAME = os.environ.get("GROQ_MODEL", "llama3-70b-8192")


def require_env(var_name: str) -> str:
    """Fetch an environment variable or raise a helpful error."""

    value = os.environ.get(var_name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {var_name}")
    return value


GITHUB_TOKEN = require_env("GITHUB_TOKEN")
GROQ_API_KEY = require_env("GROQ_API_KEY")

_repo_owner_env = os.environ.get("REPO_OWNER")
_repo_name_raw = require_env("REPO_NAME")

if "/" in _repo_name_raw:
    owner_from_slug, repo_from_slug = _repo_name_raw.split("/", 1)
    REPO_OWNER = owner_from_slug
    REPO_NAME = repo_from_slug
else:
    if not _repo_owner_env:
        raise RuntimeError(
            "REPO_OWNER environment variable is required when REPO_NAME does not include the owner"
        )
    REPO_OWNER = _repo_owner_env
    REPO_NAME = _repo_name_raw

DISCUSSION_CATEGORY_ID = require_env("DISCUSSION_CATEGORY_ID")
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"


LANGUAGE_SCHEDULE = {
    0: "Wildcard",      # Sunday
    1: "Python",        # Monday
    2: "Java",          # Tuesday
    3: "JavaScript",    # Wednesday
    4: "Go",            # Thursday
    5: "Wildcard",      # Friday
    6: "Wildcard",      # Saturday
}


DAY_NAMES = {
    0: "Sunday",
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday",
}


def get_current_day_info() -> Dict[str, str]:
    """Return mapping describing the current day in UTC and the scheduled language."""

    now = datetime.now(timezone.utc)
    weekday = now.weekday() + 1 if now.weekday() != 6 else 0  # Convert to Sunday=0 format
    return {
        "day_name": DAY_NAMES[weekday],
        "language": LANGUAGE_SCHEDULE[weekday],
        "date": now.strftime("%Y-%m-%d"),
    }


SYSTEM_PROMPT = (
    "You are an expert AI instructor who writes daily programming insight posts for "
    "beginners. Always reply with valid Markdown that is professional, concise, and "
    "aligned with the provided outline. Never include extra sections or commentary."
)


def build_user_prompt(day_info: Dict[str, str]) -> str:
    """Compose the user-facing prompt that enforces the required structure."""

    language = day_info["language"]
    day_name = day_info["day_name"]
    return f"""Create today's GitHub Discussion post for the Daily Programming Insight series.

Date: {day_info['date']}
Day: {day_name}
Scheduled Language: {language}

Follow these exact rules:

Language schedule
- Monday → Python
- Tuesday → Java
- Wednesday → JavaScript
- Thursday → Go
- Friday, Saturday, Sunday → Wildcard (you may pick any language, including niche or emerging ones)

Post structure and formatting
1. Introduction — 1-2 sentences introducing yourself as the AI assistant.
2. Topic Preview — Clearly state the specific concept or technique covered today.
3. Fun Fact — 2-4 sentences about the scheduled language including year or origin context.
4. Tips/Notes — Provide exactly 1-2 practical syntax tips, functions, or features for the language.
5. Code Snippet — Provide a runnable example in the scheduled language that demonstrates the concept. Use a fenced code block tagged with the lowercase language name. The snippet must be 30-50 lines, beginner-friendly yet intermediate in difficulty, and follow PEP 8 if the language is Python. Include helpful inline comments.
6. Explanation — Offer a step-by-step breakdown of how the code works, why the concept matters, and practical use cases. Use numbered steps.
7. Sources — If you referenced any external material, cite the links in Markdown list format. If not, output "Sources: None".

Additional requirements
- Maintain professional, concise, beginner-friendly tone.
- Never add sections beyond the list above.
- Always produce valid Markdown.
- For wildcard days, still follow the structure and pick a language that differs from the workweek schedule.
- Topic Preview, Fun Fact, and Tips must relate to the scheduled language ({language}).

Return only the finished Markdown post with the seven sections in the order listed."""


def generate_programming_tip(day_info: Dict[str, str]) -> str:
    """Use the Groq API to generate the daily post body."""

    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=0.4,
        max_tokens=2048,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(day_info)},
        ],
    )

    if not response.choices:
        raise RuntimeError("Groq completion response did not contain choices")

    content = getattr(response.choices[0].message, "content", None)
    if not content or not isinstance(content, str):
        raise RuntimeError("Received empty or non-string content from Groq completion")

    stripped = content.strip()
    if not stripped:
        raise RuntimeError("Groq completion content was blank after stripping whitespace")
    return stripped


def github_graphql(
    headers: Mapping[str, str],
    query: str,
    variables: Mapping[str, Any],
) -> Dict[str, Any]:
    """Execute a GitHub GraphQL request and surface any errors."""

    response = requests.post(
        GITHUB_GRAPHQL_ENDPOINT,
        headers=headers,
        json={"query": query, "variables": variables},
        timeout=30,
    )
    response.raise_for_status()
    payload: Dict[str, Any] = response.json()
    if "errors" in payload:
        raise RuntimeError(f"GitHub GraphQL error: {payload['errors']}")
    return payload["data"]


def fetch_repository_id(headers: Dict[str, str]) -> str:
    """Retrieve the repository node ID required for creating a discussion."""

    data = github_graphql(
        headers,
        """
        query($owner: String!, $name: String!) {
          repository(owner: $owner, name: $name) {
            id
          }
        }
        """,
        {"owner": REPO_OWNER, "name": REPO_NAME},
    )
    repo = data.get("repository")
    if not isinstance(repo, Mapping) or "id" not in repo:
        raise RuntimeError("Unable to resolve repository ID from GitHub API response")
    repo_id = repo.get("id")
    if not isinstance(repo_id, str) or not repo_id:
        raise RuntimeError("GitHub repository ID was missing or invalid")
    return repo_id


def create_discussion(headers: Dict[str, str], repo_id: str, title: str, body: str) -> str:
    """Create the GitHub Discussion and return the resulting URL."""

    data = github_graphql(
        headers,
        """
        mutation($input: CreateDiscussionInput!) {
          createDiscussion(input: $input) {
            discussion {
              url
            }
          }
        }
        """,
        {
            "input": {
                "repositoryId": repo_id,
                "categoryId": DISCUSSION_CATEGORY_ID,
                "title": title,
                "body": body,
            }
        },
    )

    create_discussion = data.get("createDiscussion")
    discussion = None
    if isinstance(create_discussion, Mapping):
        discussion = create_discussion.get("discussion")

    if not isinstance(discussion, Mapping) or "url" not in discussion:
        raise RuntimeError("GitHub did not return a discussion URL")
    url = discussion.get("url")
    if not isinstance(url, str) or not url:
        raise RuntimeError("GitHub discussion URL was missing or invalid")
    return url


def main() -> None:
    day_info = get_current_day_info()
    print(f"Generating Daily Programming Insight for {day_info['day_name']} ({day_info['date']})")

    post_body = generate_programming_tip(day_info)
    title = f"Daily Programming Insight — {day_info['date']} ({day_info['day_name']})"

    if DRY_RUN:
        print("DRY_RUN enabled - not posting to GitHub.")
        print("--- Generated Post ---")
        print(post_body)
        return

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }

    repo_id = fetch_repository_id(headers)
    discussion_url = create_discussion(headers, repo_id, title, post_body)
    print(f"Discussion created successfully: {discussion_url}")


if __name__ == "__main__":
    main()
