This module handles everything for a single homeserver instance. Resposibilities include:

1. Create user
2. Create room
3. Create Bridge
4. Delete Bridge
5. Send message
etc.


Tasks
---

1. Create new instance of a homeserver
    a. register bridge manager appservice
    b. create postgres instance
    c. create admin user
    d. register details with the bridge manager

2. Implement bridge manager
    a. scalable appservice instance
    b. be able to deploy on remote servers
        a. the docker sdk can connect to remote clients
    

3. Create client to manage homeserver
