import requests
from typing import List, Dict, Any
import dotenv
import os
from bs4 import BeautifulSoup

dotenv.load_dotenv()

KF_URL = os.environ.get("KF6_URL")

STATES = {
    'login_credential': {
        'userName': os.environ.get("KF6_USERNAME"),
        'password': os.environ.get("KF6_PASSWORD")
    },
    'token': None, # this will be filled automatically later
    'author_id': None,
}

def check_login(func):
    """
    first step that needs to be done before anything else
    """
    def log_in(*args, **kwargs):
        if STATES['token']:
            return func(*args, **kwargs)

        res = requests.post(f"{KF_URL}/auth/local", json = STATES["login_credential"])
        if res.status_code != 200:
            raise Exception("Something is not right", res)

        STATES['token'] = res.json()['token']
        return func(*args, **kwargs)

    return log_in

def craft_header(content_type = False) -> Dict[str, str]:
    res = {"Authorization": f"Bearer {STATES.get('token')}"}
    if content_type:
        res['Content-Type'] = 'application/json'
    return res
 
@check_login
def get_my_communities() -> List[Dict[str, Any]]:
    """Get the communities current user has registered"""
    headers = craft_header()
    res = requests.get(f"{KF_URL}/api/users/myRegistrations", headers=headers)
    
    # for simplicity just use this as a starting point, no need for all information for now.
    return [{
        'id': i['communityId'], 
        'title': i['_community']['title'], 
        'created': i['created']
        } for i in res.json()]

@check_login
def get_contributions(community_id: str, *, filter: List[str]=None) -> List[Dict[str, Any]]:
    """
    get all the notes in the specified `community_id`. If you are only interested in a subset of notes, you 
    can pass in additional parameter `filter` with the target note ids.
    """
    body = {
        "query": {
            "type": "Note",
            "pagesize": "max",
            "status": "active"
        }
    }
    headers = craft_header(True)

    res = requests.post(f"{KF_URL}/api/contributions/{community_id}/search", headers = headers, json = body)
    response = [{
            "_id": i["_id"],
            "_type": i["type"],
            "authors": i["authors"],
            "title": i["title"],
            "text4search": i["text4search"],
            "wordCount": i['wordCount'],
            'status': i['status'],
            'data': i['data']['body'],
            'processed_text': BeautifulSoup(i['data']['body'], 'html').get_text().strip('\n').replace(u'\xa0', u' ')
        } for i in res.json()]

    if filter:
        return [i for i in response if i["_id"] in filter]
    else:
        return response


@check_login
def get_views(commuitny_id: str) -> List[Dict[str, Any]]:
    """
    Get the view from a particular community
    """
    res = requests.get(f"{KF_URL}/api/communities/{commuitny_id}/views", headers= craft_header())
    # return res.json()
    return [{
        '_id': i['_id'],
        'title': i['title'],
        'created': i['created'],
        'modified': i['modified'],
        'type': i['type']
    } for i in res.json() if i['status'] == 'active']

@check_login
def get_notes_from_view(community_id: str, view_id: str) -> List[str]:
    body = {
        "query": {
            "type": "contains",
            "from": view_id,
            "_to.type": "Note",
            "_to.status": "active"
        },
    }
    res = requests.post(f"{KF_URL}/api/links/{community_id}/search", headers= craft_header(), json= body)
    if res.json(): 
        print("VIEW TITLE:", res.json()[0]["_from"]["title"])

    target_ids = [i['to'] for i in res.json()]
    return get_contributions(community_id, filter= target_ids)
    

def get_word_count(content: str) -> int:
    return len(content.split(" ")) #TODO: this is very simple methods, should improve on

@check_login
def create_contribution(community_id: str, view_id: str, title: str, content: str):
    
    res_authors = requests.get(f"{KF_URL}/api/authors/{community_id}/me", headers=craft_header())
    STATES['author_id'] = res_authors.json()["_id"]
    contribution = {
        'communityId': community_id,
        'type': "Note",
        'title': title,
        'authors': [STATES['author_id']],
        'status': 'active',
        'permission': 'protected',
        '_groupMembers': [],
        'data': {
            'body': content,
        },
        'wordCount': get_word_count(content),
        'text4search': f"( {title} ) {content} ()",
    }
    #create contribution
    res_contri = requests.post(f"{KF_URL}/api/contributions/{community_id}", headers=craft_header(), json= contribution)
    #create link to the view
    
    # get position
    position = { #TODO: move to last
        'x': 10,
        'y': 10
    }

    link_obj = {
        'from': view_id,
        'to': res_contri.json()['_id'],
        'type': 'contains',
        'data': position
    }
    res_link = requests.post(f"{KF_URL}/api/links/", headers=craft_header(), json=link_obj)

    return

