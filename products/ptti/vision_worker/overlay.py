import collections
import json
import subprocess
import sys
from pathlib import Path
import cv2

video, prediction, destination = sys.argv[1:]
points = {p['frame']: p for p in json.loads(Path(prediction).read_text(encoding='utf-8'))}
cap = cv2.VideoCapture(video)
width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
temporary = str(Path(destination).with_suffix('.avi'))
writer = cv2.VideoWriter(temporary, cv2.VideoWriter_fourcc(*'MJPG'), cap.get(cv2.CAP_PROP_FPS), (width, height))
if not writer.isOpened(): raise RuntimeError('Overlay writer unavailable')
history = collections.deque(maxlen=20)
i = 0
while True:
    success, image = cap.read()
    if not success: break
    point = points.get(i)
    if point and point['visible']:
        center = (round(point['pixel_x']), round(point['pixel_y']))
        history.append(center)
        for a, b in zip(list(history), list(history)[1:]): cv2.line(image, a, b, (0, 220, 255), 2)
        cv2.circle(image, center, 9, (0, 255, 100), 2)
    else: history.clear()
    confidence = point.get('confidence') if point else None
    label = f'Frame {i} | confidence {confidence if confidence is not None else "N/A"}'
    cv2.putText(image, label, (25, 45), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 100), 2)
    writer.write(image); i += 1
writer.release(); cap.release()
subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', temporary, '-c:v', 'libx264',
                '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-n', destination], check=True)
Path(temporary).unlink()
