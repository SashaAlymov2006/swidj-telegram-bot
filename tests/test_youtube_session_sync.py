import http.cookiejar
import unittest
from youtube_session_sync import filter_youtube, authenticated_youtube


def cookie(domain,name,expires):
    return http.cookiejar.Cookie(0,name,'fixture',None,False,domain,True,domain.startswith('.'),
                                 '/',True,True,expires,expires is None,None,None,{},False)


class BrowserSessionFilterTests(unittest.TestCase):
    def test_google_identity_cookies_without_youtube_login_are_rejected(self):
        jar=http.cookiejar.CookieJar()
        for name in ('SID','SAPISID','__Secure-1PSID','__Secure-3PSID'):
            jar.set_cookie(cookie('.youtube.com',name,2000))
        self.assertFalse(authenticated_youtube(jar,now=1000))
        jar.set_cookie(cookie('.youtube.com','LOGIN_INFO',2000))
        self.assertTrue(authenticated_youtube(jar,now=1000))

    def test_expired_login_and_google_only_login_are_rejected(self):
        jar=http.cookiejar.CookieJar()
        jar.set_cookie(cookie('.youtube.com','SAPISID',2000))
        jar.set_cookie(cookie('.youtube.com','LOGIN_INFO',500))
        jar.set_cookie(cookie('.google.com','LOGIN_INFO',2000))
        self.assertFalse(authenticated_youtube(jar,now=1000))

    def test_login_without_signature_cookie_is_rejected(self):
        jar=http.cookiejar.CookieJar();jar.set_cookie(cookie('.youtube.com','LOGIN_INFO',2000))
        self.assertFalse(authenticated_youtube(jar,now=1000))

    def test_export_excludes_other_sites_and_expired_cookies(self):
        jar=http.cookiejar.CookieJar()
        for row in (cookie('.youtube.com','SID',2000),cookie('.google.com','SID',2000),
                    cookie('.notyoutube.com','SID',2000),cookie('.youtube.com','old',500)):
            jar.set_cookie(row)
        self.assertEqual(filter_youtube(jar,now=1000),(1,1))
        self.assertEqual([item.domain for item in jar],['.youtube.com'])

    def test_browser_session_cookie_without_expiry_is_preserved(self):
        jar=http.cookiejar.CookieJar();jar.set_cookie(cookie('.youtube.com','LOGIN_INFO',None))
        self.assertEqual(filter_youtube(jar,now=1000),(1,1))

    def test_guest_cookies_do_not_count_as_an_authenticated_export(self):
        jar=http.cookiejar.CookieJar();jar.set_cookie(cookie('.youtube.com','visitor',2000))
        self.assertEqual(filter_youtube(jar,now=1000),(1,0))
