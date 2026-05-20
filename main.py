import os
import sys
import re
import random
import string
import time
import json
import platform
import requests
import subprocess
import imaplib
import email
from email.header import decode_header
from typing import Set, Optional
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from faker import Faker
import pyotp
import logging
import threading
import html

import concurrent.futures
from os import path
from urllib.request import Request, urlopen

# Setup logging
logging.basicConfig(level=logging.INFO, filename="app.log", format="%(asctime)s - %(levelname)s - %(message)s")

# ANSI color codes
W = '\033[97m'
G = '\033[92m'
R = '\033[91m'
V = '\033[1;34m'
Y = '\033[93m'
B = '\033[1;30m'
RESET = '\033[0m'

ua = UserAgent()

# ============ YANDEX EMAIL CONFIGURATION ============
from dotenv import load_dotenv
load_dotenv()

YANDEX_EMAIL = os.getenv("YANDEX_EMAIL", "k3wiin@yandex.com")
YANDEX_APP_PASSWORD = os.getenv("YANDEX_APP_PASSWORD", "guboopikktydwgmw")

# ============ PROXY CONFIGURATION ============
PROXY_FILE = "proxies.txt"
working_proxies = []
proxy_lock = threading.Lock()

def load_proxies():
    """Load proxies from proxies.txt file"""
    proxies = []
    if not os.path.exists(PROXY_FILE):
        print(f"{Y}[!] proxies.txt not found, creating empty file{W}")
        open(PROXY_FILE, 'w').close()
        return proxies
    
    with open(PROXY_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                proxies.append(line)
    
    print(f"{G}[✓] Loaded {len(proxies)} proxies from {PROXY_FILE}{W}")
    return proxies

def test_proxy(proxy):
    """Test if proxy is working with Facebook"""
    try:
        test_url = "https://mbasic.facebook.com"
        proxies = {"http": proxy, "https": proxy}
        response = requests.get(test_url, proxies=proxies, timeout=10, headers={"User-Agent": ugenX()})
        if response.status_code == 200:
            return True, proxy
        return False, proxy
    except:
        return False, proxy

def get_working_proxies():
    """Get all working proxies from list"""
    global working_proxies
    all_proxies = load_proxies()
    
    if not all_proxies:
        print(f"{Y}[!] No proxies found, using direct connection{W}")
        return []
    
    print(f"{Y}[*] Testing {len(all_proxies)} proxies...{W}")
    working = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(test_proxy, proxy): proxy for proxy in all_proxies}
        for future in concurrent.futures.as_completed(futures):
            is_working, proxy = future.result()
            if is_working:
                working.append(proxy)
                print(f"{G}[✓] Working proxy: {proxy}{W}")
    
    working_proxies = working
    print(f"{G}[✓] {len(working)} working proxies found{W}")
    return working

def get_random_proxy():
    """Get a random working proxy"""
    global working_proxies
    with proxy_lock:
        if working_proxies:
            return random.choice(working_proxies)
    return None

def create_session_with_proxy():
    """Create a requests session with proxy"""
    session = requests.Session()
    proxy = get_random_proxy()
    if proxy:
        session.proxies = {"http": proxy, "https": proxy}
        print(f"{Y}[*] Using proxy: {proxy}{W}")
    else:
        print(f"{Y}[*] No proxy available, using direct connection{W}")
    return session

# ============ OTP EXTRACTION ============
def extract_otp_from_text(text):
    if not text:
        return None
    text = html.unescape(text)
    fb_match = re.search(r'FB[-\s]*(\d{5,6})', text, re.IGNORECASE)
    if fb_match:
        return fb_match.group(1)
    code_match = re.search(r'(?:code|confirmation code)[:\s]+(\d{5,6})', text, re.IGNORECASE)
    if code_match:
        return code_match.group(1)
    isolated_match = re.search(r'(?<!\d)(\d{5,6})(?!\d)', text)
    if isolated_match:
        return isolated_match.group(1)
    return None

def fetch_otp_from_yandex(email_address, timeout=180, mark_read=True):
    """Yandex se OTP fetch karega"""
    try:
        imap = imaplib.IMAP4_SSL("imap.yandex.com")
        imap.login(YANDEX_EMAIL, YANDEX_APP_PASSWORD)
        imap.select("INBOX")
        
        start_time = time.time()
        
        print(f"{Y}[*] Looking for OTP for email: {email_address}{W}")
        
        while time.time() - start_time < timeout:
            status, messages = imap.search(None, f'HEADER Delivered-To "{email_address}"')
            
            if status != "OK" or not messages[0]:
                status, messages = imap.search(None, '(UNSEEN FROM "facebookmail.com")')
            
            if status != "OK" or not messages[0]:
                status, messages = imap.search(None, f'TEXT "{email_address.split("@")[0]}"')
            
            if status == "OK" and messages[0]:
                email_ids = messages[0].split()
                latest_ids = sorted(email_ids, key=lambda x: int(x), reverse=True)
                
                for num in latest_ids[:10]:
                    status, msg_data = imap.fetch(num, "(RFC822)")
                    
                    if status == "OK":
                        for response_part in msg_data:
                            if isinstance(response_part, tuple):
                                msg = email.message_from_bytes(response_part[1])
                                
                                delivered_to = msg.get("Delivered-To", "")
                                x_original_to = msg.get("X-Original-To", "")
                                to_header = msg.get("To", "")
                                from_header = msg.get("From", "")
                                
                                is_for_us = (email_address in delivered_to or 
                                           email_address in x_original_to or
                                           email_address in to_header)
                                
                                subject, encoding = decode_header(msg["Subject"])[0]
                                if isinstance(subject, bytes):
                                    subject = subject.decode(encoding if encoding else "utf-8")
                                
                                body = ""
                                if msg.is_multipart():
                                    for part in msg.walk():
                                        if part.get_content_type() in ["text/plain", "text/html"]:
                                            body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                                            break
                                else:
                                    body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
                                
                                full_text = subject + " " + body
                                otp = extract_otp_from_text(full_text)
                                
                                if otp and len(otp) >= 5:
                                    if is_for_us or "facebook" in from_header.lower():
                                        if mark_read:
                                            imap.store(num, '+FLAGS', '\\Seen')
                                        imap.close()
                                        imap.logout()
                                        print(f"{G}[✓] OTP fetched: {otp} for {email_address}{W}")
                                        return otp
            
            elapsed = int(time.time() - start_time)
            print(f"{Y}[*] Polling for OTP... ({elapsed}s / {timeout}s){W}", end="\r")
            time.sleep(8)
        
        imap.close()
        imap.logout()
        return None
        
    except Exception as e:
        logging.error(f"Yandex IMAP error: {e}")
        return None

def mark_emails_as_read(email_address):
    try:
        imap = imaplib.IMAP4_SSL("imap.yandex.com")
        imap.login(YANDEX_EMAIL, YANDEX_APP_PASSWORD)
        imap.select("INBOX")
        status, messages = imap.search(None, f'TO "{email_address}"')
        if status == "OK" and messages[0]:
            for num in messages[0].split():
                imap.store(num, '+FLAGS', '\\Seen')
        imap.close()
        imap.logout()
    except:
        pass

def request_resend_code(session, current_page_text):
    try:
        soup = BeautifulSoup(current_page_text, 'html.parser')
        resend_elem = None
        for a in soup.find_all('a', href=True):
            if 'resend' in a.text.lower() or 'again' in a.text.lower():
                resend_elem = a
                break
        if not resend_elem:
            for btn in soup.find_all('button'):
                if 'resend' in btn.text.lower() or 'again' in btn.text.lower():
                    resend_elem = btn
                    break
        if not resend_elem:
            return False
        url = resend_elem.get('href')
        if not url.startswith('http'):
            url = 'https://mbasic.facebook.com' + url
        resp = session.get(url, allow_redirects=True)
        return 'checkpoint' in resp.text.lower() or 'code' in resp.text.lower()
    except:
        return False

def submit_otp_to_facebook(session, otp_code, max_attempts=3):
    for attempt in range(max_attempts):
        try:
            print(f"{Y}[*] Submitting OTP {otp_code} (attempt {attempt+1})...{W}")
            
            current_url = "https://mbasic.facebook.com/"
            resp = session.get(current_url, allow_redirects=True)
            
            if 'c_user' in session.cookies.get_dict():
                cookies = session.cookies.get_dict()
                print(f"{G}[✓] Already confirmed! UID: {cookies['c_user']}{W}")
                return True, cookies['c_user'], cookies
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            fb_dtsg = None
            dtsg_input = soup.find('input', {'name': 'fb_dtsg'})
            if dtsg_input:
                fb_dtsg = dtsg_input.get('value')
            
            jazoest = None
            jazoest_input = soup.find('input', {'name': 'jazoest'})
            if jazoest_input:
                jazoest = jazoest_input.get('value')
            
            form = None
            for f in soup.find_all('form'):
                if 'checkpoint' in str(f).lower() or 'confirm' in str(f).lower() or 'code' in str(f).lower():
                    form = f
                    break
            
            if form:
                action = form.get('action', '')
                if not action.startswith('http'):
                    if action.startswith('/'):
                        action = 'https://mbasic.facebook.com' + action
                    else:
                        action = 'https://mbasic.facebook.com/' + action
                
                fields = {}
                for inp in form.find_all('input'):
                    name = inp.get('name')
                    value = inp.get('value', '')
                    if name:
                        fields[name] = value
                
                otp_field = None
                for key in ['code', 'confirm_code', 'n', 'otp', 'verification_code', 'confirmation_code', 'approvals_code']:
                    if key in fields:
                        otp_field = key
                        break
                
                if not otp_field:
                    for inp in form.find_all('input'):
                        inp_type = inp.get('type', '').lower()
                        if inp_type in ['text', 'number', 'tel']:
                            otp_field = inp.get('name')
                            break
                
                if otp_field:
                    fields[otp_field] = otp_code
                    print(f"{G}[✓] OTP placed in field: {otp_field}{W}")
                    
                    headers = {
                        "User-Agent": ugenX(),
                        "Referer": current_url,
                        "Content-Type": "application/x-www-form-urlencoded"
                    }
                    
                    submit_resp = session.post(action, data=fields, headers=headers, allow_redirects=True, timeout=20)
                    
                    cookies = session.cookies.get_dict()
                    if 'c_user' in cookies:
                        print(f"{G}[✓] OTP accepted! UID: {cookies['c_user']}{W}")
                        return True, cookies['c_user'], cookies
            
            if fb_dtsg:
                json_payload = {
                    'fb_dtsg': fb_dtsg,
                    'jazoest': jazoest or '25455',
                    'code': otp_code
                }
                
                json_headers = {
                    "User-Agent": ugenX(),
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-FB-Connection-Type": "WIFI",
                    "X-FB-Request-Analytics-Tags": "client_android_version=13,client_os=Android,device=22041219PI",
                    "X-FB-Net-HNI": "40410",
                    "X-FB-SIM-HNI": "40410"
                }
                
                confirm_resp = session.post("https://www.facebook.com/confirmemail.php", data=json_payload, headers=json_headers, allow_redirects=True)
                
                cookies = session.cookies.get_dict()
                if 'c_user' in cookies:
                    print(f"{G}[✓] API confirmation successful! UID: {cookies['c_user']}{W}")
                    return True, cookies['c_user'], cookies
                
                checkpoint_resp = session.post("https://www.facebook.com/checkpoint/", data=json_payload, headers=json_headers, allow_redirects=True)
                cookies = session.cookies.get_dict()
                if 'c_user' in cookies:
                    print(f"{G}[✓] Checkpoint API confirmation successful! UID: {cookies['c_user']}{W}")
                    return True, cookies['c_user'], cookies
            
            print(f"{Y}[*] OTP submitted, waiting for final confirmation...{W}")
            time.sleep(3)
            
            final_check = session.get("https://mbasic.facebook.com/me/", allow_redirects=True)
            final_cookies = session.cookies.get_dict()
            if 'c_user' in final_cookies:
                print(f"{G}[✓] Final confirmation successful! UID: {final_cookies['c_user']}{W}")
                return True, final_cookies['c_user'], final_cookies
            
            if 'checkpoint' not in final_check.text.lower() and 'confirm' not in final_check.text.lower():
                if 'c_user' in final_cookies:
                    return True, final_cookies['c_user'], final_cookies
                    
        except Exception as e:
            print(f"{R}[!] OTP submission error: {e}{W}")
        
        time.sleep(2)
    
    return False, None, None

# ============ COMPLETE CHECKPOINT HANDLER - FULL ACCOUNT CREATION ============
def handle_security_checkpoints(session, email_address):
    """
    Handle additional security checkpoints after OTP
    Completes full account creation including skipping phone/profile/interests
    """
    max_checks = 8
    for attempt in range(max_checks):
        try:
            resp = session.get("https://mbasic.facebook.com/", allow_redirects=True)
            
            # Check if we have full access
            if 'c_user' in session.cookies.get_dict():
                uid = session.cookies.get_dict()['c_user']
                print(f"{G}[✓] Full access achieved! UID: {uid}{W}")
                return True, uid, session.cookies.get_dict()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            resp_lower = resp.text.lower()
            
            # ====== 1. CLICK OK BUTTON ON EMAIL CONFIRMATION ======
            if "you should receive your email" in resp_lower or "enter the code" in resp_lower:
                print(f"{Y}[*] Clicking OK button on email confirmation page...{W}")
                ok_button = soup.find('form')
                if ok_button:
                    action = ok_button.get('action', '')
                    if not action.startswith('http'):
                        action = 'https://mbasic.facebook.com' + action
                    
                    fields = {}
                    for inp in ok_button.find_all('input'):
                        name = inp.get('name')
                        value = inp.get('value', '')
                        if name:
                            fields[name] = value
                    
                    session.post(action, data=fields, allow_redirects=True)
                    time.sleep(2)
                    continue
            
            # ====== 2. SKIP PHONE NUMBER ======
            if "confirm your phone number" in resp_lower or "add a phone" in resp_lower or "phone number" in resp_lower:
                print(f"{Y}[*] Skipping phone number addition...{W}")
                skip_links = soup.find_all('a', href=True)
                for link in skip_links:
                    text = link.text.lower()
                    if 'skip' in text or 'not now' in text or 'later' in text:
                        skip_url = link.get('href')
                        if not skip_url.startswith('http'):
                            skip_url = 'https://mbasic.facebook.com' + skip_url
                        session.get(skip_url, allow_redirects=True)
                        time.sleep(1)
                        continue
            
            # ====== 3. PROFILE COMPLETION PAGE ======
            if "complete your profile" in resp_lower or "tell us about yourself" in resp_lower or "about you" in resp_lower:
                print(f"{Y}[*] Skipping profile completion...{W}")
                skip_btn = soup.find('a', string=re.compile(r'SKIP|LATER|NOT NOW|CONTINUE', re.I))
                if skip_btn:
                    skip_url = skip_btn.get('href')
                    if not skip_url.startswith('http'):
                        skip_url = 'https://mbasic.facebook.com' + skip_url
                    session.get(skip_url, allow_redirects=True)
                    time.sleep(1)
                    continue
            
            # ====== 4. FRIEND SUGGESTIONS PAGE ======
            if "people you may know" in resp_lower or "friend suggestions" in resp_lower or "suggestions" in resp_lower:
                print(f"{Y}[*] Skipping friend suggestions...{W}")
                next_btn = soup.find('a', string=re.compile(r'NEXT|CONTINUE|SKIP|DONE', re.I))
                if next_btn:
                    next_url = next_btn.get('href')
                    if not next_url.startswith('http'):
                        next_url = 'https://mbasic.facebook.com' + next_url
                    session.get(next_url, allow_redirects=True)
                    time.sleep(1)
                    continue
            
            # ====== 5. INTERESTS PAGE ======
            if "select your interests" in resp_lower or "interests" in resp_lower and "follow" in resp_lower:
                print(f"{Y}[*] Skipping interests selection...{W}")
                skip_link = soup.find('a', href=re.compile(r'.*skip.*', re.I))
                if skip_link:
                    skip_url = skip_link.get('href')
                    if not skip_url.startswith('http'):
                        skip_url = 'https://mbasic.facebook.com' + skip_url
                    session.get(skip_url, allow_redirects=True)
                    time.sleep(1)
                    continue
            
            # ====== 6. WELCOME/GET STARTED PAGE ======
            if "welcome" in resp_lower or "get started" in resp_lower:
                print(f"{Y}[*] Clicking Get Started...{W}")
                start_btn = soup.find('a', string=re.compile(r'GET STARTED|CONTINUE|NEXT', re.I))
                if start_btn:
                    start_url = start_btn.get('href')
                    if not start_url.startswith('http'):
                        start_url = 'https://mbasic.facebook.com' + start_url
                    session.get(start_url, allow_redirects=True)
                    time.sleep(1)
                    continue
            
            time.sleep(2)
            
        except Exception as e:
            print(f"{R}[!] Security checkpoint error: {e}{W}")
        
        time.sleep(1)
    
    # Final check
    if 'c_user' in session.cookies.get_dict():
        uid = session.cookies.get_dict()['c_user']
        return True, uid, session.cookies.get_dict()
    
    return False, None, None

def upload_profile_picture(session, uid):
    """
    Upload random profile picture to Facebook account
    """
    try:
        print(f"{Y}[*] Uploading profile picture for UID: {uid}{W}")
        
        # Get random profile picture from randomuser.me API
        gender = random.choice(['male', 'female'])
        img_url = f"https://randomuser.me/api/portraits/{gender}/{random.randint(1, 99)}.jpg"
        
        try:
            img_data = requests.get(img_url, timeout=10).content
        except:
            # Fallback - use a default image
            img_url = "https://randomuser.me/api/portraits/women/1.jpg"
            img_data = requests.get(img_url, timeout=10).content
        
        temp_path = f"temp_pfp_{uid}.jpg"
        with open(temp_path, 'wb') as f:
            f.write(img_data)
        
        # Go to profile page
        profile_url = f"https://mbasic.facebook.com/{uid}/profile.php"
        resp = session.get(profile_url)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Find change photo link
        change_photo = None
        for a in soup.find_all('a', href=True):
            href = a.get('href', '')
            if 'profile_pic' in href or 'change_photo' in href or 'photo' in href and 'edit' in href:
                change_photo = a
                break
        
        if change_photo:
            photo_url = change_photo.get('href')
            if not photo_url.startswith('http'):
                photo_url = 'https://mbasic.facebook.com' + photo_url
            
            # Get upload form
            upload_resp = session.get(photo_url)
            upload_soup = BeautifulSoup(upload_resp.text, 'html.parser')
            
            upload_form = upload_soup.find('form', enctype='multipart/form-data')
            if upload_form:
                action = upload_form.get('action', '')
                if not action.startswith('http'):
                    action = 'https://mbasic.facebook.com' + action
                
                with open(temp_path, 'rb') as f:
                    files = {'photo': (f'profile_{uid}.jpg', f, 'image/jpeg')}
                    upload_result = session.post(action, files=files, allow_redirects=True)
                
                print(f"{G}[✓] Profile picture uploaded successfully!{W}")
                
                # Cleanup
                os.remove(temp_path)
                return True
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False
        
    except Exception as e:
        print(f"{R}[!] Profile picture upload failed: {e}{W}")
        try:
            if os.path.exists(f"temp_pfp_{uid}.jpg"):
                os.remove(f"temp_pfp_{uid}.jpg")
        except:
            pass
        return False

def complete_account_creation(session, email_address, uid):
    """Complete all steps for full account creation with profile picture"""
    
    print(f"{Y}[*] Completing account creation for {email_address}...{W}")
    
    # Step 1: Handle all security checkpoints
    success, final_uid, final_cookies = handle_security_checkpoints(session, email_address)
    
    if not success or not final_uid:
        print(f"{R}[!] Failed to complete security checkpoints{W}")
        return False, None, None
    
    # Step 2: Upload profile picture
    upload_profile_picture(session, final_uid)
    
    # Step 3: Final verification
    final_resp = session.get("https://mbasic.facebook.com/me/", allow_redirects=True)
    final_cookies = session.cookies.get_dict()
    
    if 'c_user' in final_cookies:
        print(f"{G}[✓] COMPLETE ACCOUNT CREATED SUCCESSFULLY! UID: {final_cookies['c_user']}{W}")
        return True, final_cookies['c_user'], final_cookies
    
    return False, None, None

def confirm_account_with_auto_otp(session, email_address, max_retries=3):
    """Complete account confirmation with full checkpoint handling and profile picture"""
    for attempt in range(max_retries):
        print(f"{Y}[*] Attempt {attempt+1}/{max_retries} - Full checkpoint handling...{W}")
        
        # Step 1: Get OTP from email
        otp_code = fetch_otp_from_yandex(email_address, timeout=180, mark_read=True)
        if otp_code:
            print(f"{G}[✓] OTP CODE FOUND: {otp_code}{W}")
            
            # Step 2: Submit OTP
            success, uid, cookies_dict = submit_otp_to_facebook(session, otp_code)
            
            if success and uid:
                # Step 3: Complete full account creation (checkpoints + profile picture)
                full_success, final_uid, final_cookies = complete_account_creation(session, email_address, uid)
                
                if full_success and final_uid:
                    mark_emails_as_read(email_address)
                    return True, final_uid, final_cookies, otp_code
            
            # If OTP submit failed but we have the code, try with new session
            mark_emails_as_read(email_address)
        
        # Request resend if no OTP
        try:
            current_page = session.get("https://mbasic.facebook.com/", allow_redirects=True)
            if request_resend_code(session, current_page.text):
                print(f"{G}[✓] Resend requested, waiting 60 seconds...{W}")
                otp_code = fetch_otp_from_yandex(email_address, timeout=60, mark_read=True)
                if otp_code:
                    success, uid, cookies_dict = submit_otp_to_facebook(session, otp_code)
                    if success:
                        full_success, final_uid, final_cookies = complete_account_creation(session, email_address, uid)
                        if full_success:
                            return True, final_uid, final_cookies, otp_code
        except:
            pass
        
        print(f"{Y}[!] Retry {attempt+1}/{max_retries} failed{W}")
        time.sleep(2)
    
    return False, None, None, None

# File storage functions
def save_to_file(data: str, file_path: str):
    full_path = file_path
    os.makedirs(os.path.dirname(full_path) or ".", exist_ok=True)
    with open(full_path, "a", encoding="utf-8") as f:
        f.write(data + "\n")

def install_dependencies():
    try:
        import pyotp
    except ImportError:
        logging.warning("pyotp not installed. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyotp"])
        except Exception as e:
            logging.error(f"Failed to install pyotp: {e}")
            print(f"{R}Failed to install pyotp: {e}{W}")
            sys.exit(1)

def clear_screen():
    os.system('cls' if platform.system().lower() == 'windows' else 'clear')

# Device information
try:
    android_version = subprocess.check_output('getprop ro.build.version.release', shell=True).decode('utf-8').strip()
    model = subprocess.check_output('getprop ro.product.model', shell=True).decode('utf-8').strip()
    build = subprocess.check_output('getprop ro.build.id', shell=True).decode('utf-8').strip()
    fbmf = subprocess.check_output('getprop ro.product.manufacturer', shell=True).decode('utf-8').strip()
    fbbd = subprocess.check_output('getprop ro.product.brand', shell=True).decode('utf-8').strip()
    fbca = subprocess.check_output('getprop ro.product.cpu.abilist', shell=True).decode('utf-8').replace(',', ':').strip()
    fbdm = f"{{density=2.25,height={subprocess.check_output('getprop ro.hwui.text_large_cache_height', shell=True).decode('utf-8').strip()},width={subprocess.check_output('getprop ro.hwui.text_large_cache_width', shell=True).decode('utf-8').strip()}}}"
    try:
        fbcr = subprocess.check_output('getprop gsm.operator.alpha', shell=True).decode('utf-8').split(',')[0].strip()
    except:
        fbcr = 'ZONG'
except:
    android_version, model, build, fbmf, fbbd, fbca, fbdm, fbcr = '10', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'arm64-v8a', '{density=2.25,height=720,width=1280}', 'ZONG'

device = {
    'android_version': android_version,
    'model': model,
    'build': build,
    'fblc': 'en_US',
    'fbmf': fbmf,
    'fbbd': fbbd,
    'fbdv': model,
    'fbsv': android_version,
    'fbca': fbca,
    'fbdm': fbdm
}

def ugenX():
    ualist = [ua.random for _ in range(50)]
    return str(random.choice(ualist))

# Generate User-Agents list
ugen=[]
for xd in range(10000):
        rr = random.randint
        build_b = random.choice(["001","002","003","011","012","014","015","020","021","022","023","024"])
        bl_typ = random.choice(["TKQ1","SKQ1","TP1A","RKQ1","SP1A","RP1A","PPR1","QP1A"])
        oppo = random.choice(["CPH2461","CPH2451","PCGM00","PBBM00","PFZM10","PGGM10","PECT30","PCHM10","PEAT00","PEYM00","PESM10","PFGM00"])
        infinix = random.choice(["Infinix X669C","Infinix X6823","Infinix X676C","Infinix X683","Infinix X689C","Infinix X6811","Infinix X612B","Infinix X6810","Infinix X665E"])
        redmi = random.choice(["2211133G","M2004J19C","22041219I","22101316UG","2209116AG","M2010J19SY","M2012K11C","Redmi Note 7","Redmi Note 8","Redmi Note 5"])
        um2 = f"Mozilla/5.0 (Linux; Android {str(rr(6,12))}; {oppo} Build/{bl_typ}.{str(rr(120000,220000))}.{build_b}; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/{str(rr(80,114))}.0.{str(rr(4200,5400))}.{str(rr(70,150))} Mobile Safari/537.36"
        um1 = f"Mozilla/5.0 (Linux; Android {str(rr(6,12))}; {redmi} Build/{bl_typ}.{str(rr(120000,220000))}.{build_b}; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/{str(rr(80,114))}.0.{str(rr(4200,5400))}.{str(rr(70,150))} Mobile Safari/537.36"
        um3 = f"Mozilla/5.0 (Linux; Android {str(rr(6,12))}; {infinix} Build/{bl_typ}.{str(rr(120000,220000))}.{build_b}; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/{str(rr(80,114))}.0.{str(rr(4200,5400))}.{str(rr(70,150))} Mobile Safari/537.36"
        um4 = f"Mozilla/5.0 (Linux; Android {str(rr(6,12))}; {infinix}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{str(rr(100,114))}.0.{str(rr(4900,5700))}.{str(rr(70,150))} Mobile Safari/537.36"
        ugen.append(um2)
        ugen.append(um3)
        ugen.append(um1)
        ugen.append(um4)
for xhd in range(1000):
        a = random.choice(['de-at','in-id','ms-my','uk-ua','en-us','en-gb','id-id','de-de','ru-ru','en-sg','fr-fr','fa-ir','ja-jp','pt-br','cs-cz','zh-hk','zh-cn','vi-vn','en-ph','en-in','tr-tr','en-au','th-th','hi-in','zh-tw','my-zg','en-nz','en-ca','es-mx','ko-kr','el-gr','en-ez','ar-ae','fr-ch','nl-nl','gu-in'])
        b = random.choice(['A','B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z'])
        c = random.choice(['A','B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z'])
        b2 = random.choice(['A','B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z'])
        c2 = random.choice(['A','B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z'])
        d = f"Mozilla/5.0 (Linux; U; Android {str(random.randint(6,14))}; {a}; OPPO {b}{str(random.randint(10,99))}{c} Build/{b2}{str(random.randint(1,999))}{c2}) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/{str(random.randint(75,117))}.0.{str(random.randint(2500,5900))}.{str(random.randint(80,200))} Mobile Safari/537.36 HeyTapBrowser/{str(random.randint(6,47))}.{str(random.randint(7,8))}.{str(random.randint(2,40))}.{str(random.randint(1,9))}"
        ugen.append(d)

# Name and password generation
first_names_male = [
'Juan', 'Jose', 'Miguel', 'Gabriel', 'Rafael', 'Antonio', 'Carlos', 'Luis',
'Marco', 'Paolo', 'Angelo', 'Joshua', 'Christian', 'Mark', 'John', 'James',
'Daniel', 'David', 'Michael', 'Jayson', 'Kenneth', 'Ryan', 'Kevin', 'Neil',
'Jerome', 'Renzo', 'Carlo', 'Andres', 'Felipe', 'Diego', 'Mateo', 'Lucas',
]

first_names_female = [
'Maria', 'Ana', 'Sofia', 'Isabella', 'Gabriela', 'Valentina', 'Camila',
'Angelica', 'Nicole', 'Michelle', 'Christine', 'Sarah', 'Jessica',
'Andrea', 'Patricia', 'Jennifer', 'Karen', 'Ashley', 'Jasmine', 'Princess',
]

surnames = [
'Reyes', 'Santos', 'Cruz', 'Bautista', 'Garcia', 'Flores', 'Gonzales',
'Martinez', 'Ramos', 'Mendoza', 'Rivera', 'Torres', 'Fernandez', 'Lopez',
'Castillo', 'Aquino', 'Villanueva', 'Santiago', 'Dela Cruz', 'Perez',
]

rpw_first_names = [
'Luna', 'Aurora', 'Mystic', 'Crystal', 'Sapphire', 'Scarlet', 'Violet',
'Rose', 'Athena', 'Venus', 'Nova', 'Stella', 'Serena', 'Raven', 'Jade',
]

rpw_surnames = [
'Shadow', 'Dark', 'Light', 'Star', 'Moon', 'Sun', 'Sky', 'Night', 'Dawn',
'Storm', 'Frost', 'Fire', 'Stanley', 'Nero', 'Clifford',
]

def get_bd_name():
    first = random.choice(first_names_male + first_names_female)
    last = random.choice(surnames)
    return first, last

def get_rpw_name():
    return random.choice(rpw_first_names), random.choice(rpw_surnames)

def get_pass():
    name_part = ''.join(random.choices(string.ascii_letters, k=random.randint(5, 7)))
    name_part = name_part.capitalize() if random.choice([True, False]) else name_part.lower()
    symbol_part = ''.join(random.choices('!@#$%^&*()_+=', k=random.randint(2, 3)))
    digit_part = ''.join(random.choices(string.digits, k=random.randint(2, 4)))
    end_part = ''.join(random.choices(string.ascii_letters, k=random.randint(2, 4)))
    optional_upper = ''.join(random.choices(string.ascii_uppercase, k=random.randint(1, 2)))
    parts = [name_part, symbol_part, digit_part, end_part, optional_upper]
    random.shuffle(parts)
    return ''.join(parts)

def extractor(data):
    soup = BeautifulSoup(data, "html.parser")
    data = {}
    for inputs in soup.find_all("input"):
        name = inputs.get("name")
        value = inputs.get("value")
        if name:
            data[name] = value
    return data

def banner():
    clear_screen()
    print(f"""{G}
 █████╗ ██╗   ██╗████████╗ ██████╗       {R}███████╗██████╗ 
██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗      {R}██╔════╝██╔══██╗
███████║██║   ██║   ██║   ██║   ██║      {R}█████╗  ██████╔╝
██╔══██║██║   ██║   ██║   ██║   ██║      {R}██╔══╝  ██╔══██╗
██║  ██║╚██████╔╝   ██║   ╚██████╔╝      {R}██║     ██████╔╝
╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝       {R}╚═╝     ╚═════╝
            {W}A U T O  –  F B
{W}─────────────────────────────────────────────{W}
{W}[{G}•{W}]{G} PROXY SUPPORT    {W}:{G} ENABLED
{W}[{G}•{W}]{G} PROFILE PICTURE  {W}:{G} AUTO UPLOAD
{W}[{G}•{W}]{G} FULL CHECKPOINT  {W}:{G} ENABLED
{W}─────────────────────────────────────────────{W}""")

def linex():
    print(f"{W}─────────────────────────────────────────────{W}")

oks = []
cps = []

def generate_yandex_alias(account_name):
    import time as _time
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', account_name.lower())
    timestamp = int(_time.time()) % 10000
    random_suffix = random.randint(100, 999)
    alias = f"{clean_name[:20]}{timestamp}{random_suffix}"
    return f"{YANDEX_EMAIL.split('@')[0]}+{alias}@yandex.com"

def createfb_method_1():
    global oks, cps
    banner()
    
    # Load proxies at start
    get_working_proxies()
    
    print(f"{W}[{G}1{W}]{G} FILIPINO NAMES")
    print(f"{W}[{G}2{W}]{G} RPW NAMES")
    linex()
    name_choice = input(f"{W}[{G}•{W}]{G} CHOISE {W}:{G} ")
    linex()
    num = int(input(f"{W}[{G}•{W}]{G} HOW MANY ACCOUNT {W}:{G} "))
    linex()
    print(f"{W}[{G}1{W}]{G} AUTO PASSWORD")
    print(f"{W}[{G}2{W}]{G} CUSTOM PASSWORD")
    linex()
    password_choice = input(f"{W}[{G}•{W}]{G} CHOISE {W}:{G} ")
    pww = get_pass() if password_choice == '1' else input(f"{W}[{G}•{W}]{G} ENTER PASSWORD {W}:{G} ")
    linex()
    show_details = input(f"{W}[{G}•{W}]{G} Show All Details y{R}/{G}n {W}:{G} ").lower()
    banner()
    print(f"{W}[{G}•{W}]{G} ACCOUNT CREATING STARTED")
    print(f'{W}[{G}•{W}]{G} TOTAL ID {W}: {R}{num}{W}')
    print(f"{W}[{G}•{W}]{G} Use {R}PROXIES {G}from proxies.txt{W}")
    linex()

    import threading
    from concurrent.futures import ThreadPoolExecutor

    lock = threading.Lock()
    done = [0]

    def _create_one():
        while True:
            with lock:
                if done[0] >= num:
                    return
            try:
                ses = create_session_with_proxy()
                response = ses.get("https://x.facebook.com/reg", timeout=15)
                form = extractor(response.text)

                if not form.get("lsd") and not form.get("fb_dtsg"):
                    time.sleep(3)
                    continue

                firstname, lastname = get_rpw_name() if name_choice == '2' else get_bd_name()
                account_name = f"{firstname}{lastname}{random.randint(10, 999)}"
                email = generate_yandex_alias(account_name)

                payload = {
                    'ccp': "2",
                    'reg_instance': form.get("reg_instance", ""),
                    'submission_request': "true",
                    'reg_impression_id': form.get("reg_impression_id", ""),
                    'ns': "1",
                    'logger_id': form.get("logger_id", ""),
                    'firstname': firstname,
                    'lastname': lastname,
                    'birthday_day': str(random.randint(15, 25)),
                    'birthday_month': str(random.randint(5, 10)),
                    'birthday_year': str(random.randint(1985, 1995)),
                    'reg_email__': email,
                    'sex': "1",
                    'encpass': f'#PWD_BROWSER:0:{int(time.time())}:{pww}',
                    'submit': "Sign Up",
                    'fb_dtsg': form.get("fb_dtsg", ""),
                    'jazoest': form.get("jazoest", ""),
                    'lsd': form.get("lsd", "")
                }

                merged_headers = {
                    "Host": "m.facebook.com",
                    "Connection": "keep-alive",
                    "User-Agent": ugenX(),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept-Language": "en-US,en;q=0.9",
                    'referer': 'https://mbasic.facebook.com/reg/',
                    'sec-ch-ua-mobile': '?1',
                    'sec-ch-ua-platform': 'Android',
                    'sec-fetch-dest': 'document',
                    'sec-fetch-mode': 'navigate',
                    'sec-fetch-site': 'same-origin',
                    'upgrade-insecure-requests': '1',
                }

                reg_submit = ses.post("https://www.facebook.com/reg/submit/", data=payload, headers=merged_headers, timeout=20)
                login_coki = ses.cookies.get_dict()
                response_text = reg_submit.text

                if "checkpoint" in response_text.lower() or "confirm" in response_text.lower() or "code" in response_text.lower():
                    print(f"{Y}[!] Verification required for {email}, polling for OTP...{W}")
                    success, uid, cookies_dict, otp_code = confirm_account_with_auto_otp(ses, email)
                    if success and uid:
                        coki = ";".join([f"{k}={v}" for k, v in cookies_dict.items()])
                        with lock:
                            if done[0] >= num:
                                return
                            done[0] += 1
                            current = done[0]
                            oks.append(uid)
                            if show_details == 'y':
                                print(f"\n{W}[{G}•{W}] Name   : {G}{firstname} {lastname}{W}")
                                print(f"{W}[{G}•{W}] Email  : {G}{email}{W}")
                                print(f"{W}[{G}•{W}] OTP    : {G}{otp_code}{W}")
                                print(f"{W}[{G}•{W}] UID    : {G}{uid}{W}")
                                print(f"{W}[{G}•{W}] PASS   : {G}{pww}{W}")
                                print(f"{W}[{G}•{W}] COOKIES: {G}{coki}{W}")
                                print(f"{W}─────────────────────────────────────────────{W}")
                            else:
                                print(f"\n{G}CYBER-X{W}-{G}[OK] {current}/{num} | {uid} | {pww} | OTP:{otp_code}")
                            try:
                                with open('accounts.txt', 'a') as f:
                                    f.write(f"{uid}|{pww}|{email}|{coki}|OTP:{otp_code}\n")
                            except Exception:
                                pass
                    else:
                        with lock:
                            cps.append(email)
                        print(f"{R}[!] Verification failed for {email}{W}")
                
                elif "c_user" in login_coki:
                    uid = login_coki["c_user"]
                    coki = ";".join([f"{k}={v}" for k, v in login_coki.items()])
                    
                    time.sleep(3)
                    check_resp = ses.get("https://mbasic.facebook.com/me/", allow_redirects=True)
                    if "checkpoint" in check_resp.text.lower() or "confirm" in check_resp.text.lower():
                        print(f"{Y}[!] Post-creation verification needed, fetching OTP...{W}")
                        success, uid2, cookies_dict, otp_code = confirm_account_with_auto_otp(ses, email)
                        if success and uid2:
                            uid = uid2
                            coki = ";".join([f"{k}={v}" for k, v in cookies_dict.items()])
                    
                    with lock:
                        if done[0] >= num:
                            return
                        done[0] += 1
                        current = done[0]
                        oks.append(uid)
                        if show_details == 'y':
                            print(f"\n{W}[{G}•{W}] Name   : {G}{firstname} {lastname}{W}")
                            print(f"{W}[{G}•{W}] Email  : {G}{email}{W}")
                            if 'otp_code' in locals() and otp_code:
                                print(f"{W}[{G}•{W}] OTP    : {G}{otp_code}{W}")
                            print(f"{W}[{G}•{W}] UID    : {G}{uid}{W}")
                            print(f"{W}[{G}•{W}] PASS   : {G}{pww}{W}")
                            print(f"{W}[{G}•{W}] COOKIES: {G}{coki}{W}")
                            print(f"{W}─────────────────────────────────────────────{W}")
                        else:
                            otp_display = f" | OTP:{otp_code}" if 'otp_code' in locals() and otp_code else ""
                            print(f"\n{G}CYBER-X{W}-{G}[OK] {current}/{num} | {uid} | {pww}{otp_display}")
                        try:
                            with open('accounts.txt', 'a') as f:
                                otp_part = f"|OTP:{otp_code}" if 'otp_code' in locals() and otp_code else ""
                                f.write(f"{uid}|{pww}|{email}|{coki}{otp_part}\n")
                        except Exception:
                            pass
                else:
                    pass
                    
            except Exception as e:
                time.sleep(2)

    WORKERS = 5
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(_create_one) for _ in range(WORKERS)]
        for f in futures:
            f.result()
    
    print(' ')
    linex()
    print(f'{W}[{G}•{W}]{G} The process has completed')
    linex()
    print(f'{W}[{G}•{W}]{G} Total OK {W}: {G}{len(oks)}')
    print(f'{W}[{R}•{W}]{G} Total CP {W}: {R}{len(cps)}')
    linex()
    input(f'{W}[{G}•{W}]{G} Press Enter to go back to menu... {W}')

def register_account_for_bot(domain_choice="yandex", name_option="1", gender_option="3", custom_pass=None, max_retries=5):
    """Single account creation for Telegram bot - COMPLETE with proxy support"""
    import time as _time
    
    for attempt in range(max_retries):
        try:
            ses = create_session_with_proxy()
            response = ses.get("https://x.facebook.com/reg", timeout=15)
            form = extractor(response.text)

            if not form.get("lsd") and not form.get("fb_dtsg"):
                time.sleep(3)
                continue

            if name_option == "2":
                firstname, lastname = get_rpw_name()
            else:
                if gender_option == "1":
                    firstname = random.choice(first_names_male)
                elif gender_option == "2":
                    firstname = random.choice(first_names_female)
                else:
                    firstname = random.choice(first_names_male + first_names_female)
                lastname = random.choice(surnames)

            if gender_option == "1":
                fb_sex = "2"
            elif gender_option == "2":
                fb_sex = "1"
            else:
                fb_sex = random.choice(["1", "2"])

            account_name = f"{firstname}{lastname}{int(_time.time())}{random.randint(100, 999)}"
            email = generate_yandex_alias(account_name)
            pww = custom_pass if custom_pass else get_pass()

            payload = {
                'ccp': "2",
                'reg_instance': form.get("reg_instance", ""),
                'submission_request': "true",
                'reg_impression_id': form.get("reg_impression_id", ""),
                'ns': "1",
                'logger_id': form.get("logger_id", ""),
                'firstname': firstname,
                'lastname': lastname,
                'birthday_day': str(random.randint(15, 25)),
                'birthday_month': str(random.randint(5, 10)),
                'birthday_year': str(random.randint(1985, 1995)),
                'reg_email__': email,
                'sex': fb_sex,
                'encpass': f'#PWD_BROWSER:0:{int(_time.time())}:{pww}',
                'submit': "Sign Up",
                'fb_dtsg': form.get("fb_dtsg", ""),
                'jazoest': form.get("jazoest", ""),
                'lsd': form.get("lsd", ""),
            }

            headers = {
                "Host": "m.facebook.com",
                "Connection": "keep-alive",
                "User-Agent": ugenX(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "en-US,en;q=0.9",
                'referer': 'https://mbasic.facebook.com/reg/',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': 'Android',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'same-origin',
                'upgrade-insecure-requests': '1',
            }

            reg_submit = ses.post("https://www.facebook.com/reg/submit/", data=payload, headers=headers, timeout=20)
            login_coki = ses.cookies.get_dict()
            response_text = reg_submit.text
            response_lower = response_text.lower()

            if "c_user" in login_coki:
                time.sleep(3)
                check_resp = ses.get("https://mbasic.facebook.com/me/", allow_redirects=True)
                if "checkpoint" in check_resp.text.lower():
                    success, uid, cookies_dict, otp_code = confirm_account_with_auto_otp(ses, email)
                    if success and uid:
                        cookie_str = get_cookie_string(ses)
                        return {
                            "name": f"{firstname} {lastname}",
                            "email": email,
                            "password": pww,
                            "uid": uid,
                            "cookies": cookie_str,
                            "session": ses,
                            "otp_fetched": True,
                            "otp_code": otp_code if otp_code else "FETCHED"
                        }
                    else:
                        continue
                else:
                    cookie_str = get_cookie_string(ses)
                    # Complete account creation even without checkpoint
                    full_success, final_uid, final_cookies = complete_account_creation(ses, email, login_coki["c_user"])
                    if full_success:
                        return {
                            "name": f"{firstname} {lastname}",
                            "email": email,
                            "password": pww,
                            "uid": final_uid,
                            "cookies": get_cookie_string(ses),
                            "session": ses,
                            "otp_fetched": True,
                            "otp_code": "COMPLETED"
                        }
            
            otp_keywords = ["checkpoint", "confirm", "code", "verification"]
            needs_otp = any(kw in response_lower for kw in otp_keywords)
            
            if needs_otp:
                success, uid, cookies_dict, otp_code = confirm_account_with_auto_otp(ses, email)
                if success and uid:
                    cookie_str = get_cookie_string(ses)
                    return {
                        "name": f"{firstname} {lastname}",
                        "email": email,
                        "password": pww,
                        "uid": uid,
                        "cookies": cookie_str,
                        "session": ses,
                        "otp_fetched": True,
                        "otp_code": otp_code if otp_code else "FETCHED"
                    }
                else:
                    continue

        except Exception as e:
            print(f"[DEBUG] Registration error: {e}")
        
        time.sleep(2)
    
    return None

def get_cookie_string(session):
    cookies = session.cookies.get_dict()
    return ";".join([f"{k}={v}" for k, v in cookies.items()])

def method():
    while True:
        banner()
        print(f"{W}[{G}1{W}]{G} Auto Create Fb ")
        linex()
        choice = input(f"{W}[{G}•{W}]{G} CHOISE {W}:{G} ").strip()
        if choice == '1':
            createfb_method_1()
        else:
            print(f"{R}Invalid choice!{W}")
            input(f"{W}[{G}•{W}]{G} Press Enter to continue ")

if __name__ == "__main__":
    sys.stdout.write('\x1b]2; CYBER-X\x07')
    install_dependencies()
    method()
