SMURK AI — Entry Price & Payout Filter

Replace ONLY app.py in the root of the existing smurk-ai GitHub repository.
Do not replace engine.py or requirements.txt.

This update adds:
- Side-specific UP/YES and DOWN/NO spread calculations.
- A conservative paper-only entry screen.
- Estimated maximum payout and maximum loss per contract.
- A configurable per-contract fee estimate.
- WAIT when direction, spread, or potential payout conditions do not pass.

Screening defaults:
- Matching directional signal required.
- Side spread must be 5 cents or less.
- Estimated net upside if correct must be at least 10 cents per contract.

These are screening rules, not validated profitable thresholds or win probabilities.
The app remains paper-only and does not submit Kalshi orders.
