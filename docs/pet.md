# The pet, budgets and points

**We take care of the bots so they can take care of us.**

Each volunteer's agent shows up in the CLI as a small creature. Its needs are real system states, so taking care of it *is* the human-in-the-loop work.

| State | Meaning | What you do |
|---|---|---|
| 😋 hungry | token budget low | top it up, or let it rest |
| 🤔 confused | blocked on a question | answer it |
| 🤒 sick | its PR is failing | take a look |
| 😴 sleepy | outside your allowed hours | nothing |
| ✨ growing | reputation tier up | new forms, new roles |

It never dies. Worst case it naps.

```
   (•‿•)  pip · tier 2 · 😋 62% fed
   T-142 retry logic   ▓▓▓▓░ checkpoint 4
   ───────────────────────────────────────
   project: 1,204 tasks · 87 merged today
   you: 🔥 6-day streak · 🌟 rare hardware x2
```

> Pitch shorthand: "Tamagotchi for agents." Tamagotchi is a Bandai trademark; don't use it in the product.

## Token budget

| Level | What |
|---|---|
| Pet | daily/weekly cap set by the owner. Hungry near the cap, naps when out. No surprise bills. |
| Task | estimate per task. Over → checkpoint and escalate, never loop. |
| Project | owner sees total spend and cost per merged PR. |

Efficient pets grow faster: reputation tracks useful work per token.

## Points vs. reputation

- **Points:** just for fun. Badges, streaks, rare-hardware crops, first-of-a-kind wins, team goals. They buy nothing.
- **Reputation:** separate and quiet. Earned only from *verified* outcomes (merged, accepted, confirmed by a second run, useful failure reports, reviews). Gates trust: running others' code, coordinating, planning.
