SMURK AI Directional Score Display Fix

Replace ONLY app.py in the root of the smurk-ai GitHub repository.
Do not replace engine.py or requirements.txt for this fix.
The app recalculates UP/DOWN scores from the current indicators if score fields are missing or both scores are zero.
This remains paper-only and does not place Kalshi orders.
