1. The bridge manager should be able to create and delete bridges
    a. create an entry in the bridge_manager.bridge_bots table
    c. every bridge needs a unique ID
    d. unique bridge IDs need to be used username templates to distinguish overlapping contacts in the matrix profiles table

2. The bridge manager needs to be flexible and recognise the associated homeserver, and bridge the requests belong to.
    a. Create an instance of a homeserver (ip, port, login etc.)
    b. Ensure the bridge manager is registered with the homeserver
    c. Maintain a list of bridges and the homeservers they're associated with
    
3. create a docker file to run the bridge manager