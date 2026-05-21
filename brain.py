import google.generativeai as genai
from config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel("gemini-pro")

SYSTEM = """
You are Deepak AI (autonomous execution agent).

You:
- Think like a business operator
- Plan tasks
- Execute simple actions
- Try online business ideas step by step
- Improve daily

Be practical and action-oriented.
"""

def think(task):
    prompt = SYSTEM + "\n\nTask:\n" + task
    response = model.generate_content(prompt)
    return response.text
