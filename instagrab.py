# This Python file uses the following encoding: utf-8
"""Script to pull down large volumes of instagram photos from a specified account."""

import json
from collections import namedtuple

import requests
from bs4 import BeautifulSoup

Photo = namedtuple('Photo', ['ig_id', 'likes', 'posted', 'url', 'code', 'caption'])

class Instagrab(object):
    """Class to pull images/image meta from Instagram."""
    instagram = 'https://instagram.com'

    def __init__(self):
        self._session = requests.Session()

    def list_images(self, account):
        """List all of the instagram photos."""
        page = self._session.get('%s/%s/' % (self.instagram, account))

        soup = BeautifulSoup(page.text)
        blob = self._extract_json_datablob(soup)

        """
              "has_previous_page": false,
              "start_cursor": "1418024076480334792",
              "end_cursor": "1366752520647469950",
              "has_next_page": true
        """

        page_info = blob['entry_data']['ProfilePage'][0]['user']['media']['page_info']

        # Pull out all the relevent information for all of the images. Exclude videos.
        photos = [Photo(ig_id=x['id'],
                        likes=x['likes']['count'],
                        posted=x['date'],
                        url=x['display_src'],
                        code=x['code'],
                        caption=x['caption'])
                  for x in blob['entry_data']['ProfilePage'][0]['user']['media']['nodes']
                  if x['is_video'] is False]

        return photos

    def _extract_json_datablob(self, soup):
        prefix = 'window._sharedData ='
        candidates = [x.text for x in soup.find_all('script')
                      if x.text.startswith(prefix)]
        if len(candidates) != 1:
            raise RuntimeError
        else:
            return json.loads(candidates[0][len(prefix): -1])

    def wip(self):
        self._session.cookies.set('ig_vw', '1366')
        self._session.cookies.set('ig_pr', '1')
        headers = {'x-csrftoken': self._session.cookies['csrftoken'],
                   'referer': 'https://www.instagram.com/blobyblo/'}
        data = {'q': """ig_user(15882249) { media.after(1359915155178026105, 12) {
              count,
              nodes {
                caption,
                code,
                comments {
                  count
                },
                comments_disabled,
                date,
                dimensions {
                  height,
                  width
                },
                display_src,
                id,
                is_video,
                likes {
                  count
                },
                owner {
                  id
                },
                thumbnail_src,
                video_views
              },
              page_info
            }
             }""",
            'ref': 'users::show',
            'query_id': '17846611669135658'}
        url = 'https://www.instagram.com/query/'
        response = self._session.post(url, data=data, headers=headers)

        print json.dumps(response.json(), indent=2)


#Instagrab.list_images('blobyblo')
a = Instagrab()
a.list_images('blobyblo')
a.wip()

exit(0)
print
print """
curl 'https://www.instagram.com/query/' -H 'x-csrftoken: w2JfJdWzerurUQQkjBi8uSOeK687B3YN' -H 'cookie: mid=WGmL_AAEAAGFE9xFkkhxp7dFkhG0; s_network=""; csrftoken=w2JfJdWzerurUQQkjBi8uSOeK687B3YN; ig_pr=1; ig_vw=1366' -H 'referer: https://www.instagram.com/blobyblo/' --data 'q=ig_user(15882249)+%7B+media.after(1366752520647469950%2C+12)+%7B%0A++count%2C%0A++nodes+%7B%0A++++caption%2C%0A++++code%2C%0A++++comments+%7B%0A++++++count%0A++++%7D%2C%0A++++comments_disabled%2C%0A++++date%2C%0A++++dimensions+%7B%0A++++++height%2C%0A++++++width%0A++++%7D%2C%0A++++display_src%2C%0A++++id%2C%0A++++is_video%2C%0A++++likes+%7B%0A++++++count%0A++++%7D%2C%0A++++owner+%7B%0A++++++id%0A++++%7D%2C%0A++++thumbnail_src%2C%0A++++video_views%0A++%7D%2C%0A++page_info%0A%7D%0A+%7D&ref=users%3A%3Ashow&query_id=17846611669135658'
"""
