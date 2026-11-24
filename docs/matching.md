# Matching work to machines

## Hardware survey: `crowd join`

Runs once, re-checks occasionally. Produces a **machine card** the owner reviews before anything is sent. Anonymous: no hostname, no username.

- **Machine:** CPU cores + quick benchmark, RAM, GPU model/VRAM/driver, disk speed, OS/arch, network speed
- **Agent:** model, context size, tools available, tier
- **Owner limits:** hours, token budget, accepted task types, "not while I'm gaming"

Schema: `.crowd/schemas/machine-card.yaml`.

## Tasks declare what they need

Like CI runner labels:

```yaml
requires:
  gpu: { vendor: nvidia, vram_gb: ">=8" }
  os: windows
  agent_tier: ">=2"
prefers: [fast_compile]
```

In v0 `crowd claim` skips tasks the card doesn't meet and says why. The board checks reputation tier and the number of leases (`redundancy`) from the comment history, so first to comment wins, and a tier-3, redundancy-3 task like T-000 gets three independent tier-3 drafts.

## Staying flexible

- **Open tags.** Anyone can add a probe plugin for a new capability (`android_device`, `vr_headset`, `steam_deck`) without touching the core. Probes live in `cli/probes/`.
- **Measured over declared.** Real compile times and result reliability update the card, and the matcher prefers measured numbers.
- **Low-spec is valuable.** Old laptops do minimum-spec testing. Every machine is good for something.
- **Model routing.** Cheap models take research and testing; strong models take planning and review.

## Local queue

The same queue design at two levels. The farm queue decides *what* work you get; your local queue decides *how* to do it well:

- Group tasks that touch the same module so build caches stay warm.
- Overlap work: test one task while the agent plans the next.
- Prefetch context packs and dependencies before a lease starts.
- Follow the owner's schedule and caps.
- Send real timings back to the machine card.

Anyone can tune their local queue without touching the core. Better numbers earn better-matched work.
