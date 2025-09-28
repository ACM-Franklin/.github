#!/usr/bin/env python3
import os
import requests
import json
from datetime import datetime, timezone
from groq import Groq

# Configuration
GITHUB_TOKEN = os.environ['GITHUB_TOKEN']
GROQ_API_KEY = os.environ['GROQ_API_KEY']
REPO_OWNER = os.environ['REPO_OWNER']
REPO_NAME = os.environ['REPO_NAME']
DISCUSSION_CATEGORY_ID = "DIC_kwDOExample"  # Replace with your actual category ID

# Language schedule
LANGUAGE_SCHEDULE = {
    0: "Wildcard",      # Sunday
    1: "Python",        # Monday
    2: "Java",          # Tuesday
    3: "Go",            # Wednesday
    4: "JavaScript",    # Thursday
    5: "Wildcard",      # Friday
    6: "Wildcard"       # Saturday
}

DAY_NAMES = {
    0: "Sunday", 1: "Monday", 2: "Tuesday", 3: "Wednesday",
    4: "Thursday", 5: "Friday", 6: "Saturday"
}

def get_current_day_info():
    """Get current day and corresponding language"""
    now = datetime.now(timezone.utc)
    weekday = now.weekday() + 1 if now.weekday() != 6 else 0  # Convert to Sunday=0 format
    
    return {
        'day_name': DAY_NAMES[weekday],
        'language': LANGUAGE_SCHEDULE[weekday],
        'date': now.strftime('%Y-%m-%d')
    }

def generate_programming_tip(day_info):
    """Generate programming tip using Groq"""
    client = Groq(api_key=GROQ_API_KEY)
    
    pprompt = f"""You are an AI teaching assistant that writes a daily programming tip suited for beginners, formatted in Teams Markdown (basic markdown only, no emoji).

Language schedule by weekday:
- Monday → Python  
- Tuesday → Java  
- Wednesday → Go  
- Thursday → JavaScript  
- Friday / Saturday / Sunday → Wildcard (invented or niche). If wildcard, also include a short snippet in Python or JavaScript under "Alt Snippet:".

Use these parts, in this order:

---

**Daily Programming Insight — {day_info['day_name']}**

Hello team! I'm your AI learning companion, bringing today's programming knowledge boost.

**Fun Fact:**  
Something interesting about a syntax, keyword, function or concept in today's language — include year or origin if relevant.

**Code Snippet ({day_info['language']}):**  
```{day_info['language'].lower()}
# Runnable code with comments - make it practical and educational
Example Run:
COMMAND => OUTPUT
Core Concept:
Explain the main programming concept demonstrated in the code snippet.
How It Works:
Break down the mechanics step by step.
Why This Matters:
Real use cases and practical applications.
Try This:
A coding exercise to reinforce the concept.
Common Pitfall:
A mistake to avoid and how to prevent it.
Takeaway:
Clear summary statement.
{"Alt Snippet (Python/JavaScript): if wildcard" if day_info['language'] == 'Wildcard' else ""}
Today is {day_info['day_name']}, so use {day_info['language']}.
"""
