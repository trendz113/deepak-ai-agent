from groq import Groq
from config import GROQ_API_KEY

client = Groq(api_key=GROQ_API_KEY)

SYSTEM = """
You are Deepak AI (autonomous execution agent).

You:
- Think like a business operator
- Plan tasks
- Suggest actions
- Try online business ideas step-by-step
- Improve daily

Be practical and action-oriented.
"""

def think(task):
    response = client.chat.completions.create(
        model="llama3-70b-8192",  # fast + powerful
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": task}
        ]
    )

    return response.choices[0].message.content
