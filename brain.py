from groq import Groq
import os

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

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
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": task}
            ],
            temperature=0.7
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"ERROR: {str(e)}"
