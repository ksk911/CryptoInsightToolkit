import requests
import json
import os
from datetime import datetime
from typing import Optional

# --- CONFIGURATION ---
BOT_TOKEN: str = "8461651460:AAGLtyh7IEUPnVjiJqsqgIOsEw9XhMxdQ6Y" 
CHAT_ID: str = "5058519218"

# API Endpoints
TELEGRAM_MESSAGE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
TELEGRAM_DOCUMENT_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
TELEGRAM_PHOTO_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"


def send_telegram_message(message: str) -> bool:
    """
    Sends a text message to the configured Telegram chat.
    
    Args:
        message: Text message to send (supports Markdown formatting)
    
    Returns:
        bool: True if successful, False otherwise
    """
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    
    try:
        response = requests.post(TELEGRAM_MESSAGE_URL, data=payload, timeout=10)
        response.raise_for_status()
        print(f"[SUCCESS] Telegram message sent at {datetime.now().strftime('%H:%M:%S')}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Telegram message failed: {e}")
        return False


def send_telegram_document(file_path: str, caption: str = "") -> bool:
    """
    Sends a document/file (CSV, ZIP, TXT, etc.) to Telegram.
    
    Args:
        file_path: Full path to the file to send
        caption: Optional caption/description for the file (supports Markdown)
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Validate file exists
    if not os.path.exists(file_path):
        print(f"[ERROR] File not found: {file_path}")
        return False
    
    # Get file size for logging
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    file_name = os.path.basename(file_path)
    
    print(f"[INFO] Sending document: {file_name} ({file_size_mb:.2f} MB)")
    
    try:
        with open(file_path, 'rb') as file:
            files = {'document': file}
            data = {
                'chat_id': CHAT_ID,
                'caption': caption,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(
                TELEGRAM_DOCUMENT_URL, 
                files=files, 
                data=data,
                timeout=30  # Longer timeout for file uploads
            )
            response.raise_for_status()
            
        print(f"[SUCCESS] Document sent: {file_name}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to send document: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error sending document: {e}")
        return False


def send_telegram_photo(image_path: str, caption: str = "") -> bool:
    """
    Sends an image (PNG, JPG, etc.) to Telegram.
    
    Args:
        image_path: Full path to the image file
        caption: Optional caption/description for the image (supports Markdown)
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Validate file exists
    if not os.path.exists(image_path):
        print(f"[ERROR] Image not found: {image_path}")
        return False
    
    # Validate file extension
    valid_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp']
    file_ext = os.path.splitext(image_path)[1].lower()
    if file_ext not in valid_extensions:
        print(f"[ERROR] Invalid image format: {file_ext}. Must be PNG, JPG, or GIF")
        return False
    
    file_name = os.path.basename(image_path)
    file_size_mb = os.path.getsize(image_path) / (1024 * 1024)
    
    print(f"[INFO] Sending photo: {file_name} ({file_size_mb:.2f} MB)")
    
    try:
        with open(image_path, 'rb') as photo:
            files = {'photo': photo}
            data = {
                'chat_id': CHAT_ID,
                'caption': caption,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(
                TELEGRAM_PHOTO_URL,
                files=files,
                data=data,
                timeout=30
            )
            response.raise_for_status()
            
        print(f"[SUCCESS] Photo sent: {file_name}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to send photo: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error sending photo: {e}")
        return False


def send_multiple_files(file_paths: list, caption: str = "") -> dict:
    """
    Sends multiple files to Telegram in sequence.
    
    Args:
        file_paths: List of file paths to send
        caption: Caption for the batch (will be sent with first file)
    
    Returns:
        dict: Status report with success/failure counts
    """
    results = {
        'total': len(file_paths),
        'success': 0,
        'failed': 0,
        'failed_files': []
    }
    
    print(f"\n[INFO] Sending {len(file_paths)} files to Telegram...")
    
    for idx, file_path in enumerate(file_paths):
        # Add caption only to first file
        file_caption = caption if idx == 0 else ""
        
        # Determine if it's an image or document
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
            success = send_telegram_photo(file_path, file_caption)
        else:
            success = send_telegram_document(file_path, file_caption)
        
        if success:
            results['success'] += 1
        else:
            results['failed'] += 1
            results['failed_files'].append(os.path.basename(file_path))
    
    print(f"\n[SUMMARY] Files sent: {results['success']}/{results['total']}")
    if results['failed'] > 0:
        print(f"[WARNING] Failed files: {', '.join(results['failed_files'])}")
    
    return results


# ============================================
# TEST SECTION - Run this file directly to test
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("TELEGRAM FILE SENDER - TEST MODE")
    print("=" * 60)
    print()
    
    # Test 1: Send a text message
    print("[TEST 1] Sending test message...")
    send_telegram_message("*Test Alert:* Telegram file sender is now active! 🚀")
    
    print("\n" + "-" * 60 + "\n")
    
    # Test 2: Create and send a test CSV file
    print("[TEST 2] Creating and sending test CSV file...")
    
    # Create a sample CSV file for testing
    test_csv_path = "test_data.csv"
    with open(test_csv_path, 'w') as f:
        f.write("timestamp,symbol,price,volume\n")
        f.write("2024-01-15 10:00:00,BTCUSDT,42000.50,1.234\n")
        f.write("2024-01-15 10:01:00,BTCUSDT,42100.75,2.456\n")
        f.write("2024-01-15 10:02:00,BTCUSDT,42050.25,1.789\n")
    
    send_telegram_document(
        test_csv_path,
        caption="📊 *Test CSV Export*\nSample trading data from system test"
    )
    
    # Clean up test file
    if os.path.exists(test_csv_path):
        os.remove(test_csv_path)
        print(f"[CLEANUP] Removed test file: {test_csv_path}")
    
    print("\n" + "-" * 60 + "\n")
    
    # Test 3: Instructions for image testing
    print("[TEST 3] Image testing instructions:")
    print("""
    To test image sending, you need an actual image file.
    
    Example usage:
    
    from telegram_sender import send_telegram_photo
    
    send_telegram_photo(
        "chart.png",
        caption="📈 *Price Chart*\\nBTCUSDT 1-minute candles"
    )
    
    Note: You'll generate actual chart images from Streamlit pages.
    """)
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE - Check your Telegram chat!")
    print("=" * 60)