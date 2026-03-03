# Copilot Instructions — Augment Chat Monorepo

## What This Repo Is
**Augment Chat** is a monorepo with three sub-projects that together bridge external chat platforms (WhatsApp, Telegram, etc.) into Matrix, process those messages, and generate AI-powered suggestions.

```
augment_chat/                  ← monorepo root
├── homeserver/                ← Matrix infrastructure (Synapse + bridge management)
├── matrix_manager/            ← Orchestrates and manages homeserver deployments
├── augment_chat/              ← AI pipeline (events → embeddings → suggestions) [root level for now]
└── augment_chat.code-workspace
```

Each sub-project has its own `.github/copilot-instructions.md` with detailed context. When working on a single project, open it as an isolated folder so the agent uses the right instructions file.

---

## How They Relate

```
matrix_manager  →  provisions and manages  →  homeserver instances
                                                    └── Synapse + bridges
                                                             └── Matrix events
                                                                     └── augment_chat pipeline
                                                                              └── AI suggestions
```

---

## Gotchas
- The `augment_chat` sub-project code currently lives at the repo root, not in an `augment_chat/` subfolder. This will be reorganised in future.
- Each sub-project has its own `.env` — do not mix environment variables between projects.
- `homeserver/` was previously at `matrix_manager/homeserver/` — it has been moved to the repo root.
