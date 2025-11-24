Iterate fast, like fix and repair. 2 LLMs:

1. Get info via asknews (use positive / negave example checking with step 2)
2. Make prediction
3. Continue until convergence but step 2 is only conditioned on previous step 1s (not step 2 unless we find that helps)

Look for good / bad reasoning on both sides and use examples both sides

System prompt is used for unlocking capability and reasoning style.

system = role + global rules, user = task + examples + data

Primarily change system prompt
