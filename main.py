from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import yt_dlp

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

clients = {}


def get_video_audio_links(video_url):
    ydl_opts = {
        "quiet": True,
        "format": "bestaudio/bestvideo",
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        video_info = ydl.extract_info(video_url, download=False)

    video_links = []
    audio_links = []

    for fmt in video_info["formats"]:

        vcodec = fmt.get("vcodec", "none")
        acodec = fmt.get("acodec", "none")
        filesize = fmt.get("filesize", 0)  # File size in bytes
        size_mb = f"{filesize / 1024 / 1024:.2f} MB" if filesize else "Unknown Size"

        if vcodec != "none" and acodec != "none":  # Video with audio
            video_links.append(
                {
                    "resolution": fmt.get("resolution", "Unknown"),
                    "size": size_mb,
                    "url": fmt["url"],
                }
            )
        elif vcodec == "none" and acodec != "none":  # Audio only
            abr = fmt.get("abr", "Unknown")
            if abr != "Unknown":
                # Try to convert abr to float and use it for sorting
                try:
                    abr_value = float(abr)
                    abr_str = f"{abr_value:.0f} kbps"
                except ValueError:
                    abr_value = 0  # Handle non-numeric values as 0
                    abr_str = "Unknown Bitrate"
            else:
                abr_value = 0
                abr_str = "Unknown Bitrate"

            audio_links.append({"abr": abr_str, "size": size_mb, "url": fmt["url"]})

    standard_audio_links = sorted(
        audio_links,
        key=lambda x: float(x["abr"].split()[0]) if "kbps" in x["abr"] else 0,
        reverse=True,
    )[:5]

    return video_links, standard_audio_links, video_info.get("title", "Unknown Title")


@app.get("/", response_class=HTMLResponse)
def read_item(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/submit", response_class=HTMLResponse)
async def submit_youtube_link(request: Request, youtube_link: str = Form(...)):
    try:
        video_links, audio_links, video_title = get_video_audio_links(youtube_link)
        clients[request.client.host] = {
            "request": request,
            "video_links": video_links,
            "audio_links": audio_links,
            "video_title": video_title,
        }
        return templates.TemplateResponse("result.html", clients[request.client.host])
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.middleware("http")
async def remove_client_on_disconnect(request: Request, call_next):
    response = await call_next(request)
    if response.status_code == 200:
        return response
    clients.pop(request.client.host, None)
    return response
