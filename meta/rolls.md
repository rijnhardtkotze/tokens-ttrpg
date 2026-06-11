# Rolls Ledger

Append-only record of every die ever cast. Rows are written by the GM driver,
never by hand and never by the LLM. Verify any row:
`python3 scripts/dice.py --entropy <entropy sha> --pr <pr> --id <action id> --expr <expr>`

| Turn | PR | Action id | Expr | Dice | Total | Entropy SHA |
|---|---|---|---|---|---|---|
