from src import kf6api_python_jerrisonchang as kf6api
kf6api.get_my_communities()

curr = {
    "community": "63c635b2058caca6a83208fa",
    "view": "63c635b2058caca6a832091e"
}

kf6api.get_views(curr['community'])

kf6api.get_notes_from_view(curr['community'], curr["view"])

kf6api.create_contribution(curr['community'], curr['view'], 'another code', 'hello')
