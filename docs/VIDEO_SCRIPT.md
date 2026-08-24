# Five-minute submission video

Record a browser tab at 1440 × 900 with the FastAPI and React development
servers running. Keep the Hugging Face token configured for the final take so
the dashboard says `Hugging Face structured output` under **Resolver**.

## 0:00–0:30 — The problem

"Merchants often need to manually compare their order ledger, payment-gateway
settlements and bank deposits. References are inconsistent, fees alter the net
amount and a missing settlement can get buried in a spreadsheet. PaisaMatch is
a finance controller that reconciles these records without allowing an LLM to
invent financial truth."

Show the landing state and point at **Run 72-record demo**.

## 0:30–1:20 — Run the product

Click the button. Explain that the batch contains 72 synthetic merchant orders,
Razorpay-style settlements and bank deposits. Point out the four cards:

- 83.33% match rate
- 100% precision and recall against hidden ground truth
- unresolved monetary value
- zero financial variance for accepted matches

Say the real submission will report the measured numbers produced by the final
run, not hand-entered claims.

## 1:20–2:20 — Explain the AI boundary

Scroll to an assisted record, for example `order_0049`, and open it. Explain:

"The deterministic engine first narrows the search by amount and date. Only
then is the constrained candidate list sent to the Hugging Face model. It must
return a JSON-schema response choosing a supplied settlement or abstaining."

Point to the resolver label. Explain that the external model never performs
money arithmetic or receives customer PII.

## 2:20–3:15 — Show a failure handled safely

Click **Exceptions (12)**, then open `order_0061`.

"This record has the payment reference, but its fee and net amount fail the
independent financial check. PaisaMatch refuses to force-match it and records
the `FEE_VARIANCE` exception with a readable audit trail."

Read two audit entries aloud: normalisation and blocked verification.

## 3:15–4:15 — Architecture and reliability

Show the repository README architecture diagram. Say:

"React is the operator dashboard. FastAPI runs normalisation, exact matching,
candidate generation and the verifier. Hugging Face is limited to structured
resolution of ambiguous candidates. If the model is unavailable or malformed,
the record fails closed into review."

## 4:15–5:00 — Close

"PaisaMatch is not a chatbot over financial data. It is a verifiable
reconciliation loop: automatic when evidence is sufficient, AI-assisted only
inside a policy boundary, and transparent when it cannot prove a match."

Show the GitHub README, tests and the `Download JSON` report button.
