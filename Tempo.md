# Tempo

**Tempo keeps you at your pace.**

Tempo is an AI agent that reads how focused you are through an EEG headband. When it sees you getting tired, it buys what you need to keep going, within limits you set once. The first version orders coffee.

---

## The problem

When you're deep in work, your focus fades. You notice too late, and fixing it means stopping.

- **Fatigue creeps in.** Focus drops over minutes. You usually notice only when you're already making mistakes.
- **The fix breaks your flow.** Getting a coffee means stopping, picking a shop, choosing, paying and waiting. Every step pulls you out of the work.
- **So people push through, tired.** They put off the break, and the work suffers.

Today the only thing that notices your fatigue is you, at the moment you're least able to.

## The solution

Tempo watches your focus so you don't have to. It has three jobs:

1. **Sense:** estimate your focus level from brain activity, live.
2. **Decide:** when you've been fading for a sustained period, choose what to get you, based on your rules.
3. **Act:** buy it through Reap's agentic checkout and tell you it's on the way. You never open an app or type a request.

---

## How it works

```
Muse headband ──► BCI server ──► Agent server ──► Reap Agentic API ──► Merchant
   (EEG)          (state)         (rules + buy)    (discover, quote,     (Dutch Colony)
                                                    checkout)
                        └──────────► Web app (focus, orders, controls)
```

### 1. Sensing: Muse headband
- **Electrodes:** four EEG channels: TP9 and TP10 behind the ears, AF7 and AF8 on the forehead. FPZ is the reference.
- **Signal:** the BCI server measures the strength of the standard EEG frequency bands. As people get drowsy, theta (4–8 Hz) and alpha (8–12 Hz) activity typically rises and beta (13–30 Hz) falls. Tempo turns these readings into one **focus score**.
- **Second signal (planned):** blink rate and eye-closure from the webcam, to confirm fatigue and cut false alarms.

### 2. State
The focus score maps to three states:

| State | Meaning | What Tempo does |
|---|---|---|
| **Focused** | Normal working level | Nothing |
| **Fading** | Score falling | Shows a warning in the app |
| **Tired** | Score below the threshold for a sustained window | Starts an order |

The threshold must hold for a set window, so a single blink or head movement doesn't trigger a purchase.

### 3. Acting: the agent
When the state turns **Tired**, the agent server:
1. Checks the request against the user's spending rules (below).
2. Uses **Reap's Agentic module** to find the product and get a live price.
3. Re-checks the price against the rules.
4. Shows a short cancel countdown in the web app.
5. Checks out through Reap and reports the result.

### 4. Paying: Reap
- All purchasing goes through Reap's Agentic API: product discovery, pricing and checkout.
- The card is held by Reap. **The AI never sees card details.**
- Checkout is simulated in the sandbox, so nothing is actually delivered.

---

## Spending controls

The user sets these once. **The rules are enforced in code, not by the AI**, so the model can't talk its way past a limit.

| Control | Proposed default | Why |
|---|---|---|
| Daily budget | S$15 | Hard cap on what Tempo can spend per day |
| Price cap per order | S$8 | Blocks anything unexpectedly expensive |
| Max orders per day | 3 | Also limits caffeine |
| Cooldown between orders | 90 min | Stops repeat orders on a long dip |
| Cutoff time | No coffee after 16:00 | Protects sleep |
| Cancel window | 10 s | User can stop any order with one tap |
| Default order | 5oz Black, Dutch Colony | No decision needed when tired |

When a rule blocks an order, Tempo says why. For example: *"You're tired, but it's past 4pm. No coffee. Take a break instead."*

---

## What the user sees (web app)

- **Live focus meter:** the current focus score and state (Focused / Fading / Tired).
- **Companion:** a character that speaks for Tempo, e.g. *"You're tired. Getting you a coffee."*
- **Order card:** the item, merchant, price and a cancel countdown.
- **Payment states:** each one shown clearly: *Checking rules → Getting price → Paying → Paid*, or *Blocked (reason)* / *Failed (reason)*.
- **Today:** what's been spent against the budget, orders left and the time of the next allowed order.
- **Controls:** the spending rules above, editable.

---

## Privacy

- **Raw EEG stays on the BCI server.** Only the state and a confidence score are passed to the agent.
- **No card details reach the AI.** Payment goes through Reap.
- Tempo estimates focus for convenience. **It is not a medical device** and makes no health claims.

---

## Scope

**MVP (this hackathon)**
- Muse headband → focus score → Tired state
- Agent orders one coffee from Dutch Colony through Reap Agentic (sandbox)
- Spending controls enforced, including at least one visible "blocked" case
- Web app showing focus, the order and the payment result

**Next**
- Webcam fatigue signal alongside EEG
- More than coffee: water, a snack or lunch when you've skipped a meal, or simply a break
- Learning the user's patterns: when they dip and what actually helps

---

## Merchant

- **Dutch Colony** (`dutchcolony.sg`, Singapore) is on Reap's supported merchant list.
- **Single-cup items:** 5oz Black (S$4.50), Espresso (S$3), Matcha Latte (S$6), plus bottled chilled drinks.
- **To verify:** that these items work through the sandbox checkout. The merchant sheet's test item is a bag of beans.

---

## Hackathon fit

- **Prize track:** Most Worthwhile Problem.
- **Themes:** Everyday life and Business spend.
- **Core:** the purchase can't happen without Reap's Agentic module.
- **Permission and limits:** clearly visible.
- **Not a search-and-buy chatbot:** the purchase is triggered by the user's state, not a typed request.
- **Rules:** coffee is not a restricted category, and the AI never handles card data.

---

## Open questions

- Focus-score threshold and window length: to tune on the real headband.
- Live or scripted fatigue trigger for the demo video.
- Whether single-cup Dutch Colony items check out in the sandbox.
