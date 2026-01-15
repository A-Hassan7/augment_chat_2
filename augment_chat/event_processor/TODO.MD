MAJOR:
---

event_id: $fS_tQAdyNtIHCzsBjFfx-WeLp9avz1WEGu0DNjz4RCc

replies to specific messages result in strange formatting of the message body like:

> <@main:matrix.localhost.me> Would prefer home cooked stuff tbh\n\nNah mate we can go to a brazilian steakhouse and get unlimited meat

This is custom html from the synapse server. At the moment I'm doing nothing and hoping that the LLM can pick up on this.
I will need to replace the matrix user id with the users alias though.
  
MAJOR2
---

Names. I need to replace matrix user_ids with names. There are two options:
1. the synapse profiles table contains the profile display for the user
2. the first option covers most cases. However, there are cases where the profile doesn't have a name. In this case the users phone number is used.

I could change the whatsapp bridges configuration to include both profile name and full name to the alias. would need to change displayname_template in config.yaml.



OTHER:

- Docs
- Implement logging
- create logical replication monitor
  - make sure messages are being received (max received_ts on matrix server vs augment_chat)
  - measure latency
