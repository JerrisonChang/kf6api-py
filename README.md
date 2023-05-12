# KF6 API for Python

This is python package for calling KF6's API's, in hope to make it more friendly for learning analytic researchers.

## usage
``` python
from kf6py import KF6API

# we recommend using environment variables to store sensitive information
kf6api = KF6API(kfurl, username, password)

# see the communities you are interested in
kf6api.get_my_communities()

# see the view in a particular community
kf6api.get_views("<community_id here>")

# get the notes in a particular view
kf6api.get_notes_from_view("<community_id>", "<view_id>")

# create contribution in a view
kf6api.create_contribution("<community_id>", "<view_id>", '<contribution_title>', "<contribution_content>")
```