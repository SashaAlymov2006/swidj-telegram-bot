"""Public track metadata only: no accounts, tokens, paid APIs or protected audio."""
import json
import re
from urllib.parse import urlparse, parse_qs
import requests
from bs4 import BeautifulSoup

def classify(url):
    try:
        parsed=urlparse(url)
        host=(parsed.hostname or "").lower()
        if parsed.scheme not in ("http","https") or parsed.username or parsed.password or parsed.port not in (None,80,443):
            return None
        path=parsed.path
        if host in ("youtu.be","youtube.com","www.youtube.com","m.youtube.com","music.youtube.com"):
            return "youtube" if host=="youtu.be" and path.strip("/") or re.match(r"/(watch|shorts/|live/)",path) else None
        if host in ("tiktok.com","www.tiktok.com","m.tiktok.com") and re.fullmatch(r"/(?:@[^/]+/video/\d+|t/[A-Za-z0-9]+|embed/v2/\d+)/?",path):
            return "tiktok"
        if host in ("vm.tiktok.com","vt.tiktok.com") and re.fullmatch(r"/[A-Za-z0-9]+/?",path):
            return "tiktok"
        if host in ("instagram.com","www.instagram.com") and re.fullmatch(r"/(?:[A-Za-z0-9_.]+/)?(?:reel|reels|p|tv)/[A-Za-z0-9_-]+/?",path):
            return "instagram"
        if host in ("soundcloud.com","www.soundcloud.com","m.soundcloud.com","on.soundcloud.com"):
            return "soundcloud"
        if host=="open.spotify.com" and re.match(r"/(?:intl-[a-z]+/)?track/",path):
            return "spotify"
        if host in ("music.yandex.ru","music.yandex.com","music.yandex.kz","music.yandex.by") and re.fullmatch(r"/(?:album/\d+/)?track/\d+/?",path):
            return "yandex"
        if host=="music.apple.com" and (re.match(r"/[a-z]{2}/song/",path) or re.match(r"/[a-z]{2}/album/",path) and parse_qs(parsed.query).get("i")):
            return "apple"
        if host in ("vk.com","www.vk.com","m.vk.com","vk.ru","www.vk.ru","m.vk.ru") and (re.match(r"/audio-?\d+_\d+",path) or path=="/music" and re.search(r"audio-?\d+_\d+",parse_qs(parsed.query).get("z",[""])[0])):
            return "vk"
        if host=="music.vk.com" and path.startswith("/track/"):
            return "vk"
    except ValueError:
        pass
    return None

def extract_links(text):
    result=[]; seen=set()
    for match in re.finditer(r"https?://[^\s<>]+",text or ""):
        url=match[0].rstrip(".,;!?)\"'»")
        platform=classify(url)
        if platform and url not in seen:
            result.append({"url":url,"platform":platform});seen.add(url)
    return result

def apple_metadata(url):
    if classify(url)!="apple":
        raise ValueError("Нужна ссылка на отдельную песню Apple Music.")
    parsed=urlparse(url); params=parse_qs(parsed.query)
    identifier=params.get("i",[None])[0]
    if not identifier:
        identifier=parsed.path.rstrip("/").rsplit("/",1)[-1]
    if not str(identifier).isdigit():
        raise ValueError("Нужна ссылка на отдельную песню Apple Music.")
    country=parsed.path.split("/")[1]
    for storefront in dict.fromkeys((country,"us","gb")):
        try:
            response=requests.get("https://itunes.apple.com/lookup",params={"id":identifier,"country":storefront,"entity":"song"},timeout=8)
            response.raise_for_status()
            for track in response.json().get("results",[]):
                if track.get("kind")=="song" and str(track.get("trackId"))==identifier and track.get("trackName") and track.get("artistName"):
                    return {"title":track["trackName"],"artist":track["artistName"],"cover":track.get("artworkUrl100"),"query":track["trackName"]+" "+track["artistName"]}
        except (requests.RequestException,ValueError,TypeError):
            continue
    raise ValueError("Не удалось прочитать песню Apple Music. Напиши название и исполнителя.")

def public_metadata(url,platform):
    if classify(url)!=platform or platform not in ("yandex","vk"):
        raise ValueError("Нужна ссылка на отдельный трек.")
    response=requests.get(url,timeout=12,allow_redirects=False)
    response.raise_for_status()
    if response.status_code!=200 or len(response.text.encode("utf-8"))>2*1024*1024:
        raise ValueError("Страница трека недоступна.")
    soup=BeautifulSoup(response.text,"html.parser")
    for script in soup.find_all("script",type="application/ld+json"):
        try:
            value=json.loads(script.string or script.get_text())
        except (ValueError,TypeError):
            continue
        pending=list(value) if isinstance(value,list) else [value]
        while pending:
            track=pending.pop(0)
            if not isinstance(track,dict):
                continue
            pending.extend(track.get("@graph",[]) if isinstance(track.get("@graph"),list) else [])
            types = track.get("@type", [])
            if "MusicRecording" not in (types if isinstance(types,list) else [types]):
                continue
            artists=track.get("byArtist",[])
            if isinstance(artists,dict): artists=[artists]
            if isinstance(artists,str): artists=[{"name":artists}]
            artist=", ".join(str(a["name"]) if isinstance(a,dict) else a for a in artists if isinstance(a,str) and a or isinstance(a,dict) and a.get("name"))
            title=track.get("name")
            if title and artist:
                cover=track.get("image")
                return {"title":str(title)[:180],"artist":artist[:120],"query":str(title)+" "+artist,"cover":cover if isinstance(cover,str) else None}
    raise ValueError("Не удалось прочитать название и исполнителя.")

def yandex_api_metadata(url):
    if classify(url)!="yandex":
        raise ValueError("Invalid Yandex track link")
    identifier=urlparse(url).path.rstrip("/").rsplit("/",1)[-1]
    response=requests.get("https://api.music.yandex.net/tracks/"+identifier,timeout=12,allow_redirects=False)
    response.raise_for_status()
    payload=response.json()
    for track in payload.get("result",[]) if isinstance(payload,dict) else []:
        if not isinstance(track,dict) or str(track.get("id"))!=identifier:
            continue
        title=track.get("title")
        artist=", ".join(str(item["name"]) for item in track.get("artists",[]) if isinstance(item,dict) and item.get("name"))
        if title and artist:
            version=track.get("version")
            title=str(title)+(f" ({version})" if version else "")
            return {"title":title[:180],"artist":artist[:120],"query":title+" "+artist}
    raise ValueError("Yandex track metadata unavailable")


def songlink_yandex_metadata(url):
    """Read public smart-link metadata; exact catalog ID must match."""
    if classify(url)!="yandex":
        raise ValueError("Invalid Yandex track link")
    identifier=urlparse(url).path.rstrip("/").rsplit("/",1)[-1]
    target="https://song.link/ya/"+identifier
    for _ in range(3):
        response=requests.get(target,timeout=12,allow_redirects=False)
        if response.status_code in (301,302,303,307,308):
            from urllib.parse import urljoin
            target=urljoin(target,response.headers.get("Location",""))
            parsed=urlparse(target)
            if parsed.scheme!="https" or parsed.hostname not in ("song.link","odesli.co") or parsed.username or parsed.password or parsed.port not in (None,443):
                raise ValueError("Unexpected smart-link redirect")
            continue
        response.raise_for_status()
        if response.status_code!=200 or len(response.text.encode("utf-8"))>2*1024*1024:
            raise ValueError("Smart-link page unavailable")
        soup=BeautifulSoup(response.text,"html.parser")
        script=soup.find("script",id="__NEXT_DATA__",type="application/json")
        if not script:
            raise ValueError("Smart-link metadata unavailable")
        payload=json.loads(script.string or script.get_text())
        data=payload.get("props",{}).get("pageProps",{}).get("pageData",{})
        if data.get("entityUniqueId")!="yandex|song|"+identifier:
            raise ValueError("Smart-link track does not match")
        for section in data.get("sections",[]):
            if not isinstance(section,dict):
                continue
            title,artist=section.get("title"),section.get("artistName")
            if isinstance(title,str) and title.strip() and isinstance(artist,str) and artist.strip():
                return {"title":title.strip()[:180],"artist":artist.strip()[:120],"query":title.strip()+" "+artist.strip()}
        raise ValueError("Smart-link title unavailable")
    raise ValueError("Too many smart-link redirects")


def catalog_metadata(platform,url):
    if platform=="apple":
        return apple_metadata(url)
    if platform=="yandex":
        # Independent public metadata sources. No account, preview audio or bypass.
        try:
            return public_metadata(url,platform)
        except (requests.RequestException,ValueError,TypeError,KeyError):
            try:
                return yandex_api_metadata(url)
            except (requests.RequestException,ValueError,TypeError,KeyError):
                return songlink_yandex_metadata(url)
    return public_metadata(url,platform)
