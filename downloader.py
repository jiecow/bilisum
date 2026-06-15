import os
import re
import json
import logging
import subprocess
import requests

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}

BILIBILI_URL_PATTERN = re.compile(
    r"(https?://)?((www\.|m\.)?bilibili\.com/(video/)?(BV[\w]+)|b23\.tv/[\w]+)"
)


def is_bilibili_url(url: str) -> bool:
    return bool(BILIBILI_URL_PATTERN.match(url))


def _extract_p(url: str) -> int | None:
    """Extract p (part/page number) from Bilibili URL query parameters."""
    m = re.search(r"[?&]p=(\d+)", url)
    if m:
        return int(m.group(1))
    return None


def _extract_bvid(url: str) -> str:
    """Extract BV id from a Bilibili URL."""
    m = re.search(r"BV[\w]+", url)
    if m:
        return m.group(0)
    # Handle b23.tv short links
    if "b23.tv" in url:
        m = re.search(r"b23\.tv/([\w]+)", url)
        if m:
            resp = requests.get(
                f"https://{m.group(0)}", headers=HEADERS, timeout=15, allow_redirects=True
            )
            m2 = re.search(r"BV[\w]+", resp.url)
            if m2:
                return m2.group(0)
    raise RuntimeError(f"无法从链接中提取 BV号: {url}")


def _get_video_info(bvid: str, p: int | None = None) -> dict:
    """Fetch video metadata from Bilibili API (title, cid, etc).

    If p is specified, fetch info for that specific part/page.
    """
    api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    if p is not None:
        api_url += f"&p={p}"
    resp = requests.get(api_url, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"B站API请求失败: HTTP {resp.status_code}")
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"B站API错误: {data.get('message', 'unknown')}")
    v = data["data"]
    cid = v.get("cid", 0)
    pages = v.get("pages", [])
    if pages:
        if p is not None and 1 <= p <= len(pages):
            cid = pages[p - 1]["cid"]
        elif not cid:
            cid = pages[0]["cid"]
    title = v.get("title", "Unknown")
    # When p is specified, get the part sub-title if available
    if p is not None and pages and 1 <= p <= len(pages):
        part_title = pages[p - 1].get("part", "")
        if part_title and part_title != title:
            title = f"{title} (P{p} - {part_title})"
    return {
        "title": title,
        "bvid": bvid,
        "cid": cid,
        "duration": v.get("duration", 0),
        "pic": v.get("pic", ""),
        "p": p,
    }


def _get_audio_url(bvid: str, cid: int) -> str:
    """
    Get audio stream URL from Bilibili player API.
    Returns the URL of the audio-only (or lowest quality) stream.
    """
    # 16 = lowest quality, we only need audio
    api_url = (
        f"https://api.bilibili.com/x/player/playurl?"
        f"bvid={bvid}&cid={cid}&qn=16&fnver=0&fnval=4048&fourk=1"
    )
    resp = requests.get(api_url, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"播放链接API请求失败: HTTP {resp.status_code}")
    data = resp.json()
    if data.get("code") != 0:
        # Try dash format
        api_url2 = (
            f"https://api.bilibili.com/x/player/wbi/v2?"
            f"bvid={bvid}&cid={cid}&qn=16&fnver=0&fnval=4048"
        )
        resp2 = requests.get(api_url2, headers=HEADERS, timeout=15)
        if resp2.status_code == 200:
            data2 = resp2.json()
            if data2.get("code") == 0:
                dash = data2["data"].get("dash", {})
                audio_list = dash.get("audio", [])
                if audio_list:
                    for a in audio_list:
                        base_url = a.get("baseUrl") or a.get("base_url", "")
                        if base_url:
                            return base_url
                    # Try backup URLs
                    for a in audio_list:
                        backup = a.get("backupUrl") or a.get("backup_url", [])
                        if backup:
                            return backup[0]
        raise RuntimeError(f"无法获取音频流: {data.get('message', 'unknown')}")

    dash = data["data"].get("dash", {})
    audio_list = dash.get("audio", [])
    if audio_list:
        # Prefer audio stream with best bandwidth
        audio_list.sort(key=lambda x: x.get("bandwidth", 0), reverse=True)
        base_url = audio_list[0].get("baseUrl") or audio_list[0].get("base_url", "")
        if base_url:
            return base_url
        # Try backup
        for a in audio_list:
            backup = a.get("backupUrl") or a.get("backup_url", [])
            if backup:
                return backup[0]

    # Fallback to the first video stream (lowest quality)
    video_list = data["data"].get("dash", {}).get("video", [])
    if video_list:
        base_url = video_list[-1].get("baseUrl") or video_list[-1].get("base_url", "")
        if base_url:
            return base_url

    raise RuntimeError("无法从响应中找到音频流")


def download_audio(url: str, output_dir: str) -> str:
    """
    Download audio from a Bilibili video using direct API.
    Returns path to the downloaded MP3 file.
    """
    os.makedirs(output_dir, exist_ok=True)

    bvid = _extract_bvid(url)
    p = _extract_p(url)
    logger.info("Extracted BV id: %s, p=%s", bvid, p)

    info = _get_video_info(bvid, p=p)
    logger.info("Video: %s (cid=%s)", info["title"], info["cid"])

    audio_url = _get_audio_url(bvid, info["cid"])
    logger.info("Audio URL obtained (length: %d chars)", len(audio_url))

    # Use BV号 for unique filename (titles can collide)
    safe_title = re.sub(r'[\\/*?:"<>|]', "", info["title"]).strip()[:40]
    m4a_path = os.path.join(output_dir, f"{bvid}_{safe_title}.m4a")

    # Download via FFmpeg (Bilibili audio stream is AAC in m4s container)
    logger.info("Downloading audio to: %s", m4a_path)
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-headers", f"User-Agent: {HEADERS['User-Agent']}\r\nReferer: {HEADERS['Referer']}\r\n",
        "-i", audio_url,
        "-c", "copy",
        m4a_path,
    ]
    result = subprocess.run(
        ffmpeg_cmd, capture_output=True, text=True, timeout=600
    )
    if result.returncode != 0 or not os.path.exists(m4a_path) or os.path.getsize(m4a_path) == 0:
        # Fallback: try re-encoding to m4a
        logger.warning("Stream copy failed, trying re-encode: %s", result.stderr[-300:])
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-headers", f"User-Agent: {HEADERS['User-Agent']}\r\nReferer: {HEADERS['Referer']}\r\n",
            "-i", audio_url,
            "-c:a", "aac",
            "-b:a", "128k",
            m4a_path,
        ]
        result = subprocess.run(
            ffmpeg_cmd, capture_output=True, text=True, timeout=600
        )
        if result.returncode != 0 or not os.path.exists(m4a_path) or os.path.getsize(m4a_path) == 0:
            raise RuntimeError(f"FFmpeg 下载失败: {result.stderr.strip()[-300:]}")

    logger.info("Audio downloaded: %s (%d bytes)", m4a_path, os.path.getsize(m4a_path))
    return m4a_path


def extract_title(url: str) -> str:
    """Extract video title via Bilibili API."""
    try:
        bvid = _extract_bvid(url)
        p = _extract_p(url)
        info = _get_video_info(bvid, p=p)
        return info["title"]
    except Exception as e:
        logger.warning("Failed to extract title: %s", e)
        return "Unknown Title"


def convert_to_wav(audio_path: str, output_dir: str) -> str:
    """
    Convert audio file to 16kHz mono WAV for whisper input.
    Returns path to the WAV file.
    """
    base = os.path.splitext(os.path.basename(audio_path))[0]
    wav_path = os.path.join(output_dir, f"{base}.wav")
    cmd = [
        "ffmpeg", "-y",
        "-i", audio_path,
        "-ar", "16000",
        "-ac", "1",
        "-sample_fmt", "s16",
        wav_path,
    ]
    logger.info("Converting to WAV: %s -> %s", audio_path, wav_path)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg转换失败: {result.stderr.strip()[:300]}")
    logger.info("WAV ready: %s (%d bytes)", wav_path, os.path.getsize(wav_path))
    return wav_path
