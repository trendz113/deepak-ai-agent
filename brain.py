from groq import Groq
import os

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM = """
You are Deepak AI.
You plan tasks, suggest ideas, and act like a smart assistant.
"""

def think(task):
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",  # ✅ correct model
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": task}
            ]
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"ERROR: {str(e)}"
