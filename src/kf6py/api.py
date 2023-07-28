import requests
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

class KF6API:
    def __init__(self, url: str, username: str, password: str):
        self.login_credential = {
            'userName': username,
            'password': password
        }
        self.KF_URL = url.strip('/ ')
        self.token = self._login()
        self.author_id = None
        self.current_community = None
        self.temp_data = {} # holds contributions map in current community

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
        responses = {i["_id"]: self._simplify_notes(i) for i in res.json()}

        self.current_community = community_id
        self.temp_data = responses
        print("contributions has been saved in the memory")

    def _simplify_notes(self, note_obj) -> Dict[str, Any]:
        processed_text = BeautifulSoup(note_obj['data']['body'], features="html.parser").get_text().strip('\n').replace(u'\xa0', u' ')
        return {
            "_id": note_obj["_id"],
            "_type": note_obj["type"],
            "authors": note_obj["authors"],
            "title": note_obj["title"],
            "text4search": note_obj["text4search"],
            "wordCount": note_obj.get('wordCount', self._get_word_count(processed_text)),
            'status': note_obj['status'],
            'created': note_obj['created'],
            'data': note_obj['data']['body'],
            'riseabove_view': note_obj['data'].get('riseabove', {}).get('viewId', None),
            'processed_text': processed_text
        }

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
            data = self.temp_data.setdefault(i, self._simplify_notes(self.get_single_object(i)))
            result.append(data)

            riseabove_view = data.get('riseabove_view', None) # this helps for some scheme where this doesn't exist
            if riseabove_view:
                riseaboves.append(riseabove_view)

        while riseaboves:
            ra_view_id = riseaboves.pop(0)
            result += self.get_notes_from_view(community_id, ra_view_id)

        return result

    def get_single_object(self, object_id: str):
        response = requests.get(f"{self.KF_URL}/api/objects/{object_id}", headers=self._craft_header() ).json()
        return response

    def get_links(self, community_id: str, type: Optional[str] = None, succinct: bool = True):
        body = {
            'query': {
                "_from.status": "active"
            }
        }
        if type:
            assert type in ['buildson', 'contains'] # support these for now...
            body['query']['type'] = type

        res_links = requests.post(f"{self.KF_URL}/api/links/{community_id}/search", headers=self._craft_header(), json=body)
        if succinct:
            return [{
                "from": i["from"],
                "to": i["to"]
            } for i in res_links.json()]
        else:
            return res_links.json()

    def get_notes_from_author(self, author_id: str) -> Dict:
        """get notes from a given author"""
        assert self.current_community is not None

        return {i: j for i, j in self.temp_data.items() if author_id in j["authors"]}


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

        # get position
        position = { #TODO: move to last
            'x': 10,
            'y': 10
        }

        link_obj = {
            'from': view_id, # create link to view
            'to': res_contri.json()['_id'],
            'type': 'contains',
            'data': position
        }
        res_link = requests.post(f"{self.KF_URL}/api/links/", headers= self._craft_header(), json=link_obj)

        return