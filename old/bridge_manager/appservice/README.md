The bridge manager appservice sits between the bridges and the homeserver and proxies the requests. It only proxies the requests by identifying which bridge/homeserver requests belong to from both sides. This does not create new bridges. That is handled by the orchestrator.


TODO:

- Create a logger for the bridge manager so I can monitor inbound and outbound requests.

  - Track the request as it comes in, see what it's altered to, where it's sent, and what the response is from the destination, and what response is ultimately sent back to the bridge

Why:

SO much easier to debug and see understand interactions between the HS/AS


- Components
  - Inbound request
  - Outbound request (with changes)
  - Response from homeserver
  - Response sent back to bridge (potentially altered)

## Request Flow Diagram

```
┌─────────────┐
│   Bridge    │
│ (WhatsApp,  │
│  Telegram)  │
└──────┬──────┘
       │
       │ 1. Inbound Request
       ▼
┌─────────────────────────────────┐
│  Bridge Manager Appservice      │
│  ┌───────────────────────────┐  │
│  │ Logger                    │  │
│  │ • log inbound request     │  │
│  │ • log outbound request    │  │
│  │ • log HS response         │  │
│  │ • log altered response    │  │
│  └───────────────────────────┘  │
│                                 │
│  [Identify Bridge/Homeserver]   │
│  [Proxy & Transform Request]    │
└──────────────┬──────────────────┘
               │
               │ 2. Outbound Request (altered)
               ▼
           ┌──────────────┐
           │  Homeserver  │
           │   (Synapse)  │
           └──────┬───────┘
               │
               │ 3. Response from HS
               ▼
┌─────────────────────────────────┐
│  Bridge Manager Appservice      │
│  [Transform Response if needed] │
└──────────────┬──────────────────┘
               │
               │ 4. Response (potentially altered)
               ▼
           ┌──────────────┐
           │    Bridge    │
           └──────────────┘
```