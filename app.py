from flask import Flask, request, jsonify, send_file
from pydub import AudioSegment
import requests
import tempfile
import os
import uuid
import threading
import time

app = Flask(__name__)

temp_files = {}

def cleanup_old_files():
    while True:
        time.sleep(3600)
        current_time = time.time()
        to_delete = []
        
        for session_id, data in temp_files.items():
            if current_time - data['created'] > 3600:
                for chunk_path in data['chunks']:
                    if os.path.exists(chunk_path):
                        os.remove(chunk_path)
                to_delete.append(session_id)
        
        for session_id in to_delete:
            del temp_files[session_id]

cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

@app.route('/split', methods=['POST'])
def split_audio():
    try:
        data = request.json
        audio_url = data['audio_url']
        chunk_minutes = data.get('chunk_minutes', 5)
        
        print(f"מוריד אודיו מ: {audio_url}")
        
        response = requests.get(audio_url, timeout=300)
        response.raise_for_status()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
            temp_file.write(response.content)
            temp_path = temp_file.name
        
        try:
            audio = AudioSegment.from_file(temp_path)
            chunk_length_ms = chunk_minutes * 60 * 1000
            
            print(f"אורך אודיו: {len(audio)/1000/60:.1f} דקות")
            
            session_id = str(uuid.uuid4())[:8]
            chunks_dir = f"/tmp/chunks_{session_id}"
            os.makedirs(chunks_dir, exist_ok=True)
            
            chunks_info = []
            chunks_paths = []
            start = 0
            chunk_number = 1
            
            while start < len(audio):
                end = min(start + chunk_length_ms, len(audio))
                chunk = audio[start:end]
                
                chunk_filename = f"chunk_{chunk_number}.mp3"
                chunk_path = os.path.join(chunks_dir, chunk_filename)
                
                chunk.export(
                    chunk_path,
                    format="mp3",
                    bitrate="64k",
                    parameters=["-ac", "1"]
                )
                
                chunks_paths.append(chunk_path)
                
                download_url = f"{request.host_url}download/{session_id}/{chunk_number}"
                
                chunks_info.append({
                    "url": download_url,
                    "chunk_number": chunk_number,
                    "start_time": round(start / 1000, 2),
                    "end_time": round(end / 1000, 2),
                    "duration_minutes": round((end - start) / 1000 / 60, 2)
                })
                
                if end >= len(audio):
                    break
                
                start = end - 2000
                chunk_number += 1
            
            temp_files[session_id] = {
                'chunks': chunks_paths,
                'created': time.time()
            }
            
            print(f"נוצרו {len(chunks_info)} חלקים")
            
            return jsonify({
                "success": True,
                "session_id": session_id,
                "total_chunks": len(chunks_info),
                "total_duration_minutes": round(len(audio) / 1000 / 60, 2),
                "chunks": chunks_info
            })
            
        finally:
            os.remove(temp_path)
            
    except Exception as e:
        print(f"שגיאה: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/download/<session_id>/<int:chunk_number>', methods=['GET'])
def download_chunk(session_id, chunk_number):
    if session_id not in temp_files:
        return jsonify({"error": "Session not found"}), 404
    
    chunks = temp_files[session_id]['chunks']
    
    if chunk_number < 1 or chunk_number > len(chunks):
        return jsonify({"error": "Invalid chunk number"}), 404
    
    chunk_path = chunks[chunk_number - 1]
    
    if not os.path.exists(chunk_path):
        return jsonify({"error": "File not found"}), 404
    
    return send_file(
        chunk_path,
        mimetype='audio/mpeg',
        as_attachment=True,
        download_name=f'chunk_{chunk_number}.mp3'
    )

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
```

שמור בשם: `app.py`

---

### קובץ 2: `requirements.txt`

פתח Notepad חדש, הדבק:
```
flask==3.0.0
pydub==0.25.1
requests==2.31.0
gunicorn==21.2.0
```

שמור בשם: `requirements.txt`

---

### קובץ 3: `Procfile`

פתח Notepad חדש, הדבק:
```
web: gunicorn app:app
```

שמור בשם: `Procfile` (בלי סיומת!)

---

## שלב 2: העלאה ל-GitHub

**א. יצירת חשבון GitHub (אם אין לך):**
1. לך ל-https://github.com
2. לחץ "Sign up"
3. מלא פרטים
4. אמת את המייל

**ב. יצירת Repository:**
1. אחרי שנכנסת, לחץ על הכפתור הירוק "New" (או "+" למעלה)
2. מלא:
   - Repository name: `audio-splitter`
   - בחר: **Public**
   - לחץ "Create repository"

**ג. העלאת הקבצים:**
1. תראה מסך עם אפשרויות
2. לחץ על "uploading an existing file"
3. גרור את 3 הקבצים שיצרת (app.py, requirements.txt, Procfile)
4. למטה כתוב "Add files"
5. לחץ "Commit changes"

✅ **סיימת! עכשיו יש לך את הקוד ב-GitHub**

---

## שלב 3: העלאה ל-Render.com

**א. יצירת חשבון:**
1. לך ל-https://render.com
2. לחץ "Get Started for Free"
3. בחר "Sign in with GitHub"
4. אשר את החיבור

**ב. יצירת Web Service:**
1. אחרי שנכנסת, תראה Dashboard
2. לחץ "New +" למעלה
3. בחר "Web Service"
4. תראה רשימה של ה-Repositories שלך
5. מצא את `audio-splitter`
6. לחץ "Connect" ליד השם

**ג. הגדרות (מלא בדיוק כך):**
```
Name: audio-splitter
Region: Oregon (US West)
Branch: main
Runtime: Python 3
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app

Instance Type: Free
```

7. גלול למטה ולחץ "Create Web Service"

**ד. המתן:**
- תראה לוגים רצים
- המתן 2-3 דקות
- כשזה מסיים תראה למעלה URL כמו:
  `https://audio-splitter-xxxx.onrender.com`

**ה. העתק את ה-URL הזה!** תצטרך אותו למייק.

---

# חלק ב': בניית הסנריו ב-Make.com

## שלב 4: יצירת התרחיש ב-Make

**א. כניסה ל-Make:**
1. לך ל-https://www.make.com
2. התחבר לחשבון שלך

**ב. יצירת תרחיש חדש:**
1. לחץ "Create a new scenario"
2. שם: "Audio Splitter + BASE"

---

## שלב 5: הוספת Webhook

**Module 1: Webhook**

1. לחץ על ה-"+" הראשון
2. חפש "Webhooks"
3. בחר "Custom Webhook"
4. לחץ "Create a webhook"
5. שם: `Audio Split Webhook`
6. לחץ "Save"
7. **העתק את ה-URL** שקיבלת (נראה כמו: https://hook.eu2.make.com/xxxx)

✅ עכשיו יש לך webhook! בוא נמשיך.

---

## שלב 6: הוספת HTTP Request לשרת

**Module 2: HTTP Request**

1. לחץ על ה-"+" אחרי ה-Webhook
2. חפש "HTTP"
3. בחר "Make a request"
4. מלא:
```
URL: https://audio-splitter-xxxx.onrender.com/split
(שים את ה-URL שקיבלת מRender!)

Method: POST

Headers:
  Key: Content-Type
  Value: application/json

Body type: Raw

Request content:
{
  "audio_url": "{{1.audio_url}}",
  "chunk_minutes": 5
}
```

5. Parse response: **YES**
6. לחץ "OK"

---

## שלב 7: הוספת Iterator

**Module 3: Iterator**

1. לחץ על ה-"+" אחרי HTTP
2. חפש "Iterator"
3. בחר "Iterator"
4. ב-Array: לחץ על השדה
5. תראה את הנתונים מ-Module 2
6. בחר: `2. chunks`
7. לחץ "OK"

---

## שלב 8: שליחה ל-BASE 44

**Module 4: HTTP Request (ל-BASE)**

1. לחץ על ה-"+" אחרי Iterator
2. שוב "HTTP" → "Make a request"
3. מלא (תצטרך לשנות לפי ה-API של BASE):
```
URL: [כאן תשים את ה-URL של BASE 44 API שלך]

Method: POST

Headers:
  Key: Content-Type
  Value: application/json

Body type: Raw

Request content:
{
  "audio_url": "{{3.url}}",
  "chunk_number": {{3.chunk_number}}
}