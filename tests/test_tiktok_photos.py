import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from tiktok_photos import parse_post,checked_url,photo_url,download


def fixture():
    return {'id':'123','desc':'Fixture photos','author':{'nickname':'Fixture'},'music':{'playUrl':'https://sf16-music.tiktokcdn-eu.com/audio.mp3'},
            'imagePost':{'images':[{'imageWidth':120,'imageHeight':160,'imageURL':{'urlList':['https://p16.tiktokcdn-eu.com/first.webp']}},
                                   {'imageWidth':120,'imageHeight':160,'imageURL':{'urlList':['https://p16.tiktokcdn-eu.com/second.webp']}}]}}


def html(item):
    return '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">'+json.dumps({'__DEFAULT_SCOPE__':{'webapp.video-detail':{'statusCode':0,'itemInfo':{'itemStruct':item}}}})+'</script>'


class PhotoPostTests(unittest.TestCase):
    def test_app_routes_unsupported_photo_to_its_handler(self):
        import yt_dlp
        from app_media import fetch
        with tempfile.TemporaryDirectory() as directory,patch('yt_dlp.YoutubeDL') as downloader,patch('tiktok_photos.download',return_value={'path':'fixture.mp4','title':'Photos'}) as photos:
            downloader.return_value.__enter__.return_value.extract_info.side_effect=yt_dlp.utils.DownloadError('No suitable extractor found for URL https://www.tiktok.com/@a/photo/123')
            result=fetch({'url':'https://vm.tiktok.com/ABC12/','mode':'video','height':720},directory)
            self.assertEqual(result['title'],'Photos');photos.assert_called_once()
    def test_photo_identity_and_public_cdn_are_validated(self):
        self.assertEqual(len(parse_post(html(fixture()),'123')['images']),2)
        with self.assertRaises(ValueError):parse_post(html(fixture()),'999')
        bad=fixture();bad['imagePost']['images'][0]['imageURL']['urlList']=['https://127.0.0.1/private']
        with self.assertRaises(ValueError):parse_post(html(bad),'123')
        for url in ('https://tiktok.com.evil.test/@a/photo/123','https://user:pass@www.tiktok.com/@a/photo/123','http://www.tiktok.com/@a/photo/123'):
            with self.assertRaises(ValueError):checked_url(url)
    def test_photo_long_link_needs_no_redirect_request(self):
        with patch('tiktok_photos.requests.get') as network:
            value=photo_url('https://www.tiktok.com/@a/photo/123?tracking=1')
            self.assertEqual(value[0],'https://www.tiktok.com/@a/photo/123')
            network.assert_not_called()
    def test_real_slideshow_retains_images_audio_and_portrait_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);image=root/'fixture.jpg';second=root/'second.jpg';audio=root/'fixture.mp3'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=120x160','-frames:v','1',str(image)],check=True)
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=green:s=120x160','-frames:v','1',str(second)],check=True)
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=1',str(audio)],check=True)
            def resource(url,target,limit,media=True):
                target=Path(target)
                if not media:target.write_text(html(fixture()))
                else:shutil.copyfile(audio if 'audio.mp3' in url else second if 'second.webp' in url else image,target)
                # Simulate larger image inputs than the permitted final MP4 size.
                return 600*1024 if media and 'audio.mp3' not in url else target.stat().st_size
            with patch('tiktok_photos.download_resource',side_effect=resource):
                result=download('https://www.tiktok.com/@a/photo/123',root/'work','video',720,max_bytes=1024*1024)
            data=json.loads(subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',result['path']],capture_output=True,text=True,check=True).stdout)
            video=next(row for row in data['streams'] if row['codec_type']=='video')
            self.assertGreater(video['height'],video['width'])
            self.assertTrue(any(row['codec_type']=='audio' for row in data['streams']))
            sound=next(row for row in data['streams'] if row['codec_type']=='audio')
            self.assertGreater(float(sound['duration']),5.8)
            self.assertAlmostEqual(float(data['format']['duration']),6,delta=.2)
            for at,dominant in (('0.5',2),('4.5',1)):
                decoded=subprocess.run(['ffmpeg','-v','error','-ss',at,'-i',result['path'],'-frames:v','1','-vf','scale=2:2','-f','rawvideo','-pix_fmt','rgb24','-threads','1','pipe:1'],capture_output=True)
                self.assertEqual(decoded.returncode,0,decoded.stderr.decode(errors='replace'))
                pixel=decoded.stdout
                self.assertEqual(len(pixel),12);self.assertEqual(max(range(3),key=lambda n:sum(pixel[n::3])),dominant)
