"""
FraudLocate Lite - Synthetic Evidence Generator.
Creates simulated, synthetic CCTV images and short video clips for hackathon demonstration.

IMPORTANT ETHICAL & PRIVACY NOTICE:
All generated media is 100% synthetic graphic rendering.
No real human faces, CCTV surveillance feeds, banking systems, or police records are accessed or depicted.
"""

import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

try:
    import cv2
except ImportError:
    cv2 = None

SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sample_evidence")


def get_default_font():
    """Attempt to load a clean TTF font, fallback to default."""
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def generate_synthetic_cctv_image(
    filename: str,
    cam_id: str,
    atm_id: str,
    location_name: str,
    timestamp_str: str,
    theme: str = "day",
) -> str:
    """Generate a realistic synthetic CCTV surveillance still."""
    os.makedirs(SAMPLE_DIR, exist_ok=True)
    out_path = os.path.join(SAMPLE_DIR, filename)
    if os.path.exists(out_path):
        return out_path

    width, height = 720, 480
    # Background tone
    if theme == "night":
        base_color = (25, 32, 40)
        accent_color = (15, 23, 42)
    else:
        base_color = (45, 55, 72)
        accent_color = (30, 41, 59)

    img = Image.new("RGB", (width, height), color=base_color)
    draw = ImageDraw.Draw(img)

    # Draw simulated ATM vestibule geometry (interior wall, ATM kiosk shape, screen)
    # Background floor
    floor_color = (20, 25, 35) if theme == "night" else (35, 42, 54)
    draw.polygon([(0, 320), (width, 320), (width, height), (0, height)], fill=floor_color)

    # ATM Machine body
    draw.rectangle([240, 140, 480, 440], fill=(70, 80, 95), outline=(100, 115, 135), width=3)
    # ATM Screen
    draw.rectangle([280, 180, 440, 280], fill=(15, 76, 129), outline=(56, 189, 248), width=2)
    # Cash Dispenser Slot
    draw.rectangle([300, 320, 420, 340], fill=(20, 20, 20), outline=(200, 200, 200), width=1)
    # Keypad
    draw.rectangle([310, 360, 410, 400], fill=(40, 40, 40), outline=(100, 100, 100), width=1)

    # Synthetic ATM Text on screen
    draw.text((295, 220), "SYNTHETIC ATM", fill=(255, 255, 255))
    draw.text((310, 240), "[ACTIVE KIOSK]", fill=(56, 189, 248))

    # Add subtle surveillance noise
    np_img = np.array(img)
    noise = np.random.normal(0, 12, np_img.shape).astype(np.int16)
    noisy_img = np.clip(np_img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # Scan lines effect
    for y in range(0, height, 4):
        noisy_img[y : y + 1, :] = (noisy_img[y : y + 1, :] * 0.88).astype(np.uint8)

    img = Image.fromarray(noisy_img)
    draw = ImageDraw.Draw(img)

    # Camera OSD (On-Screen Display) Header & Footer
    draw.rectangle([0, 0, width, 44], fill=(0, 0, 0, 200))
    draw.rectangle([0, height - 36, width, height], fill=(0, 0, 0, 200))

    # Red REC indicator
    draw.ellipse([16, 14, 28, 26], fill=(239, 68, 68))
    draw.text((36, 14), "● REC [SIMULATED]", fill=(248, 113, 113))

    # Camera Info & Timestamp
    draw.text((210, 14), f"{cam_id} | {atm_id} ({location_name})", fill=(226, 232, 240))
    draw.text((560, 14), timestamp_str, fill=(250, 204, 21))

    # Bottom notice
    draw.text(
        (20, height - 26),
        "⚠️ DEMO SYNTHETIC EVIDENCE — FOR ALGORITHMIC PATROL DECISION SUPPORT ONLY",
        fill=(148, 163, 184),
    )

    img.save(out_path, quality=92)
    return out_path


def generate_synthetic_cctv_video(
    filename: str = "sample_cctv_clip.mp4",
    cam_id: str = "CAM-02",
    atm_id: str = "ATM_HYD_201",
    location_name: str = "Madhapur Tech Corridor",
    num_seconds: int = 3,
    fps: int = 15,
) -> str:
    """Generate a realistic short synthetic CCTV MP4 video with rolling timecode."""
    os.makedirs(SAMPLE_DIR, exist_ok=True)
    out_path = os.path.join(SAMPLE_DIR, filename)
    if os.path.exists(out_path):
        return out_path

    if cv2 is None:
        return out_path

    width, height = 640, 480
    total_frames = num_seconds * fps

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_path, fourcc, fps, (width, height))

    base_frame = np.full((height, width, 3), (35, 45, 55), dtype=np.uint8)
    # Floor
    cv2.rectangle(base_frame, (0, 320), (width, height), (22, 28, 36), -1)
    # ATM machine
    cv2.rectangle(base_frame, (220, 140), (420, 440), (60, 70, 85), -1)
    cv2.rectangle(base_frame, (220, 140), (420, 440), (100, 110, 130), 2)
    # Screen
    cv2.rectangle(base_frame, (250, 170), (390, 260), (120, 60, 20), -1)
    # Cash slot
    cv2.rectangle(base_frame, (270, 300), (370, 320), (15, 15, 15), -1)
    # Keypad
    cv2.rectangle(base_frame, (280, 340), (360, 380), (30, 30, 30), -1)

    for i in range(total_frames):
        frame = base_frame.copy()

        # Add frame-varying digital surveillance noise
        noise = np.random.normal(0, 8, frame.shape).astype(np.int16)
        frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        # Subtle scan line pulse
        scan_offset = (i * 12) % height
        cv2.line(frame, (0, scan_offset), (width, scan_offset), (80, 90, 105), 1)

        # OSD Header bar
        cv2.rectangle(frame, (0, 0), (width, 40), (10, 10, 10), -1)
        # REC icon
        cv2.circle(frame, (20, 20), 6, (0, 0, 220), -1)
        cv2.putText(frame, "REC [SIMULATED]", (35, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 150, 255), 1)

        # Camera & ATM tag
        tag_text = f"{cam_id} | {atm_id} | {location_name}"
        cv2.putText(frame, tag_text, (170, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1)

        # Timecode
        sub_sec = int((i % fps) * (100 / fps))
        second_val = 15 + int(i / fps)
        timecode = f"2026-10-02 18:45:{second_val:02d}:{sub_sec:02d}"
        cv2.putText(frame, timecode, (460, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 240, 240), 1)

        # Bottom disclaimer
        cv2.rectangle(frame, (0, height - 30), (width, height), (10, 10, 10), -1)
        cv2.putText(
            frame,
            "SYNTHETIC FRAUD EVIDENCE - ALGORITHMIC DECISION SUPPORT DEMO",
            (20, height - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.36,
            (130, 140, 155),
            1,
        )

        writer.write(frame)

    writer.release()
    return out_path


def ensure_sample_evidence_exists() -> None:
    """Generate all baseline sample evidence if not present."""
    os.makedirs(SAMPLE_DIR, exist_ok=True)
    generate_synthetic_cctv_image(
        filename="sample_cctv_1.jpg",
        cam_id="CAM-01 [Ameerpet Metro]",
        atm_id="ATM_HYD_102",
        location_name="Maitrivanam Kiosk",
        timestamp_str="2026-10-02 10:42:15",
        theme="day",
    )
    generate_synthetic_cctv_image(
        filename="sample_cctv_2.jpg",
        cam_id="CAM-04 [Cyber Towers]",
        atm_id="ATM_HYD_201",
        location_name="Hitec City Concourse",
        timestamp_str="2026-10-02 19:35:40",
        theme="night",
    )
    generate_synthetic_cctv_image(
        filename="sample_atm_kiosk.jpg",
        cam_id="SURV-08 [Transit Hub]",
        atm_id="ATM_HYD_303",
        location_name="Station Rd Lounge",
        timestamp_str="2026-10-02 14:10:05",
        theme="day",
    )
    generate_synthetic_cctv_video(
        filename="sample_cctv_clip.mp4",
        cam_id="CAM-02",
        atm_id="ATM_HYD_201",
        location_name="Madhapur Tech Corridor",
        num_seconds=3,
        fps=15,
    )


if __name__ == "__main__":
    ensure_sample_evidence_exists()
    print("Sample synthetic evidence successfully verified/generated.")
