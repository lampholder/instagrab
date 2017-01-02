# This Python file uses the following encoding: utf-8
"""Script to pull down large volumes of instagram photos from a specified account by simulating
a browser connection rather than using the dedicated (and rate-limited) API. I've undoubtedly
cargo-culted in a bunch of the magic numbers that seem to make requests work."""

import sys
import json
import threading
from StringIO import StringIO
from collections import namedtuple

import requests
from PIL import Image
from bs4 import BeautifulSoup
from pymongo import MongoClient

Photo = namedtuple('Photo',
                   ['ig_id', 'likes', 'posted', 'url', 'code', 'caption', 'owner_id', 'account_name'])

BatchMeta = namedtuple('BatchMeta',
                       ['start_cursor', 'end_cursor', 'has_previous_page', 'has_next_page'])

class Instagrab(object):
    """Class to pull images/image meta from Instagram."""
    instagram = 'https://www.instagram.com'

    def __init__(self):
        self._session = requests.Session()
        self._session.cookies.set('ig_vw', '1366')
        self._session.cookies.set('ig_pr', '1')

    def _get_first_page(self, account):
        """List all of the instagram photos."""
        first_page = self._session.get('%s/%s/' % (self.instagram, account))

        soup = BeautifulSoup(first_page.text)
        blob = Instagrab._extract_json_datablob(soup)

        return Instagrab._parse(blob['entry_data']['ProfilePage'][0]['user']['media'], account)

    @staticmethod
    def _parse(media, account):
        page_info = media['page_info']
        nodes = media['nodes']

        # Pull out the batch meta.
        meta = BatchMeta(start_cursor=int(page_info['start_cursor']),
                         end_cursor=int(page_info['end_cursor']),
                         has_previous_page=page_info['has_previous_page'],
                         has_next_page=page_info['has_next_page'])

        # Pull out all the relevent information for all of the images. Exclude videos.
        photos = [Photo(ig_id=x['id'],
                        likes=x['likes']['count'],
                        posted=x['date'],
                        url=x['display_src'],
                        code=x['code'],
                        caption=x.get('caption', None),
                        owner_id=int(x['owner']['id']),
                        account_name=account)
                  for x in nodes
                  if x['is_video'] is False]

        return (meta, photos)

    @staticmethod
    def _extract_json_datablob(soup):
        """The first useful json blob is being fished out of the Profile Page's HTML;
        this method does that."""
        prefix = 'window._sharedData ='
        candidates = [x.text for x in soup.find_all('script')
                      if x.text.startswith(prefix)]
        if len(candidates) != 1:
            raise RuntimeError
        else:
            return json.loads(candidates[0][len(prefix): -1])

    def _get_next_page(self, account, owner_id, last_id, batch_size=12):
        """Fetches another batch of json from the Instagram query API."""
        instagram_query_string = \
                """ig_user(%d) {
                       media.after(%d, %d) {
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
               }"""

        headers = {'x-csrftoken': self._session.cookies['csrftoken'],
                   'referer': 'https://www.instagram.com/'}

        data = {'q': instagram_query_string % (owner_id, last_id, batch_size),
                'ref': 'users::show',
                'query_id': '17846611669135658'}

        response = self._session.post(self.instagram + '/query/', data=data, headers=headers)

        return Instagrab._parse(response.json()['media'], account)

    def fetch_photos(self, account):
        """Generator returning batches of photos. Will keep going until the source is exhausted."""
        (batch_meta, photos) = self._get_first_page(account)
        yield photos

        owner_id = photos[0].owner_id
        while batch_meta.has_next_page:
            (batch_meta, photos) = self._get_next_page(account, owner_id, batch_meta.end_cursor)
            yield photos


class Downloader(object):
    """Uses Instagrab to download photographs in parallel."""

    @staticmethod
    def save_image(photo, directory, mongo_client=None):
        """Saves an image from a requests response."""
        response = requests.get(photo.url)
        image = Image.open(StringIO(response.content))
        image_path = '%s/%s.jpg' % (directory, photo.ig_id)
        image.save(image_path)
        if mongo_client is not None:
            # We want to stuff the file location into the mongodb entry along with all the
            #  other gubbins
            mongo_dict = photo._asdict()
            mongo_dict['file_path'] = image_path
            mongo_client.instagram.posts.insert_one(mongo_dict)
        sys.stdout.write('.')
        sys.stdout.flush()

    @staticmethod
    def download_photographs(photos, directory='content', max_batches=None, mongo_client=None):
        """Download photographs from the Photos generator."""
        batch_count = 0
        while max_batches is None or max_batches < batch_count:
            batch_count += 1
            # We're consuming each batch in parallel which is not optimal but is better
            #  than nothing.
            threads = [threading.Thread(target=Downloader.save_image, args=(photo, directory, mongo_client,))
                       for photo in photos.next()]
            for thread in threads:
                thread.start()

#Downloader.download_photographs(Instagrab().fetch_photos('asasjostromphotography'))
mongo_client = MongoClient('localhost', 27017)
Downloader.download_photographs(Instagrab().fetch_photos('daveyoder'), mongo_client=mongo_client)
