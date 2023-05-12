import requests
from typing import List, Dict, Any
from bs4 import BeautifulSoup

class KF6API:
    def __init__(self, url, username, password):
        self.login_credential = {
            'userName': username,
            'password': password
        }
        self.KF_URL = url
        self.token = self._login()
        self.author_id = None
        self.current_community = None
        self.temp_data = []

    def _login(self) -> str:
        res = requests.post(f"{self.KF_URL}/auth/local", json = self.login_credential)
        if res.status_code != 200:
            raise Exception("Something is not right", res)

        return res.json()['token']
        
    def _craft_header(self, content_type = False) -> Dict[str, str]:
        res = {"Authorization": f"Bearer {self.token}"}
        
        if content_type:
            res['Content-Type'] = 'application/json'
        
        return res

    def _get_word_count(self, content: str) -> int:
        return len(content.split(" ")) #TODO: this is very simple methods, should improve on

    def get_my_communities(self) -> List[Dict[str, Any]]:
        """Get the communities current user has registered"""
        headers = self._craft_header()
        res = requests.get(f"{self.KF_URL}/api/users/myRegistrations", headers=headers)
        
        # for simplicity just use this as a starting point, no need for all information for now.
        return [{
            'id': i['communityId'], 
            'title': i['_community']['title'], 
            'created': i['created']
            } for i in res.json()]

    def get_contributions(self, community_id: str):
        """
        get all the notes in the specified `community_id`. If you are only interested in a subset of notes, you 
        can pass in additional parameter `filter` with the target note ids.
        """

        if self.current_community == community_id: # don't need to retieve again, already in memory
            return

        body = {
            "query": {
                "type": "Note",
                "pagesize": "max",
                "status": "active"
            }
        }
        headers = self._craft_header(True)

        res = requests.post(f"{self.KF_URL}/api/contributions/{community_id}/search", headers = headers, json = body)
        responses = {i["_id"]: {
                "_id": i["_id"],
                "_type": i["type"],
                "authors": i["authors"],
                "title": i["title"],
                "text4search": i["text4search"],
                "wordCount": i['wordCount'],
                'status': i['status'],
                'data': i['data']['body'],
                'riseabove_view': i['data'].get('riseabove', {}).get('viewId', None),
                'processed_text': BeautifulSoup(i['data']['body'], 'html').get_text().strip('\n').replace(u'\xa0', u' ')
            } for i in res.json()}
       
        self.current_community = community_id
        self.temp_data = responses
        print("contributions has been saved in the memory")

    def get_views(self, community_id: str) -> List[Dict[str, Any]]:
        """
        Get the view from a particular community
        """
        res = requests.get(f"{self.KF_URL}/api/communities/{community_id}/views", headers= self._craft_header())
        # return res.json()
        return [{
            '_id': i['_id'],
            'title': i['title'],
            'created': i['created'],
            'modified': i['modified'],
            'type': i['type']
            } for i in res.json() if i['status'] == 'active']

    def get_notes_from_view(self, community_id: str, view_id: str) -> List[Any]:
        if community_id != self.current_community:
            self.get_contributions(community_id)

        body = {
            "query": {
                "type": "contains",
                "from": view_id,
                "_to.type": "Note",
                "_to.status": "active"
            },
        }
        res = requests.post(f"{self.KF_URL}/api/links/{community_id}/search", headers= self._craft_header(), json= body)
        if res.json(): 
            print("VIEW TITLE:", res.json()[0]["_from"]["title"])

        riseaboves = []
        target_ids = [i['to'] for i in res.json()]
        result = []
        for i in target_ids:
            data = self.temp_data[i]
            result.append(data)
            
            riseabove_view = data['riseabove_view']
            if riseabove_view:
                riseaboves.append(riseabove_view)
        
        while riseaboves:
            ra_view_id = riseaboves.pop(0)
            result += self.get_notes_from_view(community_id, ra_view_id)

        return result
    
    def create_contribution(self, community_id: str, view_id: str, title: str, content: str):
    
        res_authors = requests.get(f"{self.KF_URL}/api/authors/{community_id}/me", headers= self._craft_header())
        self.author_id = res_authors.json()["_id"]
        contribution = {
            'communityId': community_id,
            'type': "Note",
            'title': title,
            'authors': [self.author_id],
            'status': 'active',
            'permission': 'protected',
            '_groupMembers': [],
            'data': {
                'body': content,
            },
            'wordCount': self._get_word_count(content),
            'text4search': f"( {title} ) {content} () [kf6py]",
        }
        #create contribution
        res_contri = requests.post(f"{self.KF_URL}/api/contributions/{community_id}", headers= self._craft_header(), json= contribution)
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
        res_link = requests.post(f"{self.KF_URL}/api/links/", headers= self._craft_header(), json=link_obj)

        return