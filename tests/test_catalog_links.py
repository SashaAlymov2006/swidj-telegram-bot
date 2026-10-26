import unittest
from unittest.mock import Mock, patch
from catalog_links import classify, extract_links, apple_metadata, public_metadata
class CatalogLinksTests(unittest.TestCase):
    def test_copied_tiktok_share_formats_work_in_chat_and_miniapp(self):
        from app_media import validate
        url='https://vm.tiktok.com/ABC12/'
        samples=[url,'vm.tiktok.com/ABC12/','HTTPS://VM.TIKTOK.COM/ABC12/',
                 'Shared video '+url+'\u200b','Watch: '+url+'»',url+url]
        for text in samples:
            with self.subTest(text=text):
                links=extract_links(text)
                self.assertTrue(links);self.assertEqual(links[0]['platform'],'tiktok')
                self.assertEqual(validate({'url':text,'mode':'video','height':720})[3],'tiktok')
        self.assertEqual(len(extract_links(url+url)),1)
        for text in ('vm.tiktok.com.evil.test/ABC12/','https://user:password@vm.tiktok.com/ABC12/','https://127.0.0.1/ABC12/'):
            self.assertEqual(extract_links(text),[])
            with self.assertRaises(ValueError):validate({'url':text})
    def test_selected_platform_urls_only_and_deduplication(self):
        cases={"https://music.yandex.ru/album/1/track/2?utm_source=x":"yandex",
               "https://music.yandex.kz/track/12":"yandex",
               "https://music.apple.com/gb/album/name/123?i=456":"apple",
               "https://music.apple.com/us/song/name/456":"apple",
               "https://vk.com/audio-123_456":"vk",
               "https://vk.ru/music?z=audio-123_456":"vk"}
        for url,kind in cases.items(): self.assertEqual(classify(url),kind)
        for url in ("https://music.apple.com.evil.test/us/song/123","https://vk.com.evil.test/audio1_2","https://127.0.0.1/audio1_2",
                    "https://music.apple.com/us/album/name/123","https://bandcamp.com/song",
                    "https://user:pass@vk.com/audio1_2"):
            self.assertIsNone(classify(url))
        self.assertEqual(len(extract_links("https://vk.com/audio1_2 https://vk.com/audio1_2")),1)
    def test_apple_lookup_requires_actual_matching_song_not_album_or_preview(self):
        response=Mock();response.json.return_value={"results":[{"trackId":456,"kind":"song","trackName":"Song","artistName":"Artist","previewUrl":"https://preview.example/sample"}]}
        with patch("catalog_links.requests.get",return_value=response) as get:
            data=apple_metadata("https://music.apple.com/gb/album/name/123?i=456")
        self.assertEqual(data["title"],"Song");self.assertNotIn("previewUrl",data)
        self.assertEqual(get.call_args.kwargs["params"]["id"],"456")
        self.assertEqual(get.call_args.kwargs["params"]["country"],"gb")
        response.json.return_value={"results":[{"trackId":123,"kind":"song","trackName":"Wrong","artistName":"Artist"}]}
        with patch("catalog_links.requests.get",return_value=response),self.assertRaises(ValueError):
            apple_metadata("https://music.apple.com/us/song/name/456")
    def test_public_music_recording_only_and_closed_page_fallback(self):
        response=Mock(status_code=200)
        response.text='<script type="application/ld+json">{"@type":"MusicRecording","name":"Song","byArtist":{"name":"Artist"}}</script>'
        with patch("catalog_links.requests.get",return_value=response) as get:
            self.assertEqual(public_metadata("https://vk.com/audio1_2","vk")["artist"],"Artist")
            self.assertFalse(get.call_args.kwargs["allow_redirects"])
        response.text="<title>Sign in</title>"
        with patch("catalog_links.requests.get",return_value=response),self.assertRaises(ValueError):
            public_metadata("https://vk.com/audio1_2","vk")

    def test_completed_private_download_job_cleanup_keeps_other_files(self):
        from pathlib import Path
        import tempfile
        import scratch
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            job=root/"yt_video_fixture";job.mkdir()
            video=job/"video.mp4";video.write_bytes(b"video")
            (job/"fragment.part").write_bytes(b"leftover")
            unrelated=root/"my-file";unrelated.write_bytes(b"keep")
            with patch.object(scratch,"TEMP_ROOT",root):
                scratch.remove_owned_file(video)
            self.assertFalse(job.exists())
            self.assertEqual(unrelated.read_bytes(),b"keep")

    def test_working_cache_budget_keeps_active_users_and_saved_library(self):
        import tempfile, os, time
        from pathlib import Path
        from media_store import MediaStore
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            cache=MediaStore(root/"audio")
            old=cache.user_directory(1)/"old.mp3";old.write_bytes(b"x"*12)
            active=cache.user_directory(2)/"active.mp3";active.write_bytes(b"y"*12)
            library=root/"library";library.mkdir()
            saved=library/"saved.mp3";saved.write_bytes(b"keep")
            os.utime(old,(time.time()-100,time.time()-100))
            removed=cache.trim_cache(protected_users={2},max_bytes=16,max_age=1000)
            self.assertEqual(removed,1)
            self.assertFalse(old.exists())
            self.assertTrue(active.exists())
            self.assertEqual(saved.read_bytes(),b"keep")

    def test_cache_age_limit_and_protected_oversize_work_are_safe(self):
        import tempfile, os, time
        from pathlib import Path
        from media_store import MediaStore
        with tempfile.TemporaryDirectory() as directory:
            cache=MediaStore(Path(directory)/"audio")
            expired=cache.user_directory(1)/"expired.mp3";expired.write_bytes(b"old")
            active=cache.user_directory(2)/"active.mp3";active.write_bytes(b"x"*20)
            os.utime(expired,(time.time()-100,time.time()-100))
            self.assertEqual(cache.trim_cache(protected_users={2},max_bytes=8,max_age=20),1)
            self.assertFalse(expired.exists())
            self.assertTrue(active.exists())

    def test_tiktok_video_and_share_links_only(self):
        for url in ("https://www.tiktok.com/@artist/video/12345","https://vm.tiktok.com/ABC12/","https://vt.tiktok.com/ABC12/","https://www.tiktok.com/t/ABC12/","https://tiktok.com/@a/photo/123"):
            self.assertEqual(classify(url),"tiktok")
        for url in ("https://www.tiktok.com/@artist","https://tiktok.com.evil.test/@a/video/123","https://vm.tiktok.com/","https://user:pass@tiktok.com/@a/video/123"):
            self.assertIsNone(classify(url))

    def test_yandex_jsonld_graph_types_and_artist_list(self):
        response=Mock(status_code=200)
        response.text='<script type="application/ld+json">{"@graph":[{"@type":["Thing","MusicRecording"],"name":"Song","byArtist":["Artist",{"name":"Guest"}]}]}</script>'
        with patch("catalog_links.requests.get",return_value=response):
            data=public_metadata("https://music.yandex.ru/album/1/track/2","yandex")
        self.assertEqual(data["artist"],"Artist, Guest")
        self.assertEqual(data["query"],"Song Artist, Guest")

    def test_yandex_uses_independent_public_api_when_page_fails(self):
        from catalog_links import catalog_metadata
        response=Mock();response.json.return_value={"result":[{"id":2,"title":"Song","artists":[{"name":"Artist"}]}]}
        with patch("catalog_links.public_metadata",side_effect=ValueError("page unavailable")), patch("catalog_links.requests.get",return_value=response) as get:
            result=catalog_metadata("yandex","https://music.yandex.ru/album/1/track/2")
        self.assertEqual(result["query"],"Song Artist")
        self.assertEqual(get.call_args.args[0],"https://api.music.yandex.net/tracks/2")
        response.json.return_value={"result":[{"id":3,"title":"Wrong song","artists":[{"name":"Artist"}]}]}
        with patch("catalog_links.requests.get",return_value=response),self.assertRaises(ValueError):
            from catalog_links import yandex_api_metadata
            yandex_api_metadata("https://music.yandex.ru/track/2")

    def test_apple_tries_another_storefront_for_same_track_id(self):
        from catalog_links import apple_metadata
        empty=Mock();empty.json.return_value={"results":[]}
        found=Mock();found.json.return_value={"results":[{"kind":"song","trackId":456,"trackName":"Song","artistName":"Artist"}]}
        with patch("catalog_links.requests.get",side_effect=[empty,found]) as get:
            self.assertEqual(apple_metadata("https://music.apple.com/de/song/456")["title"],"Song")
        self.assertEqual([call.kwargs["params"]["country"] for call in get.call_args_list],["de","us"])

    def test_instagram_video_links_and_host_validation(self):
        for url in ("https://www.instagram.com/reel/Chunk8-jurw/","https://instagram.com/p/ABC_12-/?igsh=x","https://www.instagram.com/artist/reel/ABC12/","https://instagram.com/tv/ABC12/"):
            self.assertEqual(classify(url),"instagram")
        for url in ("https://instagram.com/artist/","https://instagram.com/stories/a/123","https://instagram.com.evil.test/reel/ABC/","https://user:pass@instagram.com/reel/ABC/","https://instagram.com/reels/audio/123"):
            self.assertIsNone(classify(url))

    def test_exact_user_yandex_link_resolves_from_public_smart_link(self):
        import json
        from catalog_links import catalog_metadata
        payload={"props":{"pageProps":{"pageData":{"entityUniqueId":"yandex|song|20220545","sections":[{"title":"Song","artistName":"Artist"}]}}}}
        page=Mock(status_code=200)
        page.text='<script id="__NEXT_DATA__" type="application/json">'+json.dumps(payload)+'</script>'
        url="https://music.yandex.ru/album/2303525/track/20220545?ref_id=fixture&utm_medium=copy_link"
        with patch("catalog_links.public_metadata",side_effect=ValueError("region")), patch("catalog_links.yandex_api_metadata",side_effect=ValueError("451")), patch("catalog_links.requests.get",return_value=page) as get:
            result=catalog_metadata("yandex",url)
        self.assertEqual(result["query"],"Song Artist")
        get.assert_called_once_with("https://song.link/ya/20220545",timeout=12,allow_redirects=False)
        payload["props"]["pageProps"]["pageData"]["entityUniqueId"]="yandex|song|999"
        page.text='<script id="__NEXT_DATA__" type="application/json">'+json.dumps(payload)+'</script>'
        with patch("catalog_links.requests.get",return_value=page),self.assertRaises(ValueError):
            from catalog_links import songlink_yandex_metadata
            songlink_yandex_metadata(url)

    def test_smart_link_rejects_untrusted_redirect(self):
        from catalog_links import songlink_yandex_metadata
        response=Mock(status_code=302,headers={"Location":"https://evil.test/"})
        with patch("catalog_links.requests.get",return_value=response) as get,self.assertRaises(ValueError):
            songlink_yandex_metadata("https://music.yandex.ru/track/20220545")
        self.assertEqual(get.call_count,1)
