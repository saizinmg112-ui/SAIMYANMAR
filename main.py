from fastapi import FastAPI, UploadFile, File, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
import os
import uvicorn # ဆာဗာ Run ဖို့အတွက် ထပ်ထည့်ထားပါတယ်

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/transcribe")
async def transcribe_audio(file: UploadFile = File(...), x_api_keys: str = Header(None)):
    if not x_api_keys:
        raise HTTPException(status_code=401, detail="API Key လိုအပ်ပါသည်။")

    api_key_list = [k.strip() for k in x_api_keys.split(",") if k.strip()]
    file_location = f"/tmp/{file.filename}" 
    
    with open(file_location, "wb") as f:
        f.write(await file.read())

    for index, current_key in enumerate(api_key_list):
        try:
            client = Groq(api_key=current_key)
            with open(file_location, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    file=(file.filename, audio_file.read()),
                    model="whisper-large-v3",
                    response_format="text"
                )
            os.remove(file_location)
            return {"srt_content": transcription}
        except Exception as e:
            if index == len(api_key_list) - 1:
                if os.path.exists(file_location):
                    os.remove(file_location)
                raise HTTPException(status_code=400, detail="Keys အားလုံး Limit ပြည့်သွားပါပြီ။")
            continue

# မှတ်ချက်။ ။ အစ်ကိုရေးထားတဲ့ Microsoft Voice (edge-tts) အသံထုတ်မယ့်ကုဒ် ရှိရင် ဒီကြားထဲမှာ ထည့်ရေးလို့ရပါတယ်။

# SnapDeploy သို့မဟုတ် Render ပေါ်မှာ ဆာဗာ အလိုအလျောက် Run ဖို့အတွက် ဒီအပိုင်း အောက်ဆုံးမှာ မဖြစ်မနေ ပါရပါမယ်
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
