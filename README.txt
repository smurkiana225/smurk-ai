SMURK AI — Final Safety Filter Update

Replace ONLY app.py in the root of your existing smurk-ai GitHub repository.
Leave engine.py and requirements.txt unchanged.

Changes:
- Shows approximate break-even win-rate threshold from the displayed ask plus entered fee estimate.
- Explains that indicator agreement is not a calibrated win probability.
- Keeps the entry screen at WAIT until a validated probability model can be compared against break-even.
- Flags contradictory completed-candle momentum versus the overall directional signal.

This is a paper-only research tool. It does not place orders and does not guarantee results.
Enter a realistic fee estimate; zero is a placeholder only.
