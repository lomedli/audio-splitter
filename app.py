from flask import Flask, request, jsonify, send_file
import requests
import tempfile
import os
import uuid
import threading
import time
import subprocess

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

def get_audio_duration(file_path):
    """Get audio duration in seconds using ffprobe"""
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        file_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())

def split_audio_ffmpeg(input_path, output_path, start_time, duration):
    """Split audio using ffmpeg"""
    cmd = [
        'ffmpeg', '-i', input_path,
        '-ss', str(start_time),
        '-t', str(duration),
        '-acodec', 'libmp3lame',
        '-ab', '64k',
        '-ac', '1',
        '-y',
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)

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
            # Get audio duration
            total_duration = get_audio_duration(temp_path)
            print(f"Audio length: {total_duration/60:.1f} minutes")
            
            chunk_duration = chunk_minutes * 60
            
            session_id = str(uuid.uuid4())[:8]
            chunks_dir = f"/tmp/chunks_{session_id}"
            os.makedirs(chunks_dir, exist_ok=True)
            
            chunks_info = []
            chunks_paths = []
            start_time = 0
            chunk_number = 1
            
            while start_time < total_duration:
                end_time = min(start_time + chunk_duration, total_duration)
                actual_duration = end_time - start_time
                
                chunk_filename = f"chunk_{chunk_number}.mp3"
                chunk_path = os.path.join(chunks_dir, chunk_filename)
                
                # Split using ffmpeg
                split_audio_ffmpeg(temp_path, chunk_path, start_time, actual_duration)
                
                chunks_paths.append(chunk_path)
                
                download_url = f"{request.host_url}download/{session_id}/{chunk_number}"
                
                chunks_info.append({
                    "url": download_url,
                    "chunk_number": chunk_number,
                    "start_time": round(start_time, 2),
                    "end_time": round(end_time, 2),
                    "duration_minutes": round(actual_duration / 60, 2)
                })
                
                if end_time >= total_duration:
                    break
                
                start_time = end_time - 2
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
                "total_duration_minutes": round(total_duration / 60, 2),
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
