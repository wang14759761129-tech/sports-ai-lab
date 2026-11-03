import threading
import unittest
from urllib.request import urlopen
from urllib.error import HTTPError
from http.server import HTTPServer
from serve import Handler, ROOT

class SpikeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_local_page_and_headers(self):
        with urlopen(self.base) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            self.assertEqual(response.headers['Referrer-Policy'], 'strict-origin-when-cross-origin')
            self.assertIn('frame-src https://www.youtube.com;', response.headers['Content-Security-Policy'])
            self.assertIn('单视频', response.read().decode('utf-8'))

    def test_no_repository_or_private_files_served(self):
        for path in ['/../official_video_sources.json', '/serve.py', '/.env', '/matches.db', '/media/test.jpg']:
            with self.assertRaises(HTTPError) as error:
                urlopen(self.base + path)
            self.assertEqual(error.exception.code, 404)

    def test_script_served_unchanged(self):
        with urlopen(self.base + '/spike.js') as response:
            self.assertEqual(response.read(), (ROOT / 'spike.js').read_bytes())

    def test_exact_video_no_image_or_autoplay(self):
        script = (ROOT / 'spike.js').read_text(encoding='utf-8')
        page = (ROOT / 'index.html').read_text(encoding='utf-8')
        self.assertIn('https://www.youtube.com/embed/0QgbtsBWZhk?autoplay=0&controls=1', script)
        self.assertIn("frame.width='640';frame.height='360'", script)
        self.assertNotIn('i.ytimg.com', script + page)
        self.assertNotIn('<img', page)

    def test_manual_evidence_never_native_pass(self):
        script = (ROOT / 'spike.js').read_text(encoding='utf-8')
        self.assertIn('MANUAL_OBSERVATION_NOT_INDEPENDENTLY_VERIFIED', script)
        self.assertIn("native_playback:'NOT_TESTED'", script)
        self.assertIn('media_permission_changes:[]', script)
        self.assertIn("['NOT_TESTED','OBSERVED','NOT_OBSERVED','BLOCKED']", script)

    def test_fallback_present_without_player(self):
        page = (ROOT / 'index.html').read_text(encoding='utf-8')
        script = (ROOT / 'spike.js').read_text(encoding='utf-8')
        self.assertIn('href="https://www.youtube.com/watch?v=0QgbtsBWZhk"', page)
        self.assertIn('readonly value="https://www.youtube.com/watch?v=0QgbtsBWZhk"', page)
        self.assertIn('document.querySelector(\'#url\').select()', script)

if __name__ == '__main__':
    unittest.main()
