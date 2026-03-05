"""
============================================================
  QR Code Reader → ESP32 Robot Arm Controller
  
  Requirements:
    pip install opencv-python pyzbar pyserial
  
  Usage:
    1. Connect ESP32 via USB
    2. Update COM_PORT below (e.g. 'COM3' on Windows, '/dev/ttyUSB0' on Linux)
    3. Run: python qr_robot_controller.py
    4. Show QR code to camera — arm moves automatically!
============================================================
"""

import cv2
from pyzbar import pyzbar
import serial
import serial.tools.list_ports
import time
import sys

# ── Configuration ──────────────────────────────────────────
COM_PORT    = 'COM3'        # ← CHANGE THIS to your ESP32 port
BAUD_RATE   = 115200
CAMERA_ID   = 0             # 0 = default webcam, change if needed
COOLDOWN    = 4.0           # seconds between two QR triggers (avoid repeat)

# ── QR → Command Mapping ───────────────────────────────────
QR_MAP = {
    "amazon":   ('A', "AMAZON",   30),
    "meesho":   ('M', "MEESHO",   60),
    "flipkart": ('F', "FLIPKART", 90),
}

# ── Colors for display ─────────────────────────────────────
COLOR = {
    "amazon":   (0, 165, 255),   # Orange
    "meesho":   (255, 0, 180),   # Pink
    "flipkart": (0, 200, 50),    # Green
    "unknown":  (0, 0, 255),     # Red
    "idle":     (200, 200, 200), # Gray
}

# ── Auto-detect ESP32 port ─────────────────────────────────
def find_esp32_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        desc = port.description.lower()
        if any(x in desc for x in ['cp210', 'ch340', 'esp32', 'uart', 'usb serial']):
            print(f"[INFO] Auto-detected ESP32 on: {port.device}")
            return port.device
    return None

# ── Connect to ESP32 ───────────────────────────────────────
def connect_serial(port):
    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=2)
        time.sleep(2)  # Wait for ESP32 to boot
        print(f"[OK] Connected to ESP32 on {port}")
        return ser
    except serial.SerialException as e:
        print(f"[ERROR] Cannot connect to {port}: {e}")
        return None

# ── Send command and wait for READY ───────────────────────
def send_command(ser, cmd_char, label):
    print(f"\n[→] Sending command '{cmd_char}' for {label}...")
    ser.write(cmd_char.encode())
    ser.flush()
    
    # Wait for ESP32 to finish and reply READY
    timeout = 30  # seconds max
    start = time.time()
    while time.time() - start < timeout:
        if ser.in_waiting:
            line = ser.readline().decode(errors='ignore').strip()
            if line:
                print(f"  [ESP32] {line}")
            if "READY" in line:
                print("[✓] ESP32 is ready for next command.")
                return True
        time.sleep(0.05)
    
    print("[WARN] Timeout waiting for ESP32 READY signal.")
    return False

# ── Draw overlay on frame ──────────────────────────────────
def draw_overlay(frame, status_text, status_color, qr_boxes=None):
    h, w = frame.shape[:2]
    
    # Top status bar
    cv2.rectangle(frame, (0, 0), (w, 50), (20, 20, 20), -1)
    cv2.putText(frame, status_text, (10, 33),
                cv2.FONT_HERSHEY_SIMPLEX, 0.85, status_color, 2)
    
    # QR bounding boxes
    if qr_boxes:
        for (x, y, w2, h2, text, color) in qr_boxes:
            cv2.rectangle(frame, (x, y), (x + w2, y + h2), color, 3)
            cv2.rectangle(frame, (x, y - 30), (x + w2, y), color, -1)
            cv2.putText(frame, text.upper(), (x + 4, y - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
    
    # Bottom guide
    cv2.rectangle(frame, (0, frame.shape[0] - 30), (frame.shape[1], frame.shape[0]), (20, 20, 20), -1)
    cv2.putText(frame, "Show QR: amazon | meesho | flipkart   [Q] Quit  [H] Home",
                (8, frame.shape[0] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150, 150, 150), 1)
    
    return frame

# ── Main ───────────────────────────────────────────────────
def main():
    # Find port
    port = find_esp32_port() or COM_PORT
    ser = connect_serial(port)
    
    if ser is None:
        print("\n[ERROR] Could not connect to ESP32.")
        print("  → Check USB cable")
        print("  → Update COM_PORT in the script")
        print("  → Install driver: CP210x or CH340")
        sys.exit(1)
    
    # Wait for initial READY from ESP32
    print("[INFO] Waiting for ESP32 to send READY...")
    timeout = 10
    start = time.time()
    while time.time() - start < timeout:
        if ser.in_waiting:
            line = ser.readline().decode(errors='ignore').strip()
            if line: print(f"  [ESP32] {line}")
            if "READY" in line:
                break
        time.sleep(0.05)
    
    # Open camera
    cap = cv2.VideoCapture(CAMERA_ID)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open camera {CAMERA_ID}")
        ser.close()
        sys.exit(1)
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    print("\n[RUNNING] Camera open. Show QR code to camera.")
    print("  Press Q to quit | Press H to send Home command\n")
    
    last_qr_data  = ""
    last_qr_time  = 0
    is_busy       = False
    status_text   = "Ready — Show QR Code"
    status_color  = COLOR["idle"]
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("[ERROR] Camera frame read failed.")
            break
        
        qr_boxes = []
        decoded = pyzbar.decode(frame)
        
        for qr in decoded:
            raw = qr.data.decode("utf-8", errors="ignore").strip().lower()
            
            # Draw box
            rx, ry, rw, rh = qr.rect
            brand_color = COLOR.get(raw, COLOR["unknown"])
            qr_boxes.append((rx, ry, rw, rh, raw, brand_color))
            
            now = time.time()
            already_done = (raw == last_qr_data and now - last_qr_time < COOLDOWN)
            
            if raw in QR_MAP and not is_busy and not already_done:
                cmd_char, label, angle = QR_MAP[raw]
                
                is_busy      = True
                last_qr_data = raw
                last_qr_time = now
                status_text  = f"Running: {label} → {angle}°"
                status_color = brand_color
                
                # Draw current frame with status before blocking
                display = draw_overlay(frame.copy(), status_text, status_color, qr_boxes)
                cv2.imshow("QR Robot Controller", display)
                cv2.waitKey(1)
                
                # Send command (blocking until arm finishes)
                send_command(ser, cmd_char, label)
                
                is_busy      = False
                status_text  = f"Done: {label} placed at {angle}° — Ready"
                status_color = brand_color
            
            elif raw not in QR_MAP:
                status_text  = f"Unknown QR: '{raw}'"
                status_color = COLOR["unknown"]
            
            elif already_done:
                status_text  = f"Cooldown... ({label} done)"
        
        if not decoded and not is_busy:
            status_text  = "Ready — Show QR Code"
            status_color = COLOR["idle"]
        
        # Draw and show
        display = draw_overlay(frame, status_text, status_color, qr_boxes)
        cv2.imshow("QR Robot Controller", display)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            print("[EXIT] Quitting...")
            break
        elif key == ord('h') or key == ord('H'):
            if not is_busy:
                print("[→] Sending HOME command...")
                send_command(ser, 'H', 'HOME')
                status_text  = "Arm returned to HOME"
                status_color = COLOR["idle"]
    
    cap.release()
    cv2.destroyAllWindows()
    ser.close()
    print("[DONE] Closed camera and serial connection.")

if __name__ == "__main__":
    main()
