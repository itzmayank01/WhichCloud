# Model keys, and what happens when one runs out

A description is read by a model. Free tiers are small -- Gemini's is twenty
requests a day -- and they run out mid-sentence rather than at a convenient
moment, so WhichCloud takes a list of keys and works down it.

## Adding a key

Set it in the environment. Nothing else changes.

```bash
# the first one tried
GEMINI_API_KEY=...

# more of the same, used in order when the one before is exhausted
GEMINI_API_KEY_2=...
GEMINI_API_KEY_3=...

# a different service, tried after every Gemini key is spent
GROQ_API_KEY=...
GROQ_API_KEY_2=...

# billed, so tried last
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
```

One variable can hold several keys, so `GEMINI_API_KEY="a,b,c"` is three.
Duplicates are dropped -- the same key twice is one exhausted quota, not two
chances.

`GET /health` reports how many keys each provider has. Counts only; a key
never reaches a log, a response or a screen.

## Where to get them

| Provider | Free tier | Sign up |
|---|---|---|
| Gemini | 20 requests/day per key | aistudio.google.com/apikey |
| Groq | generous, rate-limited per minute | console.groq.com/keys |
| OpenAI | none, billed | platform.openai.com/api-keys |
| Anthropic | none, billed | console.anthropic.com |

Several Google accounts each give their own Gemini key, which is the cheapest
way to raise the daily ceiling.

## What moves to the next key

Only "not now" answers: quota exhausted, rate limited, overloaded, or an empty
credit balance. A description the model cannot parse fails the same way on
every provider, so it is reported once rather than retried four times.

When every key is spent the error says so plainly, and names which were tried.
Descriptions read earlier still open instantly -- they come from the
extraction cache and need no model at all.
