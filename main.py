from fastapi import FastAPI, UploadFile, File, Header, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from groq import Groq
import os
import uvicorn
import tempfile
import uuid
import edge_tts

app = FastAPI()

# CORS ဖွင့်ထားခြင်း (Vercel Frontend မှ လှမ်းခေါ်ခွင့်ပြုရန်)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# TTS အတွက် Frontend မှ ပို့မည့် Data ပုံစံ
class TTSRequest(BaseModel):
    text: str
    voice: str

# အသုံးပြုပြီးသား ဖိုင်ဟောင်းများကို ဖျက်ရန် Function
def remove_temp_file(path: str):
    if os.path.exists(path):
        os.remove(path)

# (၁) ပင်မ Endpoint - Server အလုပ်လုပ်/မလုပ် စစ်ဆေးရန် (404 Error ဖြေရှင်းရန်)
@app.get("/")
def read_root():
    return {"status": "success", "message": "SAI TRANSCRIPT PRO API is running successfully!"}

# (၂) Transcribe Endpoint - Groq ဖြင့် စာသားထုတ်ရန်
@app.post("/api/transcribe")
async def transcribe_audio(file: UploadFile = File(...), x_api_keys: str = Header(None)):
    if not x_api_keys:
        raise HTTPException(status_code=401, detail="API Key လိုအပ်ပါသည်။")

    api_key_list = [k.strip() for k in x_api_keys.split(",") if k.strip()]
    
    # Windows နှင့် Linux (Render) နှစ်ခုလုံးတွင် အဆင်ပြေစေရန် Temp Directory အသုံးပြုခြင်း
    temp_dir = tempfile.gettempdir()
    file_location = os.path.join(temp_dir, file.filename)
    
    with open(file_location, "wb") as f:
        f.write(await file.read())

    for index, current_key in enumerate(api_key_list):
        try:
            client = Groq(api_key=current_key)
            with open(file_location, "rb") as audio_file:
                # ဖိုင်ကို ဒီပုံစံအတိုင်း ပို့ပေးပါ
                transcription = client.audio.transcriptions.create(
                    file=(file.filename, audio_file), # audio_file.read() အစား audio_file ကို တိုက်ရိုက်ပေးလိုက်ပါ
                    model="whisper-large-v3",
                    response_format="text"
                )
            # ... ကျန်တဲ့ ကုဒ်များ ...
            os.remove(file_location)
            return {"srt_content": transcription}
        except Exception as e:
            # နောက်ဆုံး Key အထိ စမ်းလို့မရရင် တကယ့် Error အစစ် (str(e)) ကို Frontend ဆီ ပို့ပေးပါမည်
            if index == len(api_key_list) - 1:
                if os.path.exists(file_location):
                    os.remove(file_location)
                raise HTTPException(status_code=400, detail=f"API မှ လက်မခံပါ: {str(e)}")
            continue

# (၃) TTS Endpoint - Edge TTS ဖြင့် အသံထုတ်လုပ်ရန် (Frontend မှ Error ကို ဖြေရှင်းရန်)
@app.post("/api/tts")
async def generate_tts(request: TTSRequest, background_tasks: BackgroundTasks):
    try:
        # File နာမည်မထပ်စေရန် UUID ဖြင့် နာမည်ပေးခြင်း
        temp_dir = tempfile.gettempdir()
        filename = f"tts_{uuid.uuid4().hex}.mp3"
        filepath = os.path.join(temp_dir, filename)

        # Edge-TTS ဖြင့် အသံထုတ်ပြီး သိမ်းဆည်းခြင်း
        communicate = edge_tts.Communicate(request.text, request.voice)
        await communicate.save(filepath)

        # Audio file ကို Frontend သို့ ပို့ပေးပြီးနောက် Server ပေါ်မှ အလိုအလျောက် ပြန်ဖျက်ရန်
        background_tasks.add_task(remove_temp_file, filepath)

        return FileResponse(filepath, media_type="audio/mpeg", filename="voiceover.mp3")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"အသံထုတ်လုပ်ခြင်း မအောင်မြင်ပါ: {str(e)}")


# Render ပေါ်တွင် ဆာဗာ အလိုအလျောက် Run ဖို့အတွက်
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
