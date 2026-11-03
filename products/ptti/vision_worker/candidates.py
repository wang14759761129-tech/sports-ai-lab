"""Real sigmoid-response peaks. Responses are NOT calibrated probabilities."""
def extract_peaks(heatmap, top_k, minimum_response, radius):
    import numpy as np
    if top_k < 1 or radius < 1 or not 0 <= minimum_response <= 1:
        raise ValueError('Invalid candidate parameters')
    values = np.asarray(heatmap, dtype=np.float32).copy()
    if values.ndim != 2 or not np.isfinite(values).all():
        raise ValueError('Invalid heatmap')
    import cv2
    local_max = cv2.dilate(values.astype(np.float32), np.ones((3,3),np.uint8))
    values[values < local_max] = -1
    peaks = []
    for _ in range(top_k):
        y, x = np.unravel_index(values.argmax(), values.shape)
        response = float(values[y, x])
        if response < minimum_response:
            break
        peaks.append({'model_x': int(x), 'model_y': int(y), 'model_response': response})
        # Greedy spatial NMS keeps a weak peak away from a strong distractor.
        values[max(0,y-radius):y+radius+1,max(0,x-radius):x+radius+1] = -1
    return peaks
