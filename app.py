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
        
        print(f"Downloading audio from: {audio_url}")
        
        response = requests.get(audio_url, timeout=300)
        response.raise_for_status()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
            temp_file.write(response.content)
            temp_path = temp_file.name
        
        try:
            audio = AudioSegment.from_file(temp_path)
            chunk_length_ms = chunk_minutes * 60 * 1000
            
            print(f"Audio length: {len(audio)/1000/60:.1f} minutes")
            
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
            
            print(f"Created {len(chunks_info)} chunks")
            
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
        print(f"Error: {str(e)}")
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
