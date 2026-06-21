import cv2
import mediapipe as mp
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
import math
import threading
import time

# ==========================================
# KONFIGURASI & INISIALISASI
# ==========================================
WIDTH, HEIGHT = 1000, 700
NUM_PARTICLES = 1500  

lock = threading.Lock()
shared_data = {
    "mode": 1,
    "target_x": 0.0,
    "target_y": 0.0,
    "target_z": -12.0,
    "frame": None,
    "running": True
}

# ==========================================
# GENERASI DATA BENTUK (PARTIKEL 3D)
# ==========================================
pos_space = np.random.uniform(-4.0, 4.0, (NUM_PARTICLES, 3))

# Mode 2: Saturnus (Bola Inti + Cincin)
pos_planet = np.zeros((NUM_PARTICLES, 3))
NUM_SPHERE = 700  
for i in range(NUM_SPHERE):
    phi = np.random.uniform(0, 2 * np.pi)
    costheta = np.random.uniform(-1, 1)
    theta = np.arccos(costheta)
    r = 1.3  
    pos_planet[i, 0] = r * np.sin(theta) * np.cos(phi)
    pos_planet[i, 1] = r * np.sin(theta) * np.sin(phi)
    pos_planet[i, 2] = r * np.cos(theta)

for i in range(NUM_SPHERE, NUM_PARTICLES):
    theta = np.random.uniform(0, 2 * np.pi)
    r = np.random.uniform(1.8, 3.8)  
    pos_planet[i, 0] = r * np.cos(theta)
    pos_planet[i, 1] = np.random.uniform(-0.05, 0.05)  
    pos_planet[i, 2] = r * np.sin(theta)

# Mode 3: Tulisan "I LOVE YOU"
text_img = np.zeros((200, 800), dtype=np.uint8)
cv2.putText(text_img, "I LOVE YOU", (20, 130), cv2.FONT_HERSHEY_SIMPLEX, 3.5, 255, 12, cv2.LINE_AA)
y_indices, x_indices = np.where(text_img > 0)
x_text = (x_indices - 400) / 70.0
y_text = -(y_indices - 100) / 70.0 
z_text = np.random.uniform(-0.1, 0.1, len(x_text))
pos_text = np.zeros((NUM_PARTICLES, 3))
text_points = np.stack((x_text, y_text, z_text), axis=-1)
chosen_indices = np.random.choice(len(text_points), NUM_PARTICLES)
pos_text = text_points[chosen_indices]

# Mode 4: Bentuk Hati / Love
pos_heart = np.zeros((NUM_PARTICLES, 3))
for i in range(NUM_PARTICLES):
    t = np.random.uniform(-np.pi, np.pi)
    p = np.random.uniform(-np.pi, np.pi)
    
    x = 2.0 * (np.sin(t) ** 3)
    y = 2.0 * np.cos(t) - 0.7 * np.cos(2*t) - 0.3 * np.cos(3*t) - 0.1 * np.cos(4*t)
    z = np.sin(p) * 0.4  
    
    pos_heart[i, 0] = x * 0.85
    pos_heart[i, 1] = (y * 0.85) + 0.5  
    pos_heart[i, 2] = z

current_pos = np.copy(pos_space)
target_pos = np.copy(pos_space)

# ==========================================
# FUNGSI LOGIKA DETEKSI GESTUR
# ==========================================
def hitung_mode_gestur(hand_landmarks):
    tips = [8, 12, 16, 20]  
    pips = [6, 10, 14, 18]
    jari_berdiri = [hand_landmarks.landmark[t].y < hand_landmarks.landmark[p].y for t, p in zip(tips, pips)]
    
    if sum(jari_berdiri) == 0: 
        return 4  # Genggam -> Hati
    if jari_berdiri[0] and not any(jari_berdiri[1:]):
        return 2  # Telunjuk -> Saturnus
    if jari_berdiri[0] and jari_berdiri[1] and not jari_berdiri[2] and not jari_berdiri[3]:
        return 3  # Peace -> Teks I LOVE YOU
    return 1  # Default -> Kosmos

# ==========================================
# THREAD BACKGROUND: PROSES KAMERA & AI
# ==========================================
def camera_thread_func():
    cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
    # Trik khusus macOS: pancing kamera agar memberikan prompt izin akses
    cv2.waitKey(500)

    if not cap.isOpened():
        print("ERROR: Kamera tidak bisa dibuka. Cek izin kamera di System Settings > Privacy & Security > Camera,")
        print("lalu pastikan tidak ada aplikasi lain (Zoom/FaceTime/dll) yang sedang memakai kamera.")
        shared_data["running"] = False
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 480)   
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)
    
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.5, min_tracking_confidence=0.5)

    fail_count = 0
    got_first_frame = False

    while shared_data["running"]:
        try:
            ret, frame = cap.read()
            if not ret:
                fail_count += 1
                if fail_count % 60 == 0:
                    print(f"PERINGATAN: kamera terbuka tapi belum dapat frame sama sekali ({fail_count}x gagal). "
                          f"Cek izin kamera atau apakah kamera dipakai aplikasi lain.")
                time.sleep(0.01)
                continue

            if not got_first_frame:
                print("Frame pertama berhasil didapat dari kamera.")
                got_first_frame = True
            fail_count = 0

            frame = cv2.flip(frame, 1)  
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb_frame)

            local_mode = 1
            local_x, local_y, local_z = 0.0, 0.0, -12.0

            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    mp.solutions.drawing_utils.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                    local_mode = hitung_mode_gestur(hand_landmarks)
                    
                    wrist = hand_landmarks.landmark[0]
                    local_x = (wrist.x - 0.5) * 10.0 
                    local_y = -(wrist.y - 0.5) * 7.0 
                    
                    pinky_mcp = hand_landmarks.landmark[17]
                    distance = math.sqrt((wrist.x - pinky_mcp.x)**2 + (wrist.y - pinky_mcp.y)**2)
                    local_z = -10.0 - (1.0 / (distance + 0.01)) * 0.2

            with lock:
                shared_data["mode"] = local_mode
                shared_data["target_x"] = local_x
                shared_data["target_y"] = local_y
                shared_data["target_z"] = local_z
                shared_data["frame"] = frame
        except Exception as e:
            import traceback
            print("ERROR di dalam camera thread:")
            traceback.print_exc()
            time.sleep(0.5)

    cap.release()

# Jalankan Thread Kamera terlebih dahulu
camera_thread = threading.Thread(target=camera_thread_func, daemon=True)
camera_thread.start()

# Berikan jeda 1 detik agar kamera macOS siap sebelum Pygame mengambil alih GUI utama
time.sleep(1.0)

# ==========================================
# MAIN THREAD: RENDERING GRAFIS 3D (Pygame diinisialisasi di sini)
# ==========================================
pygame.init()
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_COMPATIBILITY)
pygame.display.set_mode(
    (WIDTH, HEIGHT),
    DOUBLEBUF | OPENGL | RESIZABLE
)
pygame.display.set_caption("Space Gesture Controller - Mac Optimized")

glMatrixMode(GL_PROJECTION)
glLoadIdentity()
gluPerspective(45, (WIDTH / HEIGHT), 0.1, 50.0)
glMatrixMode(GL_MODELVIEW)
glEnable(GL_DEPTH_TEST)

clock = pygame.time.Clock()
rotation_angle = 0.0
hand_x, hand_y, hand_z = 0.0, 0.0, -12.0

while shared_data["running"]:
    pygame.event.pump()
    for event in pygame.event.get():
        if event.type == pygame.QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
            shared_data["running"] = False
        elif event.type == VIDEORESIZE:
            WIDTH, HEIGHT = event.w, event.h
            glViewport(0, 0, WIDTH, HEIGHT)
            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            gluPerspective(45, (WIDTH / HEIGHT), 0.1, 50.0)
            glMatrixMode(GL_MODELVIEW)

    with lock:
        current_mode = shared_data["mode"]
        target_hand_x = shared_data["target_x"]
        target_hand_y = shared_data["target_y"]
        target_hand_z = shared_data["target_z"]
        frame = shared_data["frame"]

    if frame is not None:
        mode_labels = {
            1: "ROTASI ANGCOSMOS (Terbuka)", 
            2: "SATURNUS 3D (Satu Jari)", 
            3: "TEKS I LOVE YOU (Peace)", 
            4: "BENTUK HATI / LOVE (Kepal)"
        }
        cv2.putText(frame, f"MODE: {mode_labels.get(current_mode, 'UNKNOWN')}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        cv2.imshow("Hand Sensor Monitor", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            shared_data["running"] = False

    glClearColor(0.0, 0.0, 0.0, 1.0)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()

    hand_x += (target_hand_x - hand_x) * 0.25
    hand_y += (target_hand_y - hand_y) * 0.25
    hand_z += (target_hand_z - hand_z) * 0.25

    if current_mode == 1:
        target_pos = pos_space
        rotation_angle += 0.5 
    elif current_mode == 2:
        target_pos = pos_planet
        rotation_angle += 2.0 
    elif current_mode == 3:
        target_pos = pos_text
        rotation_angle = 0.0  
    elif current_mode == 4:
        target_pos = pos_heart
        rotation_angle += 1.5  

    current_pos += (target_pos - current_pos) * 0.15

    if current_mode in [2, 3, 4]:
        glTranslatef(hand_x, hand_y, hand_z)
        if current_mode == 2:
            glRotatef(25, 1.0, 0.0, 0.5)
    else:
        glTranslatef(0.0, 0.0, -12.0)
    
    glRotatef(rotation_angle, 0.0, 1.0, 0.0)

    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glPointSize(4.5)  
    
    glBegin(GL_POINTS)
    for i in range(NUM_PARTICLES):
        if current_mode == 3:
            glColor4f(0.0, 0.8, 1.0, 0.9)  
        elif current_mode == 4:
            glColor4f(1.0, 0.1, 0.4, 0.95) 
        elif current_mode == 2 and i >= NUM_SPHERE:
            glColor4f(1.0, 0.7, 0.3, 0.6)  
        elif current_mode == 2 and i < NUM_SPHERE:
            glColor4f(1.0, 0.5, 0.0, 0.85) 
        else:
            glColor4f(0.1, 0.5, 1.0, 0.8)  
            
        glVertex3f(current_pos[i, 0], current_pos[i, 1], current_pos[i, 2])
    glEnd()

    pygame.display.flip()
    clock.tick(60)

cv2.destroyAllWindows()
pygame.quit()
