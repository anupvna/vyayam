"""The AI coach: explains the engine's decisions and proposes changes the engine checks.

Flow for one message (see service.py):
  1. safety.screen()     -> risky topics get a fixed, safe answer; no AI involved
  2. context.build()     -> the user's real data (plan, targets, progress) as JSON
  3. providers           -> Groq, then Gemini, each asked for a JSON reply
  4. checks              -> reply safety, numbers grounded in the data, valid actions
  5. engine_reply        -> a rule-based answer if every provider fails
"""
