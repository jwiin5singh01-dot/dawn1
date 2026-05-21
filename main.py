#DECODED BY NETZ - MODIFIED WITH YANDEX EMAIL ONLY
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
YANDEX_EMAIL = "jerryxd@yandex.com"
YANDEX_APP_PASSWORD = "kshxbeousfpcbxgq"

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
        base_email = YANDEX_EMAIL.split('@')[0]
        
        print(f"{Y}[*] Looking for OTP for email: {email_address}{W}")
        
        while time.time() - start_time < timeout:
            status, messages = imap.search(None, f'HEADER Delivered-To "{email_address}"')
            
            if status != "OK" or not messages[0]:
                status, messages = imap.search(None, '(UNSEEN FROM "facebookmail.com")')
            
            if status != "OK" or not messages[0]:
                status, messages = imap.search(None, f'TEXT "{base_email}"')
            
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

def confirm_account_with_auto_otp(session, email_address, max_retries=3):
    for attempt in range(max_retries):
        print(f"{Y}[*] Attempt {attempt+1}/{max_retries} - Fetching OTP from email (3 min wait)...{W}")
        otp_code = fetch_otp_from_yandex(email_address, timeout=180, mark_read=True)
        if otp_code:
            print(f"{G}[✓] OTP CODE FOUND: {otp_code}{W}")
            success, uid, cookies_dict = submit_otp_to_facebook(session, otp_code)
            mark_emails_as_read(email_address)
            return success, uid, cookies_dict, otp_code
        print(f"{Y}[*] No OTP yet, trying to request resend...{W}")
        current_page = session.get("https://mbasic.facebook.com/", allow_redirects=True)
        if request_resend_code(session, current_page.text):
            print(f"{G}[✓] Resend requested, waiting 60 seconds for OTP...{W}")
            otp_code = fetch_otp_from_yandex(email_address, timeout=60, mark_read=True)
            if otp_code:
                print(f"{G}[✓] OTP CODE FOUND after resend: {otp_code}{W}")
                success, uid, cookies_dict = submit_otp_to_facebook(session, otp_code)
                mark_emails_as_read(email_address)
                return success, uid, cookies_dict, otp_code
        if attempt == max_retries - 1:
            print(f"{Y}[!] Auto OTP failed. Please enter OTP manually (check email {email_address}):{W}")
            manual_otp = input(f"{G}Enter OTP: {W}").strip()
            if manual_otp and len(manual_otp) >= 5:
                success, uid, cookies_dict = submit_otp_to_facebook(session, manual_otp)
                mark_emails_as_read(email_address)
                return success, uid, cookies_dict, manual_otp
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
for xd in range(1000):
   rr = random.randint; rc = random.choice
   aZ = str(rc(['A','B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z']))
   lonte = f"{str(rc(aZ))}{str(rc(aZ))}{str(rc(aZ))}{str(rr(11,99))}{str(rc(aZ))}"
   build_nokiax = ['JDQ39','JZO54K']
   oppo = ["CPH1869", "CPH1929","CPH2107", "CPH2238", "CPH2389","CPH2401", "CPH2407", "CPH2413", "CPH2415", "CPH2417", "CPH2419", "CPH2455", "CPH2459", "CPH2461", "CPH2471", "CPH2473", "CPH2477", "CPH8893", "CPH2321", "CPH2341", "CPH2373", "CPH2083", "CPH2071", "CPH2077", "CPH2185", "CPH2179", "CPH2269", "CPH2421", "CPH2349", "CPH2271", "CPH1923", "CPH1925", "CPH1837", "CPH2015", "CPH2073", "CPH2081", "CPH2029", "CPH2031", "CPH2137", "CPH1605", "CPH1803", "CPH1853", "CPH1805", "CPH1809", "CPH1851", "CPH1931", "CPH1959", "CPH1933", "CPH1935", "CPH1943", "CPH2061", "CPH2069", "CPH2127", "CPH2131", "CPH2139", "CPH2135", "CPH2239", "CPH2195", "CPH2273", "CPH2325", "CPH2309", "CPH1701", "CPH2387", "CPH1909", "CPH1920", "CPH1912", "CPH1901", "CPH1903", "CPH1905", "CPH1717", "CPH1801", "CPH2067", "CPH2099", "CPH2161", "CPH2219", "CPH2197", "CPH2263", "CPH2375", "CPH2339", "CPH1715", "CPH2385", "CPH1729", "CPH1827", "CPH1938", "CPH1937", "CPH1939", "CPH1941", "CPH2001", "CPH2021", "CPH2059", "CPH2121", "CPH2123", "CPH2203", "CPH2333", "CPH2365", "CPH1913", "CPH1911", "CPH1915", "CPH1969", "CPH2209", "CPH1987", "CPH2095", "CPH2119", "CPH2285", "CPH2213", "CPH2223", "CPH2363", "CPH1609", "CPH1613", "CPH1723", "CPH1727", "CPH1725", "CPH1819", "CPH1821", "CPH1825", "CPH1881", "CPH1823", "CPH1871", "CPH1875", "CPH2023", "CPH2005", "CPH2025", "CPH2207", "CPH2173", "CPH2307", "CPH2305", "CPH2337", "CPH1955", "CPH1707", "CPH1719", "CPH1721", "CPH1835", "CPH1831", "CPH1833", "CPH1879", "CPH1893", "CPH1877", "CPH1607", "CPH1611", "CPH1917", "CPH1919", "CPH1907", "CPH1989", "CPH1945", "CPH1951", "CPH2043", "CPH2035", "CPH2037", "CPH2036", "CPH2009", "CPH2013", "CPH2113", "CPH2091", "CPH2125", "CPH2109", "CPH2089", "CPH2065", "CPH2159", "CPH2145", "CPH2205", "CPH2201", "CPH2199", "CPH2217", "CPH1921", "CPH2211", "CPH2235", "CPH2251", "CPH2249", "CPH2247", "CPH2237", "CPH2371", "CPH2293", "CPH2353", "CPH2343", "CPH2359", "CPH2357", "CPH2457", "CPH1983", "CPH1979"]
   redmi = ["2201116SI", "M2012K11AI", "22011119TI", "21091116UI", "M2102K1AC", "M2012K11I", "22041219I", "22041216I", "2203121C", "2106118C", "2201123G", "2203129G", "2201122G", "2201122C", "2206122SC", "22081212C", "2112123AG", "2112123AC", "2109119BC", "M2002J9G", "M2007J1SC", "M2007J17I", "M2102J2SC", "M2007J3SY", "M2007J17G", "M2007J3SG", "M2011K2G", "M2101K9AG ", "M2101K9R", "2109119DG", "M2101K9G", "2109119DI", "M2012K11G", "M2102K1G", "21081111RG", "2107113SG", "21051182G", "M2105K81AC", "M2105K81C", "21061119DG", "21121119SG", "22011119UY", "21061119AG", "21061119AL", "22041219NY", "22041219G", "21061119BI", "220233L2G", "220233L2I", "220333QNY", "220333QAG", "M2004J7AC", "M2004J7BC", "M2004J19C", "M2006C3MII", "M2010J19SI", "M2006C3LG", "M2006C3LVG", "M2006C3MG", "M2006C3MT", "M2006C3MNG", "M2006C3LII", "M2010J19SL", "M2010J19SG", "M2010J19SY", "M2012K11AC", "M2012K10C", "M2012K11C", "22021211RC"]
   realme =  ["RMX3516", "RMX3371", "RMX3461", "RMX3286", "RMX3561", "RMX3388", "RMX3311", "RMX3142", "RMX2071", "RMX1805", "RMX1809", "RMX1801", "RMX1807", "RMX1803", "RMX1825", "RMX1821", "RMX1822", "RMX1833", "RMX1851", "RMX1853", "RMX1827", "RMX1911", "RMX1919", "RMX1927", "RMX1971", "RMX1973", "RMX2030", "RMX2032", "RMX1925", "RMX1929", "RMX2001", "RMX2061", "RMX2063", "RMX2040", "RMX2042", "RMX2002", "RMX2151", "RMX2163", "RMX2155", "RMX2170", "RMX2103", "RMX3085", "RMX3241", "RMX3081", "RMX3151", "RMX3381", "RMX3521", "RMX3474", "RMX3471", "RMX3472", "RMX3392", "RMX3393", "RMX3491", "RMX1811", "RMX2185", "RMX3231", "RMX2189", "RMX2180", "RMX2195", "RMX2101", "RMX1941", "RMX1945", "RMX3063", "RMX3061", "RMX3201", "RMX3203", "RMX3261", "RMX3263", "RMX3193", "RMX3191", "RMX3195", "RMX3197", "RMX3265", "RMX3268", "RMX3269","RMX2027", "RMX2020","RMX2021", "RMX3581", "RMX3501", "RMX3503", "RMX3511", "RMX3310", "RMX3312", "RMX3551", "RMX3301", "RMX3300", "RMX2202", "RMX3363", "RMX3360", "RMX3366", "RMX3361", "RMX3031", "RMX3370", "RMX3357", "RMX3560", "RMX3562", "RMX3350", "RMX2193", "RMX2161", "RMX2050", "RMX2156", "RMX3242", "RMX3171", "RMX3430", "RMX3235", "RMX3506", "RMX2117", "RMX2173", "RMX3161", "RMX2205", "RMX3462", "RMX3478", "RMX3372", "RMX3574", "RMX1831", "RMX3121", "RMX3122", "RMX3125", "RMX3043", "RMX3042", "RMX3041", "RMX3092", "RMX3093", "RMX3571", "RMX3475", "RMX2200", "RMX2201", "RMX2111", "RMX2112", "RMX1901", "RMX1903", "RMX1992", "RMX1993", "RMX1991", "RMX1931", "RMX2142", "RMX2081", "RMX2085", "RMX2083", "RMX2086", "RMX2144", "RMX2051", "RMX2025", "RMX2075", "RMX2076", "RMX2072", "RMX2052", "RMX2176", "RMX2121", "RMX3115", "RMX1921"]
   infinix = ["X676B", "X687", "X609", "X697", "X680D", "X507", "X605", "X668", "X6815B", "X624", "X655F", "X689C", "X608", "X698", "X682B", "X682C", "X688C", "X688B", "X658E", "X659B", "X689B", "X689", "X689D", "X662", "X662B", "X675", "X6812B", "X6812", "X6817B", "X6817", "X6816C", "X6816", "X6816D", "X668C", "X665B", "X665E", "X510", "X559C", "X559F", "X559", "X606", "X606C", "X606D", "X623", "X624B", "X625C", "X625D", "X625B", "X650D", "X650B", "X650", "X650C", "X655C", "X655D", "X680B", "X573", "X573B", "X622", "X693", "X695C", "X695D", "X695", "X663B", "X663", "X670", "X671", "X671B", "X672", "X6819", "X572", "X572-LTE", "X571", "X604", "X610B", "X690", "X690B", "X656", "X692", "X683", "X450", "X5010", "X501", "X401", "X626", "X626B", "X652", "X652A", "X652B", "X652C", "X660B", "X660C", "X660", "X5515", "X5515F", "X5515I", "X609B", "X5514D", "X5516B", "X5516C", "X627", "X680", "X653", "X653C", "X657", "X657B", "X657C", "X6511B", "X6511E", "X6511", "X6512", "X6823C", "X612B", "X612", "X503", "X511", "X352", "X351", "X530", "X676C", "X6821", "X6823", "X6827", "X509", "X603", "X6815", "X620B", "X620", "X687B", "X6811B", "X6810", "X6811"]
   samsung = ["E025F", "G996B", "A826S", "E135F", "G781B", "G998B", "F936U1", "G361F", "A716S", "J327AZ", "E426B", "A015F", "A015M", "A013G", "A013G", "A013M", "A013F", "A022M", "A022G", "A022F", "A025M", "S124DL", "A025U", "A025A", "A025G", "A025F", "A025AZ", "A035F", "A035M", "A035G", "A032F", "A032M", "A032F", "A037F", "A037U", "A037M", "S134DL", "A037G", "A105G", "A105M", "A105F", "A105FN", "A102U", "S102DL", "A102U1", "A107F", "A107M", "A115AZ", "A115U", "A115U1", "A115A", "A115M", "A115F", "A125F", "A127F", "A125M", "A125U", "A127M", "A135F", "A137F", "A135M", "A136U", "A136U1", "A136W", "A260F", "A260G", "A260F", "A260G", "A205GN", "A205U", "A205F", "A205G", "A205FN", "A202F", "A2070", "A207F", "A207M", "A215U", "A215U1", "A217F", "A217F", "A217M", "A225F", "A225M", "A226B", "A226B", "A226BR", "A235F", "A235M", "A300FU", "A300F", "A300H", "A310F", "A310M", "A320FL", "A320F", "A305G", "A305GT", "A305N", "A305F", "A307FN", "A307G", "A307GN", "A315G", "A315F", "A325F", "A325M", "A326U", "A326W", "A336E", "A336B", "A430F", "A405FN", "A405FM", "A3051", "A3050", "A415F", "A426U", "A426B", "A5009", "A500YZ", "A500Y", "A500W", "A500L", "A500X", "A500XZ", "A510F", "A510Y", "A520F", "A520W", "A500F", "A500FU", "A500H", "S506DL", "A505G", "A505FN", "A505U", "A505GN", "A505F", "A507FN", "A5070", "A515F", "A515U", "A515U1", "A516U", "A516V", "A516N", "A516B", "A525F", "A525M", "A526U", "A526U1", "A526B", "A526W", "A528B", "A536B", "A536U", "A536E", "A536V", "A600FN", "A600G", "A605FN", "A605G", "A605GN", "A605F", "A6050", "A606Y", "A6060", "G6200", "A700FD", "A700F", "A7000", "A700H", "A700YD", "A710F", "A710M", "A720F", "A750F", "A750FN", "A750GN", "A705FN", "A705F", "A705MN", "A707F", "A715F", "A715W", "A716U", "A716V", "A716U1", "A716B", "A725F", "A725M", "A736B", "A530F", "A810YZ", "A810F", "A810S", "A530W", "A530N", "G885F", "G885Y", "G885S", "A730F", "A805F", "G887F", "G8870", "A9000", "A920F", "A920F", "G887N", "A910F", "G8850", "A908B", "A908N", "A9080", "G313HY", "G313MY", "G313MU", "G316M", "G316ML", "G316MY", "G313HZ", "G313H", "G313HU", "G313U", "G318H", "G357FZ","G310HN", "G357FZ", "G850F", "G850M", "J337AZ", "G386T1", "G386T", "G3858", "G3858", "A226L", "C5000", "C500X", "C5010", "C5018", "C7000", "C7010", "C701F", "C7018", "C7100", "C7108", "C9000", "C900F", "C900Y", "G355H", "G355M", "G3589W", "G386W", "G386F", "G3518", "G3586V", "G5108Q", "G5108", "G3568V", "G350E", "G350", "G3509I", "G3508J", "G3502I", "G3502C", "S820L", "G360H", "G360F", "G360T", "G360M", "G361H", "E500H", "E500F", "E500M", "E5000", "E500YZ", "E700H", "E700F", "E7009", "E700M", "G3815", "G3815", "G3815", "F127G", "E225F", "E236B", "F415F", "E5260", "E625F", "F900U", "F907N", "F900F", "F9000", "F907B", "F900W", "G150NL", "G155S", "G1650", "W2015", "G7102", "G7105", "G7106", "G7108", "G7202", "G720N0", "G7200", "G720AX", "G530T1", "G530H", "G530FZ", "G531H", "G530BT", "G532F", "G531BT", "G531M", "J727AZ", "J100FN", "J100H", "J120FN", "J120H", "J120F", "J120M", "J111M", "J111F", "J110H", "J110G", "J110F", "J110M", "J105H", "J105Y", "J105B", "J106H", "J106F", "J106B", "J106M", "J200F", "J200M", "J200G", "J200H", "J200F", "J200GU", "J260M", "J260F", "J260MU", "J260F", "J260G", "J200BT", "G532G", "G532M", "G532MT", "J250M", "J250F", "J210F", "J260AZ", "J3109", "J320A", "J320G", "J320F", "J320H", "J320FN", "J330G", "J330F", "J330FN", "J337V", "J337P", "J337A", "J337VPP", "J337R4", "J327VPP", "J327V", "J327P", "J327R4", "S327VL", "S337TL", "S367VL", "J327A", "J327T1", "J327T", "J3110", "J3119S", "J3119", "S320VL", "J337T", "J400M", "J400F", "J400F", "J410F", "J410G", "J410F", "J415FN", "J415F", "J415G", "J415GN", "J415N", "J500FN", "J500M", "J510MN", "J510FN", "J510GN", "J530Y", "J530F", "J530G", "J530FM", "G570M", "G570F", "G570Y", "J600G", "J600FN", "J600GT", "J600F", "J610F", "J610G", "J610FN", "J710F", "J700H", "J700M", "J700F", "J700P", "J700T", "J710GN", "J700T1", "J727A", "J727R4", "J737T", "J737A", "J737R4", "J737V", "J737T1", "J737S", "J737P", "J737VPP", "J701F", "J701M", "J701MT", "S767VL", "S757BL", "J720F", "J720M", "G615F", "G615FU", "G610F", "G610M", "G610Y", "G611MT", "G611FF", "G611M", "J730G", "J730GM", "J730F", "J730FM", "S727VL", "S737TL", "J727T1", "J727T1", "J727V", "J727P", "J727VPP", "J727T", "C710F", "J810M", "J810F", "J810G", "J810Y", "A605K", "A605K", "A202K", "M336K", "A326K", "C115", "C115L", "C1158", "C1158", "C115W", "C115M", "S120VL", "M015G", "M015F", "M013F", "M017F", "M022G", "M022F", "M022M", "M025F", "M105G", "M105M", "M105F", "M107F", "M115F", "M115F", "M127F", "M127G", "M135M", "M135F", "M135FU", "M205FN", "M205F", "M205G", "M215F", "M215G", "M225FV", "M236B", "M236Q", "M305F", "M305M", "M307F", "M307FN", "M315F", "M317F", "M325FV", "M325F", "M326B", "M336B", "M336BU", "M405F", "M426B", "M515F", "M526BR", "M526B", "M536B", "M625F", "G750H", "G7508Q", "G7509", "N970U", "N970F", "N971N", "N970U1", "N770F", "N975U1", "N975U", "N975F", "N975F", "N976N", "N980F", "N981U", "N981B", "N985F", "N9860", "N986N", "N986U", "N986B", "N986W", "N9008V", "N9006", "N900A", "N9005", "N900W8", "N900", "N9009", "N900P", "N9000Q", "N9002", "9005", "N750L", "N7505", "N750", "N7502", "N910F", "N910V", "N910C", "N910U", "N910H", "N9108V", "N9100", "N915FY", "N9150", "N915T", "N915G", "N915A", "N915F", "N915S", "N915D", "N915W8", "N916S", "N916K", "N916L", "N916LSK", "N920L", "N920S", "N920G", "N920A", "N920C", "N920V", "N920I", "N920K", "N9208", "N930F", "N9300", "N930x", "N930P", "N930X", "N930W8", "N930V", "N930T", "N950U", "N950F", "N950N", "N960U", "N960F", "N960U", "N935F", "N935K", "N935S", "G550T", "G550FY", "G5500", "G5510", "G550T1", "S550TL", "G5520", "G5528", "G600FY", "G600F", "G6000", "G6100", "G610S", "G611F", "G611L", "G110M", "G110H", "G110B", "G910S", "G316HU", "G977N", "G973U1", "G973F", "G973W", "G973U", "G770U1", "G770F", "G975F", "G975U", "G970U", "G970U1", "G970F", "G970N", "G980F", "G981U", "G981N", "G981B", "G780G", "G780F", "G781W", "G781U", "G7810", "G9880", "G988B", "G988U", "G988B", "G988U1", "G985F", "G986U", "G986B", "G986W", "G986U1", "G991U", "G991B", "G990B", "G990E", "G990U", "G998U", "G996W", "G996U", "G996N", "G9960", "S901U", "S901B", "S908U", "S908U1", "S908B","S9080", "S908N", "S908E", "S906U", "S906E", "S906N", "S906B", "S906U1", "G730V", "G730A", "G730W8", "C105L", "C101", "C105", "C105K", "C105S", "G900F", "G900P", "G900H", "G9006V", "G900M", "G900V", "G870W", "G890A", "G870A", "G900FD", "G860P", "G901F", "G901F", "G800F", "G800H", "G903F", "G903W", "G920F", "G920K", "G920I", "G920A", "G920P", "G920S", "G920V", "G920T", "G925F", "G925A", "G925W8", "G928F", "G928C", "G9280", "G9287", "G928T", "G928I", "G930A", "G930F", "G930W8", "G930S", "G930V", "G930P", "G930L", "G891A", "G935F", "G935T", "G935W8", "G9350", "G950F", "G950W", "G950U", "G892A", "G892U", "G8750", "G955F", "G955U", "G955U1", "G955W", "G955N", "G960U", "G960U1", "G960F", "G965U", "G965F", "G965U1", "G965N", "G9650", "J321AZ", "J326AZ", "J336AZ", "T116", "T116NU", "T116NY", "T116NQ", "T2519", "G318HZ", "T255S", "W2016", "W2018", "W2019", "W2021", "W2022", "G600S", "E426S", "G3812", "G3812B", "G3818", "G388F", "G389F", "G390F", "G398FN"]
   gt = ['GT-1015','GT-1020','GT-1030','GT-1035','GT-1040','GT-1045','GT-1050','GT-1240','GT-1440','GT-1450','GT-18190','GT-18262','GT-19060I','GT-19082','GT-19083','GT-19105','GT-19152','GT-19192','GT-19300','GT-19505','GT-2000','GT-20000','GT-200s','GT-3000','GT-414XOP','GT-6918','GT-7010','GT-7020','GT-7030','GT-7040','GT-7050','GT-7100','GT-7105','GT-7110','GT-7205','GT-7210','GT-7240R','GT-7245','GT-7303','GT-7310','GT-7320','GT-7325','GT-7326','GT-7340','GT-7405','GT-7550 5GT-8005','GT-8010','GT-81','GT-810','GT-8105','GT-8110','GT-8220S','GT-8410','GT-9300','GT-9320','GT-93G','GT-A7100','GT-A9500','GT-ANDROID','GT-B2710','GT-B5330','GT-B5330B','GT-B5330L','GT-B5330ZKAINU','GT-B5510','GT-B5512','GT-B5722','GT-B7510','GT-B7722','GT-B7810','GT-B9150','GT-B9388','GT-C3010','GT-C3262','GT-C3310R','GT-C3312','GT-C3312R','GT-C3313T','GT-C3322','GT-C3322i','GT-C3520','GT-C3520I','GT-C3592','GT-C3595','GT-C3782','GT-C6712','GT-E1282T','GT-E1500','GT-E2200','GT-E2202','GT-E2250','GT-E2252','GT-E2600','GT-E2652W','GT-E3210','GT-E3309','GT-E3309I','GT-E3309T','GT-G530H','GT-g900f','GT-G930F','GT-H9500','GT-I5508','GT-I5801','GT-I6410','GT-I8150','GT-I8160OKLTPA','GT-I8160ZWLTTT','GT-I8258','GT-I8262D','GT-I8268','GT-I8505','GT-I8530BAABTU','GT-I8530BALCHO','GT-I8530BALTTT','GT-I8550E','GT-i8700','GT-I8750','GT-I900','GT-I9008L','GT-i9040','GT-I9080E','GT-I9082C','GT-I9082EWAINU','GT-I9082i','GT-I9100G','GT-I9100LKLCHT','GT-I9100M','GT-I9100P','GT-I9100T','GT-I9105UANDBT','GT-I9128E','GT-I9128I','GT-I9128V','GT-I9158P','GT-I9158V','GT-I9168I','GT-I9192I','GT-I9195H','GT-I9195L','GT-I9250','GT-I9303I','GT-I9305N','GT-I9308I','GT-I9505G','GT-I9505X','GT-I9507V','GT-I9600','GT-m190','GT-M5650','GT-mini','GT-N5000S','GT-N5100','GT-N5105','GT-N5110','GT-N5120','GT-N7000B','GT-N7005','GT-N7100T','GT-N7102','GT-N7105','GT-N7105T','GT-N7108','GT-N7108D','GT-N8000','GT-N8005','GT-N8010','GT-N8020','GT-N9000','GT-N9505','GT-P1000CWAXSA','GT-P1000M','GT-P1000T','GT-P1010','GT-P3100B','GT-P3105','GT-P3108','GT-P3110','GT-P5100','GT-P5200','GT-P5210XD1','GT-P5220','GT-P6200','GT-P6200L','GT-P6201','GT-P6210','GT-P6211','GT-P6800','GT-P7100','GT-P7300','GT-P7300B','GT-P7310','GT-P7320','GT-P7500D','GT-P7500M','GT-P7500R','GT-P7500V','GT-P7501','GT-P7511','GT-S3330','GT-S3332','GT-S3333','GT-S3370','GT-S3518','GT-S3570','GT-S3600i','GT-S3650','GT-S3653W','GT-S3770K','GT-S3770M','GT-S3800W','GT-S3802','GT-S3850','GT-S5220','GT-S5220R','GT-S5222','GT-S5230','GT-S5230W','GT-S5233T','GT-s5233w','GT-S5250','GT-S5253','GT-s5260','GT-S5280','GT-S5282','GT-S5283B','GT-S5292','GT-S5300','GT-S5300L','GT-S5301','GT-S5301B','GT-S5301L','GT-S5302','GT-S5302B','GT-S5303','GT-S5303B','GT-S5310','GT-S5310B','GT-S5310C','GT-S5310E','GT-S5310G','GT-S5310I','GT-S5310L','GT-S5310M','GT-S5310N','GT-S5312','GT-S5312B','GT-S5312C','GT-S5312L','GT-S5330','GT-S5360','GT-S5360B','GT-S5360L','GT-S5360T','GT-S5363','GT-S5367','GT-S5369','GT-S5380','GT-S5380D','GT-S5500','GT-S5560','GT-S5560i','GT-S5570B','GT-S5570I','GT-S5570L','GT-S5578','GT-S5600','GT-S5603','GT-S5610','GT-S5610K','GT-S5611','GT-S5620','G-S5670','GT-S5670B','GT-S5670HKBZTA','GT-S5690','GT-S5690R','GT-S5830','GT-S5830D','GT-S5830G','GT-S5830i','GT-S5830L','GT-S5830M','GT-S5830T','GT-S5830V','GT-S5831i','GT-S5838','GT-S5839i','GT-S6010','GT-S6010BBABTU','GT-S6012','GT-S6012B','GT-S6102','GT-S6102B','GT-S6293T','GT-S6310B','GT-S6310ZWAMID','GT-S6312','GT-S6313T','GT-S6352','GT-S6500','GT-S6500D','GT-S6500L','GT-S6790','GT-S6790L','GT-S6790N','GT-S6792L','GT-S6800','GT-S6800HKAXFA','GT-S6802','GT-S6810','GT-S6810B','GT-S6810E','GT-S6810L','GT-S6810M','GT-S6810MBASER','GT-S6810P','GT-S6812','GT-S6812B','GT-S6812C','GT-S6812i','GT-S6818','GT-S6818V','GT-S7230E','GT-S7233E','GT-S7250D','GT-S7262','GT-S7270','GT-S7270L','GT-S7272','GT-S7272C','GT-S7273T','GT-S7278','GT-S7278U','GT-S7390','GT-S7390G','GT-S7390L','GT-S7392','GT-S7392L','GT-S7500','GT-S7500ABABTU','GT-S7500ABADBT','GT-S7500ABTTLP','GT-S7500CWADBT','GT-S7500L','GT-S7500T','GT-S7560','GT-S7560M','GT-S7562','GT-S7562C','GT-S7562i','GT-S7562L','GT-S7566','GT-S7568','GT-S7568I','GT-S7572','GT-S7580E','GT-S7583T','GT-S758X','GT-S7592','GT-S7710','GT-S7710L','GT-S7898','GT-S7898I','GT-S8500','GT-S8530','GT-S8600','GT-STB919','GT-T140','GT-T150','GT-V8a','GT-V8i','GT-VC818','GT-VM919S','GT-W131','GT-W153','GT-X831','GT-X853','GT-X870','GT-X890','GT-Y8750']  
   strvoppo = f"Mozilla/5.0 (Linux; Android {str(rr(1,11))}; {str(rc(oppo))} Build/{str(rc(lonte))}) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/{str(rr(10,107))}.0.{str(rr(111,6666))}.{str(rr(10,400))} UCBrowser/{str(rr(1,20))}.{str(rr(1,10))}.0.{str(rr(111,5555))} Mobile Safari/537.36 OPR/{str(rr(10,80))}.{str(rr(1,10))}.{str(rr(111,5555))}.{str(rr(111,99999))}"
   strvredmi = f"Mozilla/5.0 (Linux; Android {str(rr(1,11))}; {str(rc(redmi))}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{str(rr(10,107))}.0.{str(rr(111,6666))}.{str(rr(10,400))} Mobile Safari/537.36"
   strvoppo1 = f"Mozilla/5.0 (Linux; Android {str(rr(1,11))}; {str(rc(oppo))}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{str(rr(10,107))}.0.{str(rr(111,6666))}.{str(rr(10,400))} Mobile Safari/537.36"
   strvinfinix = f"Mozilla/5.0 (Linux; Android {str(rr(1,11))}; Infinix {str(rc(infinix))}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{str(rr(10,107))}.0.{str(rr(111,6666))}.{str(rr(10,400))} Mobile Safari/537.36"
   strvsamsung = f"Mozilla/5.0 (Linux; Android {str(rr(1,11))}; {str(rc(samsung))}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{str(rr(10,107))}.0.{str(rr(111,6666))}.{str(rr(10,400))} Mobile Safari/537.36"
   strvredmi1 = f"Mozilla/5.0 (Linux; Android {str(rr(1,11))}; {str(rc(redmi))} Build/{str(rc(lonte))}) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/{str(rr(10,107))}.0.{str(rr(111,6666))}.{str(rr(10,400))} UCBrowser/{str(rr(1,20))}.{str(rr(1,10))}.0.{str(rr(111,5555))} Mobile Safari/537.36 OPR/{str(rr(10,80))}.{str(rr(1,10))}.{str(rr(111,5555))}.{str(rr(111,99999))}"
   strvnokiax = f"Mozilla/5.0 (Linux; Android 4.1.2; Nokia_X Build/{str(rc(build_nokiax))}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{str(rr(100,104))}.0.{str(rr(3900,4900))}.{str(rr(40,150))} Mobile Safari/537.36 NokiaBrowser/7.{str(rr(1,5))}.1.{str(rr(16,37))} {str(rc(aZ))}{str(rr(1,1000))}"
   strvgt = f"Mozilla/5.0 (Linux; Android {str(rr(4,12))}; {str(rc(gt))}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{str(rr(100,104))}.0.{str(rr(3900,4900))}.{str(rr(40,150))} Mobile Safari/537.36 {str(rc(aZ))}{str(rr(1,1000))}"
   ugen.append(strvoppo)
   ugen.append(strvredmi)
   ugen.append(strvoppo1)
   ugen.append(strvinfinix)
   ugen.append(strvsamsung)
   ugen.append(strvredmi1)
   ugen.append(strvnokiax)
   ugen.append(strvgt) 
for op in range(1000):
        rr = random.randint
        rc = random.choice
        bahasa = random.choice(["en","fr","ru","tr","id","pt","es","en-GB"])
        ua1 = f"Opera/9.80 (BlackBerry; Opera Mini/8.0.{str(rr(35000, 39000))}/{str(rr(190, 199))}.{str(rr(270, 290))}; U; {bahasa}) Presto/2.{str(rr(4, 20))}.{str(rr(420, 490))} Version/12.16"
        ua2 = f"SAMSUNG-GT-S3802 Opera/9.80 (J2ME/MIDP; Opera Mini/7.1.{str(rr(35000, 39000))}/{str(rr(190, 199))}.{str(rr(270, 290))}; U; {bahasa}) Presto/2.{str(rr(4, 20))}.{str(rr(420, 490))} Version/12.16"
        ua3 = f"Opera/9.80 (iPhone; Opera Mini/16.0.{str(rr(35000, 39000))}/{str(rr(190, 199))}.{str(rr(270, 290))}; U; {bahasa}) Presto/2.{str(rr(4, 20))}.{str(rr(420, 490))} Version/12.16"
        ua4 = f"Opera/9.80 (Android; Opera Mini/11.0.{str(rr(35000, 39000))}/{str(rr(190, 199))}.{str(rr(270, 290))}; U; {bahasa}) Presto/2.{str(rr(4, 20))}.{str(rr(420, 490))} Version/12.16"
        ua5 = f"Opera/9.80 (Windows Mobile; Opera Mini/5.1.{str(rr(35000, 39000))}/{str(rr(190, 199))}.{str(rr(270, 290))}; U; {bahasa}) Presto/2.{str(rr(4, 20))}.{str(rr(420, 490))} Version/12.16"
        ugen.append(ua1)
        ugen.append(ua2)
        ugen.append(ua3)
        ugen.append(ua4)
        ugen.append(ua5)
for generate in range(100):
        a=random.randrange(1, 9)
        b=random.randrange(1, 9)
        c=random.randrange(7, 13)
        c=random.randrange(73,100)
        d=random.randrange(4200,4900)
        e=random.randrange(40,150)
        uaku=f'Mozilla/5.0 (Linux; Android {a}.{b}; Pixel {b}) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/{c}.0.{d}.{e} Mobile Safari/537.36'
        ugen.append(uaku)


# Name and password generation
first_names_male = [
'Juan', 'Jose', 'Miguel', 'Gabriel', 'Rafael', 'Antonio', 'Carlos', 'Luis',
'Marco', 'Paolo', 'Angelo', 'Joshua', 'Christian', 'Mark', 'John', 'James',
'Daniel', 'David', 'Michael', 'Jayson', 'Kenneth', 'Ryan', 'Kevin', 'Neil',
'Jerome', 'Renzo', 'Carlo', 'Andres', 'Felipe', 'Diego', 'Mateo', 'Lucas',
'Adrian', 'Albert', 'Aldrin', 'Alfred', 'Allen', 'Alonzo', 'Amiel',
'Andre', 'Andrew', 'Angelo', 'Anton', 'Arden', 'Aries', 'Arman', 'Arnel',
'Arnold', 'Arthur', 'August', 'Avery', 'Benito', 'Benjamin', 'Bernard',
'Blake', 'Bryan', 'Bryant', 'Caleb', 'Cameron', 'Cedric', 'Cesar',
'Charles', 'Christianne', 'Clarence', 'Clark', 'Clint', 'Clyde', 'Colin',
'Conrad', 'Crispin', 'Cyril', 'Damian', 'Darrel', 'Daryl', 'Darren',
'Dean', 'Denver', 'Derrick', 'Dexter', 'Dominic', 'Dylan', 'Earl', 'Edgar',
'Edison', 'Edward', 'Edwin', 'Eli', 'Elias', 'Elijah', 'Emil', 'Emmanuel',
'Eric', 'Ernest', 'Eron', 'Ethan', 'Eugene', 'Ferdinand', 'Francis',
'Frank', 'Fred', 'Frederick', 'Galen', 'Garry', 'Genesis', 'Geo', 'Gerald',
'Gilbert', 'Giovanni', 'Greg', 'Gregory', 'Hans', 'Harold', 'Henry',
'Hugh', 'Ian', 'Irvin', 'Isaac', 'Ivan', 'Jake', 'Jared',
'Jarred', 'Jason', 'Jasper', 'Jay', 'Jayden', 'Jerald', 'Jericho',
'Jethro', 'Jimmy', 'Joel', 'Jonas', 'Jonathan', 'Jordan', 'Joseph',
'Julius', 'Justin', 'Karl', 'Kayden', 'Keith', 'Kelvin', 'Kiel', 'King',
'Kirk', 'Kyle', 'Lance', 'Larry', 'Lawrence', 'Leandro', 'Leo', 'Leonard',
'Levi', 'Liam', 'Lorenzo', 'Louie', 'Lucas', 'Lucio', 'Luisito', 'Macario',
'Malcolm', 'Marcus', 'Mario', 'Martin', 'Marvin', 'Matthew', 'Max',
'Melvin', 'Mico', 'Miguelito', 'Milan', 'Mitch', 'Nathan', 'Nathaniel',
'Neilson', 'Nelson', 'Nicholas', 'Nico', 'Noel', 'Norman', 'Oliver',
'Oscar', 'Owen', 'Patrick', 'Paulo', 'Peter', 'Philip', 'Pierre', 'Ralph',
'Randall', 'Raymond', 'Reagan', 'Reggie', 'Rein', 'Reiner', 'Ricardo',
'Rico', 'Riel', 'Robbie', 'Robert', 'Rodney', 'Roldan', 'Romeo', 'Ronald',
'Rowell', 'Russell', 'Ryanne', 'Sam', 'Samuel', 'Santino', 'Sean', 'Seth',
'Shawn', 'Simon', 'Stephen', 'Steven', 'Taylor', 'Terrence', 'Theo',
'Timothy', 'Tomas', 'Tristan', 'Troy', 'Tyler', 'Vernon', 'Victor',
'Vincent', 'Virgil', 'Warren', 'Wayne', 'Wilfred', 'William', 'Winston',
'Wyatt', 'Xander', 'Zachary', 'Zion', 'Arvin', 'Dion', 'Harvey', 'Irvin',
'Jeriel', 'Kennard', 'Levin', 'Randel', 'Ramil', 'Rendon', 'Rome', 'Roven',
'Silas', 'Tobias', 'Uriel', 'Zandro', 'Axl', 'Brysen', 'Ced', 'Clarkson',
'Deo', 'Eion', 'Errol', 'Franco', 'Gavin', 'Hansel', 'Isidro', 'Jiro',
'Kiel', 'Loren', 'Matteo', 'Noelito', 'Omar', 'Paxton', 'Quinn', 'Ramon',
'Renz', 'Sandy', 'Tyrone', 'Ulrich', 'Vince', 'Wesley', 'Yvan', 'Zed',
'Alric', 'Brent', 'Caden', 'Dionel', 'Ethaniel', 'Fritz', 'Gerson',
'Hansley', 'Ivar', 'Jeric', 'Kenzo', 'Lex', 'Morris', 'Nate', 'Orville',
'Pio', 'Quentin', 'Rydel', 'Sergio', 'Tobit', 'Ulysses', 'Val', 'Wade',
'Yohan', 'Zyren', 'Adley', 'Cairo', 'Drey', 'Enzo', 'Ferris', 'Gale',
'Hector', 'Iven', 'Jaycee', 'Kaleb', 'Lyndon', 'Macky', 'Nash', 'Oren',
'Pierce', 'Quino', 'Rustin', 'Sylvio', 'Tanner', 'Ulian', 'Vaughn',
'Weston', 'Xeno', 'Yuri', 'Zandro', 'Andro', 'Basil', 'Crisanto', 'Derris',
'Efrain', 'Florenz', 'Gael', 'Hanz', 'Ismael', 'Jeromey', 'Kielan',
'Lucian', 'Marlo', 'Nerio', 'Osric', 'Patrik', 'Rion', 'Santino', 'Timo',
'Vin', 'Wilmer', 'Zaim', 'Zen', 'Gabriel', 'Joshua', 'John', 'Mark', 'James', 'Daniel', 'Matthew', 'Miguel', 'Nathan', 'David',
'Andrew', 'Joseph', 'Christian', 'Emmanuel', 'Adrian', 'Angelo', 'Carl', 'Marco', 'Kenneth', 'Ryan',
'Justin', 'Patrick', 'Paul', 'Francis', 'Anthony', 'Carlos', 'Rafael', 'Samuel', 'Sebastian', 'Elijah',
'Aiden', 'Brent', 'Cedric', 'Darren', 'Ethan', 'Felix',
'Gavin', 'Harold', 'Ian', 'Jacob', 'Kyle', 'Lance',
'Mason', 'Noel', 'Oscar', 'Preston', 'Quentin', 'Riley',
'Steven', 'Tristan', 'Ulysses', 'Vernon', 'Warren', 'Xander',
'Yves', 'Zachary', 'Aaron', 'Benjo', 'Calvin', 'Damien',
'Edward', 'Francis', 'Gerald', 'Harvey', 'Irvin', 'Jasper',
'Kevin', 'Lloyd', 'Marco', 'Nathaniel', 'Owen', 'Patrick',
'Ramon', 'Simon', 'Trevor', 'Vincent', 'Wilfred', 'Zion',
'Alfred', 'Bryan', 'Clarence', 'Daryl', 'Emil', 'Franco',
'Gilbert', 'Henry', 'Isaac', 'Jerome', 'Kristoffer', 'Leandro',
'Mario', 'Noah', 'Paolo', 'Rey', 'Santino', 'Troy',
'Vince', 'Wayne', 'Xian', 'Yohan', 'Zayne', 'Adonis',
'Brandon', 'Cyrus', 'Dominic', 'Enzo', 'Frederick', 'Gideon',
'Hanz', 'Jett', 'Kenzo', 'Luciano', 'Matteo',
'Nico', 'Orion', 'Pierce', 'Rafael', 'Stefan', 'Tobias',
'Valentin', 'Weston', 'Xavi', 'Yasser', 'Zedrick', 'Alonzo',
'Bryce', 'Coby', 'Dexter', 'Eli', 'Finn', 'Gael',
'Hector', 'Ismael', 'Joaquin', 'Keith', 'Lawrence', 'Maverick',
'Nash', 'Oliver', 'Pio', 'Reuben', 'Seth', 'Travis',
'Vaughn', 'Wyatt', 'Yuri', 'Zoren', 'Andrei', 'Benedict',
'Carlo', 'Denver', 'Earl', 'Franz', 'Giovanni', 'Hans',
'Ian', 'Julian', 'Kirk', 'Leo', 'Myles', 'Neo',
'Orlando', 'Philip', 'Rico', 'Sean', 'Thaddeus', 'Vito',
'Wendell', 'Yohan', 'Zayden', 'Adrianne', 'Blaine', 'Cliff',
'Dean', 'Elmer', 'Floyd', 'Gino', 'Hubert', 'Ivan',
'Jonas', 'Kyleen', 'Lemuel', 'Marlon', 'Nolan', 'Omar',
'Patrik', 'Rustin', 'Silas', 'Trent', 'Ulrich', 'Vern',
'Wesley', 'Yancy', 'Zaldy', 'Alaric', 'Blake', 'Chester',
'Dominique', 'Eros', 'Francois', 'Gerry', 'Holden', 'Ira',
'Jules', 'Kean', 'Luther', 'Mackenzie', 'Othello',
'Pax', 'Romeo', 'Samson', 'Tanner', 'Vince', 'Wylie',
'Yago', 'Zionel', 'Alec', 'Ben', 'Dion',
'Emerson', 'Fritz', 'Gareth', 'Hunter', 'Isidro', 'Jairo',
'Kale', 'Levi', 'Miles', 'Oren', 'Paxton',
'Ryder', 'Shawn', 'Theo', 'Urian', 'Victor', 'Wilmer',
'Yosef', 'Zain', 'Alvin', 'Brando', 'Clint', 'Dale',
'Everett', 'Fredrick', 'Garry', 'Howard', 'Isaias', 'Jansen',
'Kaleb', 'Lorenzo', 'Markus', 'Nicko', 'Owen', 'Parker',
'Raymond', 'Shane', 'Tyrone', 'Vince', 'Winston', 'Yusef',
'Zyler', 'Aron', 'Benedicto', 'Chris', 'Dariel', 'Eagan',
'Felipe', 'George', 'Hayden', 'Ivor', 'Justin', 'Kenrick',
'Lian', 'Mack', 'Nolan', 'Osric', 'Pio', 'Ramil',
'Sherwin', 'Tadeo', 'Vaughn', 'Wilbur', 'Yvan', 'Zarek',
'Albie', 'Briggs', 'Casper', 'Damon', 'Eliot', 'Farley',
'Garth', 'Hansel', 'Jayden', 'Kristian', 'Logan',
'Matias', 'Nixon', 'Orin', 'Paulo', 'Reagan', 'Soren',
'Trevin', 'Vernon', 'Wyatt', 'Yul', 'Zebedee', 'Alexei',
'Brock', 'Claudio', 'Derrick', 'Elijah', 'Fidel', 'Gavin',
'Hershel', 'Ismael', 'Jovan', 'Kieran', 'Lucian', 'Marvin',
'Nico', 'Ollie', 'Pablo', 'Roderick', 'Simeon', 'Terrence',
'Uriel', 'Virgil', 'Wayne', 'Yoshua', 'Zain', 'Aries',
'Bruno', 'Caden', 'Darwin', 'Ephraim', 'Finnley', 'Gomer',
'Harry', 'Indie', 'Jesse', 'Keaton', 'Lazaro', 'Mordecai',
'Nero', 'Orvin', 'Presley', 'Rufus', 'Stanley', 'Tomas',
'Uri', 'Vito', 'West', 'Yasir', 'Zev', 'Alton',
'Bernard', 'Carter', 'Dionisio', 'Edison', 'Fernando', 'Gabe',
'Hugh', 'Immanuel', 'Joel', 'Kristoff', 'Lucio', 'Mikel',
'Nevin', 'Osmond', 'Paulino', 'Rico', 'Stewart', 'Trent',
'Ulysses', 'Vince', 'Wylder', 'Yunus', 'Zarek', 'Abel',
'Benson', 'Claudio', 'Dennis', 'Ezekiel', 'Francis', 'Gavin',
'Harlan', 'Ivan', 'Jericho', 'Kendrick', 'Lars', 'Mathew',
'Nestor', 'Octavio', 'Perry', 'Rogelio', 'Sandy', 'Tyrone',
'Ulises', 'Vern', 'Wendel', 'Yves', 'Zac', 'Albert',
'Blair', 'Cruz', 'Dionel', 'Elvin', 'Fabian', 'Giancarlo',
'Hanzel', 'Iago', 'Jon', 'Kyle', 'Leif', 'Marcelo',
'Nigel', 'Orwell', 'Pierce', 'Roldan', 'Sage', 'Truman',
'Urbano', 'Vance', 'Wes', 'Yuki', 'Zandro', 'Amiel',
'Bert', 'Colin', 'Daryl', 'Erwin', 'Francisco', 'Geoff',
'Harris', 'Ian', 'Jayvee', 'Kristo', 'Logen', 'Manny',
'Nuel', 'Olan', 'Pablo', 'Riel', 'Simeon', 'Thane',
'Umar', 'Val', 'Wyler', 'Yarden', 'Zeke', 'Anton',
'Bryce', 'Caden', 'Devon', 'Eman', 'Fritz', 'Garry',
'Henri', 'Isagani', 'Jiro', 'Kael', 'Lauro', 'Mackie',
'Nash', 'Ogie', 'Pax', 'Roi', 'Stefano', 'Troy',
'Uno', 'Vaughn', 'Wayne', 'Yasir', 'Zaniel', 'Armand',
'Blas', 'Corbin', 'Dindo', 'Edric', 'Fermin', 'Gerry',
'Hendrick', 'Isidore', 'Jemuel', 'Kurt', 'Lemuel', 'Maurice',
'Natan', 'Olan', 'Paulo', 'Renz', 'Sandy', 'Tobit',
'Uriel', 'Vito', 'Weston', 'Yuri', 'Zander', 'Ariel',
'Benny', 'Carmelo', 'Darel', 'Earl', 'Flint', 'Gian',
'Henley', 'Jeff', 'Kiko', 'Louie', 'Marlon',
'Nash', 'Orion', 'Pietro', 'Rico', 'Stevan', 'Tomas',
'Ulric', 'Vernon', 'Wyatt', 'Yeshua', 'Zeb', 'Axel',
'Berto', 'Clyde', 'Darrel', 'Ely', 'Fredo', 'Gelo',
'Hector', 'Irving', 'Jomar', 'Ken', 'Lenny', 'Mico', 'Nashon', 'Owen', 'Pietro', 'Randel', 'Sergio', 'Tristan',
'Uziel', 'Vaughn', 'Warren', 'Yvan', 'Zain', 'Alaric',
'Briggs', 'Cyril', 'Drew', 'Evan', 'Floyd', 'Gareth',
'Hiro', 'Ismael', 'Jaden', 'Kurtis', 'Leandro', 'Miguelito',
'Nolan', 'Osmar', 'Paxton', 'Ronan', 'Soren', 'Trey',
'Ulises', 'Vann', 'Wilbert', 'Yuri', 'Zandro', 'Aiden',
'Brando', 'Carter', 'Dustin', 'Elian', 'Fermin', 'Gavin',
'Hudson', 'Isagani', 'Jonel', 'Kasey', 'Lyle', 'Marlon',
'Noel', 'Omar', 'Preston', 'Rufino', 'Santino', 'Toby',
'Uri', 'Val', 'Wade', 'Yeshua', 'Zed', 'Alvin',
'Bryant', 'Colby', 'Dante', 'Eliot', 'Franco', 'Gideon',
'Hershel', 'Isaiah', 'Jasper', 'Kenric', 'Luther', 'Marcus',
'Nathaniel', 'Orvin', 'Pio', 'Rodel', 'Simeon', 'Tanner',
'Urbano', 'Victor', 'Wyatt', 'Yancey', 'Zavier', 'Arnold',
'Blake', 'Chester', 'Diego', 'Evan', 'Felipe', 'Grayson',
'Hendrick', 'Ian', 'Jiro', 'Karlo', 'Luis', 'Matthias',
'Nestor', 'Odie', 'Paco', 'Ronaldo', 'Salvador', 'Tyrone',
'Ulric', 'Vincent', 'Wendell', 'Yusef', 'Zeke', 'Anderson',
'Bruce', 'Clark', 'Davin', 'Eugene', 'Felix', 'Gustavo',
'Hiram', 'Irvin', 'Julius', 'Karl', 'Leopoldo', 'Morgan',
'Nixon', 'Oberon', 'Percy', 'Roland', 'Sam', 'Travis',
'Uziel', 'Vern', 'Willard', 'Yuri', 'Zacharias', 'Arturo',
'Bryan', 'Coby', 'Dennis', 'Edison', 'Frank', 'Gilbert',
'Harry', 'Isaias', 'Jose', 'Kendrick', 'Lance', 'Marcel',
'Nilo', 'Owen', 'Patrick', 'Rico', 'Sean', 'Theo',
'Uriah', 'Vince', 'Walter', 'Yohan', 'Zachary', 'Amos',
'Bobby', 'Curtis', 'Dion', 'Elias', 'Fritz', 'Gerry',
'Hansel', 'Ivan', 'Jorge', 'Kiel', 'Leo', 'Manny',
'Niel', 'Oscar', 'Paul', 'Randy', 'Seth', 'Trent',
'Ulrich', 'Victor', 'Wesley', 'Yvan', 'Zane', 'Ariel',
'Benji', 'Chris', 'Domingo', 'Edwin', 'Freddie', 'Gino',
'Harvey', 'Irwin', 'Joel', 'Kirk', 'Lou', 'Martin',
'Noel', 'Ollie', 'Phillip', 'Randy', 'Samson', 'Timothy',
'Ulysses', 'Vaughn', 'Winston', 'Yves', 'Zion', 'Adriel',
'Benedict', 'Connor', 'Dionel', 'Emmanuel', 'Francis', 'Gerson',
'Hugh', 'Isidro', 'Joshua', 'Kean', 'Lemuel', 'Miguel',
'Neil', 'Omar', 'Paolo', 'Rainer', 'Simeon', 'Tadeo',
'Urbano', 'Vincent', 'Wendell', 'Yul', 'Zandro', 'Alexis',
'Brent', 'Clint', 'Dario', 'Edison', 'Felipe', 'Gareth',
'Humbert', 'Isidro', 'Jericho', 'Kiefer', 'Levi', 'Maverick',
'Nick', 'Orville', 'Pierre', 'Rufus', 'Stefano', 'Troy',
'Uziel', 'Val', 'Warren', 'Yancy', 'Zeke', 'Albert',
'Benny', 'Carmelo', 'Dindo', 'Elvin', 'Franco', 'Giovanni',
'Henri', 'Ivan', 'Jairus', 'Kaleb', 'Lucio', 'Maurice',
'Nathan', 'Orion', 'Paolo', 'Ruel', 'Santino', 'Thaddeus',
'Uri', 'Vince', 'Wyatt', 'Yvan', 'Zionel', 'Anton',
'Bryce', 'Cedric', 'Darrel', 'Eren', 'Fabian', 'Gelo',
'Hans', 'Isidro', 'Jonel', 'Kiko', 'Lars', 'Mico',
'Noel', 'Olan', 'Patrick', 'Rico', 'Stephen', 'Tristan',
'Uly', 'Vaughn', 'Wendell', 'Yeshua', 'Zadok', 'Alaric',
'Brad', 'Clyde', 'Dylan', 'Eugene', 'Fermin', 'Garry',
'Hendrick', 'Isaac', 'Julian', 'Kenneth', 'Lorenzo', 'Marco',
'Noah', 'Oren', 'Paco', 'Rian', 'Silas', 'Tommy',
'Urbie', 'Vince', 'Walter', 'Yvan', 'Zayden', 'Amiel',
'Blas', 'Colin', 'Darwin', 'Ernest', 'Felix', 'Gabe',
'Harris', 'Ian', 'Jerome', 'Kevin', 'Lyle', 'Matthew',
'Nico', 'Owen', 'Paul', 'Ramon', 'Simon', 'Trent',
'Uriel', 'Victor', 'Will', 'Yves', 'Zander', 'Arvin',
'Bryan', 'Cedrick', 'Dale', 'Elias', 'Fred', 'George',
'Hugh', 'Isaac', 'Jude', 'Karlo', 'Lance', 'Miguel',
'Nash', 'Oscar', 'Patrick', 'Ralph', 'Steven', 'Tyler',
'Urbano', 'Vince', 'Wes', 'Yuri', 'Zack', 'Aiden',
'Blake', 'Connor', 'Daryl', 'Eren', 'Franz', 'Gideon',
'Hansel', 'Ivan', 'Jonas', 'Kean', 'Levi', 'Morris',
'Niel', 'Omar', 'Paulo', 'Ricky', 'Seth', 'Tristan',
'Ulysses', 'Vaughn', 'Wyatt', 'Yohan', 'Zain', 'Aaron',
'Brett', 'Clark', 'Darren', 'Eugene', 'Felix', 'Gabriel',
'Henry', 'Isaiah', 'Jacob', 'Kyle', 'Logan', 'Martin',
'Nolan', 'Owen', 'Pierce', 'Roderick', 'Shawn', 'Troy',
'Ulric', 'Vernon', 'Wayne', 'Yves', 'Zach', 'Ariel',
'Bryce', 'Cliff', 'Dean', 'Eli', 'Francis', 'Gio',
'Harry', 'Ivan', 'Jett', 'Ken', 'Liam', 'Matthew',
'Noel', 'Omar', 'Parker', 'Rafael', 'Simon', 'Theo',
'Ulysses', 'Victor', 'Wesley', 'Yuri', 'Zane', 'Andre',
'Brent', 'Cyrus', 'Dion', 'Eden', 'Frank', 'Gabe',
'Hans', 'Isaac', 'Joel', 'Kyle', 'Lance', 'Mark',
'Nico', 'Oscar', 'Paul', 'Ryan', 'Seth', 'Trent',
'Urbano', 'Vince', 'Walter', 'Yvan', 'Zeke', 'Aiden',
'Blair', 'Clifford', 'Dionisio', 'Eliot', 'Franco', 'Gavin',
'Hendrick', 'Isidro', 'Jules', 'Kenji', 'Lucio', 'Marcus',
'Noel', 'Ollie', 'Pierce', 'Rico', 'Stefan', 'Tobias',
'Uriah', 'Vaughn', 'Wyatt', 'Yves', 'Zion', 'Jerome', 'Jayden', 'Daniel', 'Ezekiel', 'Russell', 'Francis', 'Erwin', 'Kenneth', 'Ramon', 'Leo', 'Brylle', 'Philip', 'Leandro', 'Gerald', 'Jonathan', 'Timothy', 'Earl', 'Harold', 'Mark', 'Ryan', 'Kevin', 'Romeo', 'Dominic', 'Marvin', 'Alexander', 'Joel', 'Ralph', 'Allan', 'Kian', 'Simon', 'James', 'Alfred', 'Thomas', 'Paolo', 'John', 'Elijah', 'Rene', 'Martin', 'Justin', 'Patrick', 'Lloyd', 'Jose', 'Allen', 'Jonathan', 'Ronald', 'Jeremiah', 'Rafael', 'Christopher', 'Rowell', 'Kurt', 'Angelo', 'Leonard', 'Jason', 'Reymond', 'Kenzo', 'Elric', 'Samuel', 'Nelson', 'Aiden', 'Kian', 'Ramon', 'Kurt', 'Alexander', 'Rome', 'Martin', 'Zachary', 'Erwin', 'Gabriel', 'Christian', 'Adrian', 'Zion', 'Sean', 'Miguel', 'Jayden', 'Renz', 'Ian', 'Arnold', 'Carlo', 'Gerald', 'Jared', 'Edgar', 'Tony', 'Kevin', 'Carl', 'Paolo', 'Earl', 'Clyde', 'Brylle', 'Kian', 'Robert', 'Nelson', 'Martin', 'Sean', 'Arthur', 'Roderick', 'Marvin', 'Kenneth', 'Leandro', 'Tony', 'Jacob', 'Miguel', 'Rome', 'Carlo', 'Arvin', 'Axel', 'Noel', 'Zane', 'Ramon', 'Daryl', 'Russell', 'Darren', 'Roland', 'Rafael', 'Joshua', 'Aaron', 'Paolo', 'Eugene', 'Arvin', 'Jason', 'Jared', 'Lance', 'Aiden', 'Daryl', 'Joshua', 'Lawrence', 'Jose', 'Ramon', 'Noah', 'Victor', 'Gerald', 'Alvin', 'Jeffrey', 'Kurt', 'Roland', 'Carlo', 'Harvey', 'Reymond', 'Allen', 'Victor', 'Adrian', 'Justin', 'Allan', 'Axel', 'Albert', 'Santino', 'Ferdinand', 'Jayden', 'Dominic', 'Vincent', 'Xander', 'Dennis', 'Kenzo', 'Edgar', 'Paolo', 'Leonard', 'Edward', 'Ralph', 'Allen', 'Mathew', 'Lance', 'Christian', 'Dominic', 'Nathan', 'Jonathan', 'Zachary', 'Gilbert', 'Ferdinand', 'Alonzo', 'Joel', 'Mark', 'Timothy', 'Anthony', 'Dean', 'Allen', 'Carl',
'Reginald', 'Valentino', 'Weston', 'Xavier', 'Zachariah', 'Adriel',
'Benedict', 'Constantine', 'Dashiell', 'Emmanuel', 'Francisco', 'Giovanni',
'Harrison', 'Ignatius', 'Jeremiah', 'Kingston', 'Leonardo', 'Montgomery',
'Nathaniel', 'Orlando', 'Princeton', 'Remington',
'Afton', 'Finley', 'Kearney', 'Keary', 'Kegan', 'Keir', 'Kendall', 'Mannix',
'Melvin', 'Merlin', 'Murray', 'Perth', 'Ronan', 'Sean',
'Tadc', 'Tegan', 'Tiernan', 'Torin', 'Vaughan',
'Hodding', 'Kyler', 'Maarten', 'Rembrandt', 'Rodolf', 'Roosevelt',
'Schuyler', 'Van', 'Vandyke', 'Wagner',
'Aldo', 'Aleyn', 'Alford', 'Anson', 'Archibald',
'Atley', 'Atwell', 'Audie', 'Avery', 'Ayers', 'Baker', 'Balder',
'Barker', 'Bayard', 'Bishop', 'Blake', 'Blaine', 'Bramwell',
'Brant', 'Bryce', 'Byron',
'Cage', 'Cedar', 'Churchill', 'Colton', 'Crandall',
'Dack', 'Dakin', 'Dallin', 'Dalton', 'Dartmouth', 'Dawson', 'Dax',
'Denton', 'Denver', 'Denzel', 'Diamond',
'Doane', 'Doc', 'Draper', 'Dugan', 'Dunley',
'Dunn', 'Dunstan', 'Dwyer', 'Dyson', 'Edison',
'Edred', 'Egbert', 'Eldwin', 'Elgin', 'Ellis',
'Elwood', 'Emmett', 'Errol', 'Everest', 'Ewing', 'Falkner',
'Farold', 'Farran', 'Fenton', 'Finch', 'Fitz', 'Fleming',
'Flint', 'Fox', 'Freedom', 'Gaines',
'Gale', 'Gallant', 'Garfield', 'Garrett', 'Geary',
'Gene', 'Gifford', 'Gomer', 'Graham',
'Green', 'Griffin', 'Grover',
'Hart', 'Haskel', 'Heathcliff', 'Heaton', 'Helmut', 'Houston',
'Howard', 'Howe', 'Hoyt', 'Hurst', 'Huxley', 'Indiana',
'Jagger', 'Jarrell', 'Jax', 'Jaxon', 'Jay',
'Jet', 'Judson', 'Julian', 'Kaid', 'Keane', 'Keaton',
'Kell', 'Kelsey', 'Kelvin', 'Kennard', 'Kenneth', 'Kentlee',
'Ker', 'Kester', 'Kingsley', 'Kirby', 'Klay',
'Knightley', 'Kody', 'Kolby', 'Kolton', 'Kyler',
'Lake', 'Langston', 'Lathrop', 'Leighton',
'Lex', 'Lindell', 'Lindsay', 'Livingston', 'Locke', 'London',
'Lord', 'Lowell', 'Ludlow', 'Luke', 'Lusk', 'Lyndal',
'Lynn', 'Maddox', 'Mander',
'Mansfield', 'Markham', 'Marley', 'Marsh',
'Marston', 'Martin', 'Marvin', 'Massey', 'Matheson', 'Maverick',
'Maxwell', 'Mayer', 'Meldon',
'Merrick', 'Merton', 'Miles', 'Monte', 'Montgomery',
'Moreland', 'Morley', 'Morrison', 'Myles', 'Ned',
'Newt', 'Nile', 'Norman',
'Norris', 'Norton', 'Norvin',
'Norwin', 'Odell',
'Orlan', 'Ormond', 'Orrick', 'Orson', 'Osborn',
'Osgood', 'Ossie', 'Overton', 'Parsifal',
'Peers', 'Pelton', 'Pierce', 'Piers',
'Powell', 'Radford', 'Radley',
'Randal', 'Reed', 'Reynold',
'Rhett', 'Rhodes', 'Richard', 'Ridge', 'Ridgley',
'Rivers', 'Roan', 'Robin', 'Robson', 'Rockwell',
'Roden', 'Roe', 'Roldan', 'Ross',
'Rowley', 'Royce', 'Rudd', 'Rune',
'Ryder', 'Sage', 'Salisbury', 'Sanborn',
'Saxon', 'Searles', 'Seaton',
'Seger', 'Selby', 'Seldon', 'Selwyn', 'Seton',
'Sewell', 'Shade', 'Shelby', 'Sheldon', 'Shepley',
'Sidwell', 'Simeon', 'Siward', 'Skye',
'Slate', 'Smith', 'Somerton',
'Spalding', 'Stafford', 'Stanbury',
'Stanwick', 'Starr', 'Steadman', 'Sterling', 'Stetson', 'Stiles',
'Stoke', 'Storm', 'Stuart', 'Sunny', 'Sydney',
'Sylvester', 'Taft', 'Talon', 'Templeton', 'Thompson',
'Thorley', 'Tolbert', 'Tyson', 'Udall',
'Ulmer', 'Upjohn', 'Upton', 'Usher', 'Uther', 'Vail',
'Valen', 'Vine', 'Vinson', 'Vinton',
'Wadell', 'Wadsworth', 'Wain',
'Waite', 'Walcott', 'Wales', 'Walford', 'Walker',
'Waller', 'Walsh', 'Walworth', 'Warburton',
'Ward', 'Wardley', 'Ware', 'Waring',
'Warley', 'Warrick', 'Warton', 'Warwick', 'Washburn', 'Wat',
'Wayde', 'Waylon', 'Webb', 'Weldon',
'Westbrook', 'Whitby', 'Whitcomb', 'Whittaker',
'Wiley', 'Wilford', 'Wilton', 'Wirt',
'Wisdom', 'Witton', 'Wolcott', 'Wolf', 'Wolfe',
'Woodson', 'Wythe', 'Yardley', 'Yule', 'Zani',
]

first_names_female = [
'Maria', 'Ana', 'Sofia', 'Isabella', 'Gabriela', 'Valentina', 'Camila',
'Angelica', 'Nicole', 'Michelle', 'Christine', 'Sarah', 'Jessica',
'Andrea', 'Patricia', 'Jennifer', 'Karen', 'Ashley', 'Jasmine', 'Princess',
'Angel', 'Joyce', 'Kristine', 'Diane', 'Joanna', 'Carmela', 'Isabel',
'Lucia', 'Elena',
'Abigail', 'Adeline', 'Adrienne', 'Agnes', 'Aileen', 'Aira', 'Aiza',
'Alana', 'Alexa', 'Alexis', 'Alice', 'Allyson', 'Alyssa', 'Amara',
'Amelia', 'Amirah', 'Anabelle', 'Anastasia', 'Andrea', 'Angela', 'Angelie',
'Angelyn', 'Anita', 'Annabelle', 'Anne', 'Annie', 'Antoinette', 'April',
'Ariana', 'Arlene', 'Aubrey', 'Audrey', 'Aurora', 'Ava', 'Bea', 'Bella',
'Bernadette', 'Bianca', 'Blessy', 'Brianna', 'Bridget', 'Carla', 'Carmel',
'Cassandra', 'Catherine', 'Cecilia', 'Celeste', 'Charisse', 'Charlene',
'Charlotte', 'Chelsea', 'Cherry', 'Cheska', 'Clarice', 'Claudia', 'Coleen',
'Colleen', 'Cristina', 'Cynthia', 'Dahlia', 'Danica', 'Daniela',
'Danielle', 'Darlene', 'Diana', 'Dominique', 'Donna', 'Dorothy', 'Eden',
'Elaine', 'Eleanor', 'Elisa', 'Eliza', 'Ella', 'Ellen', 'Eloisa', 'Elsa',
'Emerald', 'Emily', 'Emma', 'Erica', 'Erin', 'Esme', 'Eunice', 'Faith',
'Fatima', 'Felice', 'Flor', 'Frances', 'Francesca', 'Genevieve', 'Georgia',
'Gillian', 'Giselle', 'Glenda', 'Grace', 'Gretchen', 'Gwen', 'Hailey',
'Hannah', 'Hazel', 'Heather', 'Heidi', 'Helen', 'Helena', 'Hope', 'Iana',
'Irene', 'Irish', 'Isabelle', 'Ivana', 'Ivory', 'Jacqueline', 'Jamie',
'Jane', 'Janella', 'Janet', 'Janine', 'Janna', 'Jasmine', 'Jean',
'Jeanine', 'Jem', 'Jenica', 'Jessa', 'Jillian', 'Joan', 'Joanna', 'Joanne',
'Jocelyn', 'Jolina', 'Joy', 'Judith', 'Julia', 'Julianne', 'Juliet',
'Justine', 'Kaila', 'Kaitlyn', 'Karen', 'Karina', 'Kate', 'Katrina',
'Kayla', 'Keira', 'Kendra', 'Kim', 'Kimberly', 'Krisha', 'Krista',
'Krystel', 'Kyla', 'Kylie', 'Lara', 'Larissa', 'Laura', 'Lauren', 'Lea',
'Leanne', 'Lena', 'Leslie', 'Lexi', 'Lianne', 'Liza', 'Lorraine', 'Louisa',
'Louise', 'Lovely', 'Lucille', 'Luna', 'Lyndsay', 'Lyra', 'Mae', 'Maggie',
'Maja', 'Mandy', 'Marcia', 'Margaret', 'Marian', 'Mariel', 'Marilyn',
'Marina', 'Marissa', 'Marites', 'Martha', 'Mary', 'Matilda', 'Maureen',
'Maxine', 'May', 'Megan', 'Melissa', 'Mia', 'Mika', 'Mikayla', 'Mila',
'Mira', 'Miranda', 'Mirella', 'Monica', 'Nadia', 'Naomi', 'Natalie',
'Nathalie', 'Nerissa', 'Nika', 'Nina', 'Nora', 'Norma', 'Olivia',
'Ophelia', 'Pamela', 'Patricia', 'Paula', 'Pauline', 'Pearl', 'Phoebe',
'Pia', 'Precious', 'Queenie', 'Quiana', 'Rachelle', 'Rae', 'Rain', 'Raisa',
'Ramona', 'Raven', 'Reina', 'Rhea', 'Rica', 'Richelle', 'Rina', 'Rochelle',
'Rosa', 'Rosalie', 'Roseanne', 'Rowena', 'Ruth', 'Sabrina', 'Samantha',
'Samira', 'Sandra', 'Sara', 'Selene', 'Serena', 'Shaira', 'Shaina',
'Shanelle', 'Shanika', 'Sharon', 'Sheena', 'Sheila', 'Sherlyn', 'Shiela',
'Shirley', 'Siena', 'Sierra', 'Sofia', 'Sophia', 'Steffany', 'Stephanie',
'Summer', 'Susan', 'Suzette', 'Sylvia', 'Tanya', 'Tara', 'Tatiana',
'Tessa', 'Thea', 'Theresa', 'Trisha', 'Trista', 'Valeria', 'Vanessa',
'Veronica', 'Vicky', 'Victoria', 'Viel', 'Vina', 'Vivian', 'Wendy',
'Whitney', 'Yasmin', 'Ysabel', 'Yvette', 'Yvonne', 'Zara', 'Zelda', 'Zia',
'Zoe', 'Althea', 'Arya', 'Beatriz', 'Czarina', 'Dayanara', 'Elora',
'Fiona', 'Gianna', 'Helena', 'Indira', 'Janine', 'Kalista', 'Larraine',
'Maeve', 'Noelle', 'Odessa', 'Patrina', 'Rowan', 'Selina', 'Tahlia', 'Una',
'Vienna', 'Willow', 'Xandra', 'Yanna', 'Zyra', 'Clarissa', 'Diane',
'Fritzie', 'Harley', 'Ivette', 'Juliana', 'Karmina', 'Leira', 'Maricel',
'Nerina', 'Odette', 'Pia', 'Riona', 'Sandy', 'Tanya', 'Vielka', 'Winona',
'Xyla', 'Ysa', 'Zian', 'Adria', 'Aubriel', 'Celina', 'Devina', 'Emerie',
'Florence', 'Graciela', 'Hilary', 'Isla', 'Jaira', 'Kelsey', 'Lianne',
'Maika', 'Nashira', 'Orla', 'Perla', 'Quinley', 'Roxanne', 'Soleil',
'Therese', 'Ulani', 'Verona', 'Xaviera', 'Althea', 'Andrea', 'Angela', 'Anna', 'Sarah', 'Nicole', 'Ella', 'Sophia', 'Isabella',
'Jasmine', 'Kristine', 'Michelle', 'Patricia', 'Catherine', 'Victoria', 'Samantha', 'Ashley', 'Gabrielle', 'Maryanne',
'Christine', 'Angelica', 'Stephanie', 'Jennifer', 'Amanda', 'Diana', 'Clarissa', 'Erica', 'Theresa', 'Monica',
'Ariana', 'Bea', 'Camille', 'Danica', 'Elaine', 'Faith',
'Giselle', 'Hannah', 'Inara', 'Janelle', 'Kaila', 'Lianne',
'Monique', 'Nadine', 'Olivia', 'Phoebe', 'Queenie', 'Rachelle',
'Savannah', 'Tiffany', 'Uma', 'Venice', 'Wynona', 'Ysabelle',
'Zoey', 'Abigail', 'Bianca', 'Caitlyn', 'Dahlia', 'Eliza',
'Farrah', 'Georgia', 'Hailey', 'Ivy', 'Jasmine', 'Katrina',
'Lara', 'Maxine', 'Nathalie', 'Opal', 'Patricia', 'Renee',
'Sienna', 'Trisha', 'Vania', 'Willow', 'Yasmin', 'Zaira',
'Alaina', 'Bridget', 'Clarisse', 'Deborah', 'Erika', 'Fiona',
'Gemma', 'Hazel', 'Isla', 'Janine', 'Kayla', 'Lianne',
'Mikaela', 'Noreen', 'Odessa', 'Penelope', 'Quiana', 'Rafaela',
'Sabrina', 'Therese', 'Valerie', 'Whitney', 'Yvette', 'Zelda',
'Alessia', 'Bethany', 'Cassandra', 'Diana', 'Elyse', 'Freya',
'Grace', 'Harriet', 'Iana', 'Jessa', 'Kimberly', 'Lynette',
'Marielle', 'Noemi', 'Orla', 'Patrice', 'Rosalind', 'Sophia',
'Tamara', 'Veronica', 'Willa', 'Yara', 'Zion', 'Amara',
'Bernadette', 'Celine', 'Delaney', 'Estelle', 'Faye', 'Gianna',
'Hilary', 'Ivana', 'Jillian', 'Keziah', 'Larissa', 'Mara',
'Nika', 'Oriana', 'Pamela', 'Rianne', 'Selene', 'Talia',
'Vittoria', 'Wendy', 'Ysadora', 'Zia', 'Aubrey', 'Blythe',
'Carmela', 'Daphne', 'Eden', 'Florence', 'Gwen', 'Helena',
'Inez', 'Joanna', 'Keira', 'Lourdes', 'Mayumi', 'Nadine',
'Ondrea', 'Pauleen', 'Regina', 'Simone', 'Theresa', 'Vera',
'Wynne', 'Yumi', 'Zandra', 'Aimee', 'Brooklyn', 'Carla',
'Daria', 'Eloisa', 'Fritzie', 'Glenda', 'Haidee', 'Isabel',
'Juliana', 'Kirsten', 'Liana', 'Matilda', 'Noreen', 'Ophelia',
'Patty', 'Rina', 'Samantha', 'Trina', 'Vienna', 'Xyra',
'Ynah', 'Zyra', 'Alana', 'Bettina', 'Clarissa', 'Darlene',
'Evelyn', 'Faith', 'Giulia', 'Hana', 'Ivory', 'Jamie',
'Krista', 'Lianne', 'Macy', 'Nerissa', 'Odette', 'Pauline',
'Rhianna', 'Selina', 'Trixie', 'Verna', 'Willa', 'Yara',
'Zenia', 'Angelie', 'Brianna', 'Catrina', 'Denise', 'Ellaine',
'Fiona', 'Grace', 'Hillary', 'Imogen', 'Janice', 'Kiara',
'Lara', 'Marin', 'Nina', 'Odessa', 'Phoebe', 'Reina',
'Savina', 'Tanya', 'Vanna', 'Wendelyn', 'Yvette', 'Zaira',
'Arielle', 'Blanca', 'Cheska', 'Doreen', 'Emeraude', 'Francine',
'Gillian', 'Harley', 'Isha', 'Jasmine', 'Krizia', 'Laraine',
'Misha', 'Nashira', 'Olesya', 'Patrizia', 'Rachelle', 'Serena',
'Tracy', 'Vanessa', 'Wynette', 'Ysabel', 'Zoe', 'Alliah',
'Beatriz', 'Caren', 'Danielle', 'Elora', 'Fatima', 'Gina',
'Hazel', 'Isabelle', 'Jade', 'Katya', 'Liza', 'Margaux',
'Nina', 'Odette', 'Pia', 'Raquel', 'Sofia', 'Therese',
'Vivienne', 'Winter', 'Ynah', 'Zia', 'Aaliyah', 'Blaire',
'Czarina', 'Desiree', 'Eliza', 'Faith', 'Georgina', 'Heidi',
'Ingrid', 'Jemima', 'Kailyn', 'Layla', 'Mika', 'Nicole',
'Olive', 'Paola', 'Ruth', 'Selena', 'Tala', 'Valeria',
'Xandra', 'Ysabella', 'Zyrah', 'Amira', 'Bettina', 'Chantal',
'Diane', 'Eira', 'Fiona', 'Gretchen', 'Hana', 'Ina',
'Janelle', 'Kendra', 'Lani', 'Mara', 'Nadine', 'Orla',
'Pauleen', 'Rafaela', 'Sandy', 'Tina', 'Verna', 'Winnie',
'Ysa', 'Zara', 'Ariane', 'Bambi', 'Caitlin', 'Danna',
'Ella', 'Faith', 'Gabbie', 'Hellen', 'Inna', 'Jessamine',
'Kyla', 'Lara', 'Mikaela', 'Noreen', 'Oona', 'Penelope',
'Raina', 'Sophia', 'Theresa', 'Vina', 'Winter', 'Yumi',
'Zelene', 'Alyssa', 'Briar', 'Chesca', 'Danna', 'Erin',
'Faye', 'Gwyneth', 'Hannah', 'Ira', 'Jodie', 'Keira',
'Luna', 'Mariel', 'Nika', 'Olivia', 'Paula', 'Rachelle',
'Sienna', 'Tessa', 'Vera', 'Wynne', 'Yelena', 'Zaira',
'Annika', 'Bea', 'Corinne', 'Dahlia', 'Elara', 'Fritzie',
'Giselle', 'Hailey', 'Isla', 'Jamie', 'Kassandra', 'Lyra',
'Mira', 'Nadine', 'Ornella', 'Patrice', 'Quinn', 'Renee',
'Sabrina', 'Trixie', 'Valentina', 'Winnie', 'Ysabel', 'Zia',
'Abbie', 'Blanche', 'Cleo', 'Daisy', 'Eleni', 'Faith',
'Gretel', 'Helena', 'Ivana', 'Joyce', 'Kara', 'Lianne',
'Maeve', 'Nina', 'Oriana', 'Pia', 'Ruth', 'Sari',
'Tanya', 'Vivian', 'Wynona', 'Yanna', 'Zenya', 'Asha',
'Brielle', 'Carmina', 'Dina', 'Elaiza', 'Florence', 'Gia',
'Hazel', 'Isabel', 'Jasmin', 'Kristine', 'Lia', 'Marla',
'Nadine', 'Odette', 'Patty', 'Raquel', 'Samara', 'Tessa',
'Vicky', 'Winona', 'Yani', 'Zyra', 'Aileen', 'Briena', 'Carla', 'Dayanara', 'Evelina', 'Fiona',
'Gwen', 'Hazel', 'Isobel', 'Jenna', 'Kaila', 'Leona',
'Meg', 'Nadine', 'Odessa', 'Pamela', 'Queenie', 'Renee',
'Savina', 'Trisha', 'Valeria', 'Wynnie', 'Yuna', 'Zelia',
'Althea', 'Blaine', 'Celina', 'Delia', 'Ember', 'Francesca',
'Gianna', 'Helene', 'Ingrid', 'Jordyn', 'Kyla', 'Lyn',
'Mikhaela', 'Nella', 'Orla', 'Penelope', 'Renee', 'Sophia',
'Tamara', 'Vanna', 'Willow', 'Yvaine', 'Zinnia', 'Aimee',
'Bella', 'Clarisse', 'Daria', 'Ellaine', 'Faith', 'Grace',
'Hannah', 'Ivy', 'Jazmine', 'Krisha', 'Laraine', 'Marina',
'Nia', 'Odelle', 'Priscilla', 'Rhianna', 'Sierra', 'Tanya',
'Vanessa', 'Wren', 'Ysadora', 'Zoe', 'Ariella', 'Bianca',
'Cailin', 'Daniella', 'Eunice', 'Felicia', 'Gabrielle', 'Hillary',
'Isabela', 'Jemma', 'Kianna', 'Lianne', 'Mayumi', 'Noelle',
'Olivine', 'Patricia', 'Roselyn', 'Tala', 'Veronica', 'Wendy',
'Yen', 'Zandra', 'Alethea', 'Brynn', 'Catrina', 'Dianne',
]

surnames = [
'Reyes', 'Santos', 'Cruz', 'Bautista', 'Garcia', 'Flores', 'Gonzales',
'Martinez', 'Ramos', 'Mendoza', 'Rivera', 'Torres', 'Fernandez', 'Lopez',
'Castillo', 'Aquino', 'Villanueva', 'Santiago', 'Dela Cruz', 'Perez',
'Castro', 'Mercado', 'Domingo', 'Gutierrez', 'Ramirez', 'Valdez',
'Alvarez', 'Salazar', 'Morales', 'Navarro', 'Abad', 'Abella', 'Abellanosa',
'Acevedo', 'Aguinaldo', 'Aguilar', 'Alcantara', 'Almonte', 'Alonzo',
'Altamirano', 'Amador', 'Amparo', 'Ancheta', 'Andrada', 'Angeles',
'Antonio', 'Aquino', 'Araneta', 'Arceo', 'Arellano', 'Arias', 'Asuncion',
'Avila', 'Ayala', 'Bagasbas', 'Balagtas', 'Balane', 'Balbuena',
'Ballesteros', 'Baltazar', 'Banaga', 'Bao', 'Barcenas', 'Baron', 'Basa',
'Basco', 'Bautista', 'Beltran', 'Benitez', 'Bernal', 'Blanco', 'Borja',
'Briones', 'Buendia', 'Bustamante', 'Caballero', 'Cabanilla', 'Cabrera',
'Cadiz', 'Calderon', 'Camacho', 'Canlas', 'Capili', 'Carpio', 'Castaneda',
'Castroverde', 'Catapang', 'Celis', 'Ceniza', 'Cerda', 'Chavez',
'Clemente', 'Coloma', 'Concepcion', 'Cordova', 'Cornejo', 'Coronel',
'Corpuz', 'Cortez', 'Cruzado', 'Cuenca', 'Cuevas', 'Dacanay', 'Daguio',
'Dalisay', 'Daluz', 'Damaso', 'Dancel', 'Danganan', 'De Guzman',
'Del Mundo', 'Del Rosario', 'Delos Reyes', 'Deluna', 'Desamparado',
'Dimaandal', 'Dimaculangan', 'Dizon', 'Dolor', 'Duque', 'Ebarle',
'Echevarria', 'Elizalde', 'Encarnacion', 'Enriquez', 'Escalante',
'Escobar', 'Escueta', 'Espinosa', 'Espiritu', 'Estrella', 'Evangelista',
'Fabian', 'Fajardo', 'Falcon', 'Fernan', 'Ferrolino', 'Ferrer', 'Figueras',
'Florencio', 'Fonseca', 'Francisco', 'Fuentes', 'Galang', 'Galvez',
'Garay', 'Garing', 'Gaspar', 'Gavino', 'Giron', 'Godinez', 'Gomez',
'Gonzaga', 'Granado', 'Guerrero', 'Guevarra', 'Guinto', 'Hernandez',
'Herrera', 'Hilario', 'Ignacio', 'Ilagan', 'Inocencio', 'Intal', 'Isidro',
'Jacinto', 'Javier', 'Jimenez', 'Labao', 'Lacson', 'Ladines', 'Lagman',
'Lao', 'Lara', 'Lasala', 'Lazaro', 'Legaspi', 'Leones', 'Leviste',
'Liwanag', 'Lorenzo', 'Lucero', 'Lumibao', 'Luna', 'Macaraig', 'Madarang',
'Madrid', 'Magalong', 'Magbago', 'Magno', 'Magpantay', 'Malabanan',
'Malig', 'Malinao', 'Manalo', 'Mangahas', 'Mangubat', 'Manlapig', 'Manuel',
'Marasigan', 'Marquez', 'Martel', 'Matic', 'Melendres', 'Meneses',
'Miranda', 'Mojica', 'Montero', 'Montoya', 'Morante', 'Moreno', 'Moya',
'Naval', 'Nieva', 'Nieto', 'Nieves', 'Nolasco', 'Obando', 'Ocampo',
'Oliva', 'Olivares', 'Ong', 'Ordonez', 'Ortega', 'Ortiz', 'Osorio',
'Padilla', 'Paguio', 'Palacio', 'Palma', 'Pangan', 'Panganiban',
'Panlilio', 'Pantoja', 'Paredes', 'Parilla', 'Parungao', 'Pasco', 'Pastor',
'Patricio', 'Pineda', 'Pizarro', 'Po', 'Policarpio', 'Ponce', 'Quijano',
'Quimpo', 'Quinto', 'Quirino', 'Rafael', 'Ramoso', 'Razon', 'Redillas',
'Relucio', 'Remulla', 'Riego', 'Rigor', 'Rivadeneira', 'Rizal', 'Robles',
'Rocha', 'Rodriguez', 'Rojo', 'Romualdez', 'Rosa', 'Rosales', 'Rosario',
'Rueda', 'Ruiz', 'Sablan', 'Salas', 'Salcedo', 'Salinas', 'Samson',
'San Juan', 'San Miguel', 'Sandoval', 'Santillan', 'Santoson', 'Sarmiento',
'Segovia', 'Sereno', 'Sia', 'Silang', 'Silva', 'Sison', 'Soledad',
'Soliman', 'Soriano', 'Subido', 'Suarez', 'Sumangil', 'Sy', 'Tablante',
'Tabora', 'Tacorda', 'Tagle', 'Tamayo', 'Tan', 'Tangonan', 'Tantoco',
'Tapales', 'Taruc', 'Tejada', 'Tiongson', 'Tolentino', 'Tongco', 'Toribio',
'Trinidad', 'Tronqued', 'Tuazon', 'Ubaldo', 'Ugalde', 'Umali', 'Untalan',
'Uy', 'Valencia', 'Valenton', 'Valera', 'Valle', 'Vargas', 'Velasco',
'Velasquez', 'Vergara', 'Verzosa', 'Villafuerte', 'Villalobos', 'Villamor',
'Villanueva', 'Villareal', 'Vizcarra', 'Yamamoto', 'Yap', 'Yatco', 'Yumul',
'Zabala', 'Zamora', 'Zarate', 'Zavalla', 'Zialcita', 'dela Cruz',
'Perez', 'Gomez', 'Rodriguez', 'Sanchez', 'Ramirez', 'Francisco', 'Pascual', 'Hernandez', 'Aguilar',
'Diaz', 'Lim', 'Chua', 'Uy', 'Co', 'Lee', 'Chan', 'Yap', 'Manalo', 'Panganiban', 'Marasigan',
'Agbayani', 'Macapagal',
'Abad', 'Abadiano', 'Abalos', 'Abanilla', 'Abanto', 'Abarca',
'Abaya', 'Abella', 'Abesamis', 'Abiera', 'Abinoja', 'Abisamis',
'Ablan', 'Ablaza', 'Abordo', 'Abrigo', 'Abril', 'Abucay', 'Abunda',
'Acabo', 'Acal', 'Acedera', 'Acevedo', 'Acosta', 'Adajar',
'Adan', 'Adarlo', 'Adaza', 'Adlawan', 'Adolfo', 'Adriano',
'Agbayani', 'Agcaoili', 'Agda', 'Agdeppa', 'Agero', 'Agliam',
'Aglibot', 'Agmata', 'Agnes', 'Agoncillo', 'Agpaoa', 'Agregado',
'Aguado', 'Aguila', 'Aguilar', 'Aguilera', 'Aguinaldo', 'Aguirre',
'Alarcon', 'Alba', 'Albano', 'Alcaraz', 'Alcazar', 'Alcober',
'Alcoseba', 'Alcuizar', 'Aldaba', 'Alday', 'Alegria', 'Alejandrino',
'Alejo', 'Alfonso', 'Aliño', 'Alinsangan', 'Allarde', 'Almeda',
'Almirante', 'Almonte', 'Almuete', 'Almario', 'Alonte', 'Alonzo',
'Alvarado', 'Alvarez', 'Amador', 'Amante', 'Amarillo', 'Amatong',
'Ambao', 'Ambrosio', 'Amistoso', 'Amores', 'Amparo', 'Ampil',
'Amurao', 'Anacleto', 'Ancheta', 'Andal', 'Andrada', 'Andres',
'Andrin', 'Ang', 'Angara', 'Angeles', 'Angping', 'Aniban',
'Aniceto', 'Anonas', 'Antiporda', 'Antonio', 'Antoque', 'Anunciacion',
'Apolonio', 'Apostol', 'Aquino', 'Araneta', 'Arce', 'Arcega',
'Arceo', 'Arciaga', 'Arcilla', 'Arellano', 'Arevalo', 'Arguelles',
'Aristores', 'Arnaiz', 'Arnaldo', 'Arriola', 'Arroyo', 'Arsenio',
'Asis', 'Asistio', 'Asuncion', 'Atienza', 'Aurelio', 'Austria',
'Avila', 'Ayala', 'Ayson', 'Azarcon', 'Azores',
'Bacani', 'Baclig', 'Bacungan', 'Badajos', 'Badayos', 'Badillo',
'Bagalay', 'Bagatsing', 'Bagay', 'Bagongon', 'Baguio', 'Bahena',
'Bailon', 'Balanay', 'Balane', 'Balatbat', 'Baldonado', 'Baldo',
'Baldoza', 'Baldovino', 'Balingit', 'Ballesteros', 'Balmeo', 'Balmes',
'Balmonte', 'Baluyot', 'Banaag', 'Banal', 'Banaria', 'Bangayan',
'Bangco', 'Bangoy', 'Banlaoi', 'Banzon', 'Baranda', 'Barba',
'Barcena', 'Barcelona', 'Barela', 'Bargas', 'Bariso', 'Barlaan',
'Barrientos', 'Barroga', 'Barsaga', 'Bartolome', 'Basco', 'Basilio',
'Batungbakal', 'Bautista', 'Bayani', 'Baylon', 'Bayona', 'Bayot',
'Beltran', 'Belmonte', 'Benitez', 'Bernabe', 'Bernardo', 'Bersamin',
'Blanco', 'Bonifacio', 'Borja', 'Borlongan', 'Borromeo',
'Braganza', 'Bravo', 'Brillantes', 'Briones', 'Buenaventura', 'Buendia',
'Bueno', 'Bugay', 'Bulaon', 'Bulanadi', 'Bulatao', 'Bunag',
'Burgos', 'Bustamante', 'Caballero', 'Cabanilla', 'Cabrera',
'Cabatingan', 'Cadiz', 'Calderon', 'Camacho', 'Camara', 'Campos',
'Candelaria', 'Canlas', 'Canoy', 'Carandang', 'Caraig', 'Carating',
'Cariño', 'Carreon', 'Carrillo', 'Carungay', 'Casal', 'Casanova',
'Casimiro', 'Castaneda', 'Castillo', 'Castro', 'Catapang',
'Cayabyab', 'Cayetano', 'Celestino', 'Celis', 'Centeno', 'Cervantes',
'Chavez', 'Chua', 'Cipriano', 'Clarin', 'Claudio', 'Clemente',
'Co', 'Concepcion', 'Cordero', 'Cordova', 'Cornejo', 'Coronel',
'Corpuz', 'Corral', 'Cortez', 'Crisologo', 'Crisostomo', 'Cruz',
'Cuenca', 'Cunanan', 'Custodio', 'Dacanay', 'Daguio', 'Dalisay',
'Damasco', 'Dancel', 'Dantes', 'David', 'Davila', 'Decena',
'Delacruz', 'Delgado', 'Delima', 'Delos Reyes', 'Del Rosario',
'Desiderio', 'DeVera', 'Diaz', 'Dichoso', 'Dimalanta', 'Dimaculangan',
'Dimagiba', 'Dinglasan', 'Dionisio', 'Dizon', 'Docena', 'Dolor',
'Domingo', 'Dominguez', 'Donato', 'Duenas', 'Dulay', 'Dumo',
'Durano', 'Ebarle', 'Echevarria', 'Edralin', 'Elizalde',
'Encarnacion', 'Enriquez', 'Enrile', 'Escalante', 'Escobar',
'Escueta', 'Escudero', 'Espinosa', 'Espiritu', 'Estacion', 'Esteban',
'Estrella', 'Estrada', 'Evangelista', 'Fabian', 'Fajardo', 'Falcon',
'Fajardo', 'Feliciano', 'Felipe', 'Fernandez', 'Fernan', 'Ferraren',
'Ferrolino', 'Ferrer', 'Figueroa', 'Florencio', 'Flores', 'Fontanilla',
'Francisco', 'Fuentes', 'Galang', 'Galvez', 'Gamboa', 'Garay',
'Garcia', 'Garing', 'Garrido', 'Gaspar', 'Gatchalian', 'Gatdula',
'Gatmaitan', 'Gavino', 'Geronimo', 'Giron', 'Gomez', 'Gonzaga',
'Gonzales', 'Gonzalez', 'Guerrero', 'Guevarra', 'Guinto', 'Gutierrez',
'Guzman', 'Habana', 'Halili', 'Hernandez', 'Herrera', 'Hidalgo',
'Hilario', 'Honasan', 'Hontiveros', 'Ignacio', 'Ilagan', 'Imperial',
'Inocencio', 'Isidro', 'Jacinto', 'Javier', 'Jimenez', 'Joaquin',
'Jocson', 'Kalaw', 'Katigbak', 'Lacson', 'Lagman', 'Lapid',
'Laurel', 'Lazaro', 'Ledesma', 'Legarda', 'Legaspi', 'Leonico',
'Lim', 'Liwanag', 'Locsin', 'Lopez', 'Lorenzana', 'Lorenzo',
'Loyola', 'Lozada', 'Lucero', 'Luna', 'Mabini', 'Macapagal',
'Macaraig', 'Magsaysay', 'Manalo', 'Manalac', 'Manglapus', 'Marasigan',
'Marcos', 'Mariano', 'Marquez', 'Martinez', 'Mateo', 'Matias',
'Medalla', 'Medina', 'Mercado', 'Miranda', 'Molina', 'Montano',
'Montenegro', 'Montero', 'Morales', 'Moreno', 'Nakpil', 'Narciso',
'Navarro', 'Nepomuceno', 'Neri', 'Nicolas', 'Nieto', 'Nolasco',
'Ocampo', 'Ordonez', 'Ortigas', 'Osmeña', 'Padilla', 'Palma',
'Panganiban', 'Pangilinan', 'Panlilio', 'Pantaleon', 'Paraiso', 'Pascual',
'Pastor', 'Paterno', 'Pelayo', 'Peña', 'Peralta', 'Perez',
'Pimentel', 'Pineda', 'Ponce', 'Puno', 'Punsalan', 'Quezon',
'Quirino', 'Ramirez', 'Ramos', 'Razon', 'Recto', 'Regalado',
'Revilla', 'Ricarte', 'Rivera', 'Robles', 'Rodriguez', 'Rojo',
'Roldan', 'Romero', 'Romualdez', 'Romulo', 'Roque', 'Rosales',
'Rosario', 'Roxas', 'Rubio', 'Ruiz', 'Salas', 'Salazar',
'Salcedo', 'Salonga', 'Salvador', 'Samonte', 'San Agustin', 'San Jose',
'San Juan', 'San Pedro', 'Sanchez', 'Santiago', 'Santillan', 'Sarmiento',
'Sebastian', 'Segovia', 'Silang', 'Singson', 'Sison', 'Soliman',
'Soriano', 'Sotto', 'Suarez', 'Sumulong', 'Sy', 'Tagle', 'Tamayo',
'Tan', 'Tantoco', 'Tapales', 'Tayag', 'Teodoro', 'Teves',
'Tolentino', 'Tordesillas', 'Torres', 'Trinidad', 'Tuason', 'Tugade',
'Ty', 'Umali', 'Uy', 'Valdez', 'Valencia', 'Valenzuela', 'Valera',
'Vargas', 'Velasco', 'Velasquez', 'Ventura', 'Vergara', 'Verzosa',
'Villafuerte', 'Villamor', 'Villanueva', 'Villareal', 'Villegas',
'Vinluan', 'Yap', 'Yumul', 'Zabala', 'Zaldivar', 'Zamora',
'Zapanta', 'Zarate', 'Zerrudo', 'Zialcita', 'Zobel', 'Zulueta',
]

def get_bd_name():
    first = random.choice(first_names_male + first_names_female)
    last = random.choice(surnames)
    return first, last

rpw_first_names = [
'Luna', 'Aurora', 'Mystic', 'Crystal', 'Sapphire', 'Scarlet', 'Violet',
'Rose', 'Athena', 'Venus', 'Nova', 'Stella', 'Serena', 'Raven', 'Jade',
'Ruby', 'Pearl', 'Ivy', 'Willow', 'Hazel', 'Skye', 'Aria', 'Melody',
'Harmony', 'Grace', 'Faith', 'Hope', 'Trinity', 'Destiny', 'Serenity',
'Angel', 'Star', 'Astra', 'Lyra', 'Celeste', 'Elara', 'Elysia', 'Raine',
'Sylvie', 'Nahara', 'Isolde', 'Ophelia', 'Althea', 'Calista', 'Delara',
'Eira', 'Freya', 'Gaia', 'Helena', 'Ilara', 'Junia', 'Kaia', 'Liora',
'Maeve', 'Nara', 'Odessa', 'Phoebe', 'Quinn', 'Rhea', 'Selene', 'Thalia',
'Una', 'Vanya', 'Wynter', 'Xanthe', 'Yara', 'Zara', 'Amara', 'Aurelia',
'Brina', 'Celine', 'Dahlia', 'Eden', 'Fiona', 'Gwen', 'Helia', 'Isla',
'Jessa', 'Kara', 'Lilia', 'Mara', 'Nerine', 'Oona', 'Perse', 'Runa',
'Sana', 'Tara', 'Vera', 'Willa', 'Xena', 'Yvaine', 'Zinnia', 'Aislinn',
'Arielle', 'Belladonna', 'Briar', 'Cassia', 'Daphne', 'Eleni', 'Flora',
'Gemma', 'Hera', 'Ione', 'Jadea', 'Kaira', 'Lilith', 'Maven', 'Nerida',
'Orla', 'Petra', 'Quilla', 'Risa', 'Saphira', 'Tessa', 'Vixie', 'Wren',
'Yuna', 'Zelie', 'Aiyana', 'Ameera', 'Blaire', 'Camina', 'Daria', 'Eirene',
'Faye', 'Greta', 'Honora', 'Indira', 'Jolie', 'Kahlia', 'Lunara', 'Maris',
'Nixie', 'Oriana', 'Phaedra', 'Reina', 'Soleil', 'Tahlia', 'Viera',
'Whisper', 'Xylia', 'Yasmin', 'Zephyra', 'Adira', 'Ariya', 'Brienne',
'Coraline', 'Dove', 'Emberly', 'Fable', 'Giselle', 'Harlow', 'Ivyra',
'Jorah', 'Keira', 'Lyrra', 'Mirelle', 'Nimue', 'Ophira', 'Paloma', 'Rivka',
'Sarai', 'Tirzah', 'Velia', 'Wynna', 'Xaria', 'Yllia', 'Zalina', 'Amoura',
'Aven', 'Brisa', 'Cassidy', 'Diantha', 'Elva', 'Farrah', 'Giada', 'Hollis',
'Inara', 'Jadeen', 'Kiera', 'Leira', 'Maelle', 'Naida', 'Orra', 'Pyria',
'Riona', 'Saphine', 'Tova', 'Vanyael', 'Winry', 'Xavia', 'Ysella', 'Zyria',
'Alera', 'Arwen', 'Brielle', 'Cyrene', 'Deira', 'Evania', 'Fianna',
'Gwenna', 'Halyn', 'Irina', 'Jovina', 'Kaelia', 'Luneth', 'Mariel',
'Nayla', 'Orelle', 'Phaena', 'Ruelle', 'Sylph', 'Thessaly', 'Valea',
'Wynnair', 'Xenara', 'Ysolde', 'Zamira', 'Alira', 'Amaris', 'Brynna',
'Ceres', 'Delyra', 'Eislyn', 'Fiora', 'Gwyne', 'Haelia', 'Ismena', 'Jalyn',
'Katria', 'Liorael', 'Maelis', 'Nessara', 'Ovelyn', 'Prisma', 'Ravine',
'Seraphine', 'Tahlira', 'Vierael', 'Wyndra', 'Xylara', 'Yvanna', 'Zerina',
'Anora', 'Aveline', 'Brienne', 'Cynra', 'Danea', 'Eirlys', 'Fael', 'Giana',
'Hessia', 'Ilona', 'Janessa', 'Kyria', 'Lirael', 'Madria', 'Norelle',
'Ophirae', 'Paela', 'Quina', 'Rilith', 'Sienna', 'Tiriel', 'Velisse',
'Wrena', 'Xamira', 'Ysenne', 'Zynra', 'Aelina', 'Alessa', 'Belwyn',
'Carmine', 'Daelia', 'Elyndra', 'Fiorael', 'Gwyneth', 'Helis', 'Isola',
'Jynra', 'Kailen', 'Lunisse', 'Mynra', 'Nyelle', 'Orissa', 'Phira',
'Rylis', 'Saphyre', 'Thyra', 'Valyn', 'Wynelle', 'Xira', 'Ylith', 'Zayra',
'Avenia', 'Ariael', 'Blythe', 'Corra', 'Delyth', 'Elaina', 'Fara', 'Gisra',
'Hellen', 'Ionea', 'Jalisa', 'Kayle', 'Lysandra', 'Mirael', 'Nysa',
'Ophirael', 'Phaelia', 'Renelle', 'Saphra', 'Tirra', 'Viona', 'Wynlie',
'Xynna', 'Ylia', 'Zinnara', 'Azura', 'Bliss', 'Cassiel', 'Dionne',
'Elaris', 'Fawn', 'Gloria', 'Haelyn', 'Inessa', 'Jael', 'Koryn', 'Lissara',
'Marenne', 'Hiraya', 'Celestine', 'Aurora', 'Astrid', 'Brielle', 'Calista', 'Davina', 'Elara', 'Freya', 'Genevieve',
'Haven', 'Iris', 'Juliet', 'Kaia', 'Lyra', 'Mira', 'Nova', 'Ophelia', 'Persephone', 'Quinn',
'Rosalie', 'Seraphina', 'Thea', 'Valencia', 'Willow', 'Xandra', 'Yara', 'Zara', 'Athena', 'Bianca', 'Hiraya', 'Seraphina', 'Anastasia', 'Celestine', 'Evangeline', 'Isadora',
'Genevieve', 'Arabella', 'Josephine', 'Valentina', 'Alessandra', 'Cassandra',
'Gabriella', 'Penelope', 'Rosalind', 'Vivienne', 'Arabesque', 'Beatrice',
'Clementine', 'Delphine', 'Esmeralda', 'Francesca', 'Gwendolyn',
'Isolde', 'Juliette', 'Katarina', 'Lavender', 'Magdalena', 'Nicolette',
'Ophelia', 'Persephone', 'Queenie', 'Rosabelle', 'Sapphire', 'Theodora',
'Valencia', 'Wilhelmina', 'Xanthia', 'Zenaida', 'Aureliana',
'Bernadette', 'Celestia', 'Desdemona', 'Fallon', 'Flannery', 'Kaie',
'Kaitlyn', 'Kassidy', 'Kathleen', 'Keena', 'Keira',
'Kendall', 'Kenna', 'Kera', 'Kiara',
'Kirra', 'Kylee', 'Lachlan', 'Lorna', 'Maeve', 'Malise',
'Morgance', 'Morgandy', 'Nonnita', 'Nuala', 'Raelin', 'Rhonda',
'Saoirse', 'Saraid', 'Seanna', 'Shela', 'Shylah', 'Tara',
'Teranika', 'Tieve', 'Treasa', 'Treva', 'Addison', 'Alivia',
'Allaya', 'Amarie', 'Amaris', 'Annabeth', 'Annalynn', 'Araminta',
'Ardys', 'Ashland', 'Avery', 'Bernadette', 'Billie',
'Birdee', 'Bliss', 'Brice', 'Brittany', 'Bryony', 'Cameo',
'Carol', 'Chalee', 'Christy', 'Corky', 'Courage',
'Daelen', 'Dana', 'Darnell', 'Dawn', 'Delsie', 'Denita',
'Devon', 'Devona', 'Diamond', 'Divinity', 'Dusty',
'Ellen', 'Eppie', 'Evelyn', 'Everilda', 'Falynn',
'Fanny', 'Faren', 'Freedom', 'Gala', 'Galen', 'Gardenia',
'Germain', 'Gig', 'Gilda', 'Giselle', 'Githa', 'Haiden',
'Halston', 'Heather', 'Henna', 'Honey', 'Idalis',
'Ilsa', 'Jersey', 'Jette', 'Jill', 'Joanna',
'Kachelle', 'Kade', 'Kady', 'Kaela', 'Kalyn', 'Kandice',
'Karrie', 'Karyn', 'Katiuscia', 'Kempley', 'Kenda', 'Kennice',
'Kenyon', 'Kiandra', 'Kimber', 'Kimn', 'Kinsey',
'Kipp', 'Kismet', 'Kortney', 'Kourtney',
'Kristal', 'Kylar', 'Ladawn', 'Ladye', 'Lainey',
'Lake', 'Lalisa', 'Landen', 'Landon', 'Landry', 'Laney',
'Langley', 'Lanna', 'Laquetta', 'Lari', 'Lark', 'Laurel',
'Lavender', 'Leane', 'LeAnn', 'Leanna', 'Leanne', 'Leanore',
'Lee', 'Leeann', 'Leighanna', 'Lexie', 'Lexis', 'Liberty',
'Liliana', 'Lillian', 'Lindley', 'Linne', 'Liora', 'Lisabet',
'Liz', 'Lizette', 'Lona', 'London', 'Loni', 'Lorena',
'Loretta', 'Lovette', 'Lynde', 'Lyndon', 'Lyndsay', 'Lynette',
'Lynley', 'Lynna', 'Lynton', 'Mada', 'Maddox', 'Madison',
'Mae', 'Maggie', 'Mahogany', 'Maia', 'Maitane', 'Maitland',
'Malachite', 'Mamie', 'Manhattan', 'Maridel', 'Marla', 'Marley',
'Marliss', 'Maud', 'May', 'Merleen', 'Mildred',
'Milissa', 'Millicent', 'Mily', 'Mykala', 'Nan',
'Nautica', 'Nelda', 'Niki', 'Nikole', 'Nimue', 'Nineve',
'Norina', 'Ofa', 'Palmer', 'Pansy', 'Paris', 'Patience',
'Patricia', 'Peony', 'Petunia', 'Pixie', 'Pleasance', 'Polly',
'Primrose', 'Princell', 'Providence', 'Purity', 'Quanah', 'Queena',
'Quella', 'Quinci', 'Rae', 'Rainbow', 'Rainelle', 'Raleigh',
'Ralphina', 'Randi', 'Raven', 'Rayelle', 'Rea', 'Remington',
'Richelle', 'Ripley', 'Roberta', 'Robin', 'Rosemary', 'Rowan',
'Rumer', 'Ryesen', 'Sable', 'Sadie', 'Saffron', 'Saga',
'Saige', 'Salal', 'Salia', 'Sandora', 'Sebille', 'Sebrina',
'Selby', 'Serenity', 'Shae', 'Shandy', 'Shanice', 'Sharman',
'Shelbi', 'Sheldon', 'Shelley', 'Sheridan', 'Sherill', 'Sheryl',
'Sheyla', 'Shirley', 'Shirlyn', 'Silver', 'Skyla', 'Skylar',
'Sorilbran', 'Sparrow', 'Spring', 'Starleen', 'Stockard', 'Storm',
'Sudie', 'Summer', 'Sunniva', 'Suzana', 'Symphony', 'Tacey',
'Tahnee', 'Taite', 'Talon', 'Tambre', 'Tamia', 'Taniya',
'Tanner', 'Tanzi', 'Taria', 'Tate', 'Tatum', 'Tawnie',
'Taya', 'Tayla', 'Taylor', 'Tayna', 'Teddi', 'Tena',
'Tera', 'Teri', 'Teryl', 'Thistle', 'Timotha', 'Tinble',
'Tosha', 'Totie', 'Traci', 'Tru', 'Trudie', 'Trudy',
'Tryamon', 'Tuesday', 'Twila', 'Twyla', 'Tyne', 'Udele',
'Unity', 'Vail', 'Vala', 'Velvet', 'Venetta', 'Walker',
'Wallis', 'Waneta', 'Waverly', 'Wendy', 'Weslee', 'Whitley',
'Whitney', 'Whoopi', 'Wilda', 'Wilfreda', 'Willow', 'Wilona',
'Winifred', 'Winsome', 'Winter', 'Wisdom', 'Wrenn', 'Yale',
'Yardley', 'Yeardley', 'Yedda', 'Young', 'Ysolde', 'Zadie',
'Zanda', 'Zavannah', 'Zavia', 'Zeolia', 'Zinnia', 'Blaine',
'Blair', 'Eilis', 'Kalene', 'Keaira', 'Keelty', 'Keely',
'Keen', 'Keitha', 'Kellan', 'Kennis', 'Kerry', 'Kevina',
'Killian', 'Kyna', 'Lakyle', 'Lee', 'Mab', 'Maeryn',
'Maille', 'Mairi', 'Maisie', 'Meara', 'Meckenzie', 'Myrna',
'Nara', 'Neala', 'Nelia', 'Oona', 'Quinn', 'Rhoswen',
'Riane', 'Riley', 'Rogan', 'Rona', 'Ryan', 'Sadb',
'Shanley', 'Shelagh', 'Sine', 'Siobhan', 'Sorcha', 'Ultreia',
'Vevila', 'Acantha', 'Adara', 'Adelpha', 'Adrienne', 'Aegle',
'Afrodite', 'Agape', 'Agata', 'Aglaia', 'Agnes', 'Aileen',
'Alcina', 'Aldora', 'Alethea', 'Alexandra', 'Alice', 'Alida',
'Alisha', 'Alixia', 'Althea', 'Aludra', 'Amara', 'Ambrosia',
'Amethyst', 'Aminta', 'Amphitrite', 'Anastasia', 'Andrea', 'Andromache',
'Andromeda', 'Angela', 'Anstice', 'Antonia', 'Anysia', 'Aphrodite',
'Arali', 'Aretha', 'Ariadne', 'Ariana', 'Arissa',
'Artemia', 'Artemis', 'Astrid', 'Athena', 'Atropos', 'Aurora',
'Avel', 'Basilissa', 'Bernice', 'Calandra',
'Calantha', 'Calista', 'Calliope', 'Candace', 'Candra', 'Carina',
'Carisa', 'Cassandra', 'Cassiopeia', 'Catherine', 'Celandia', 'Cerelia', 'Charisma', 'Christina', 'Clio', 'Cloris',
'Clotho', 'Colette', 'Cora', 'Cressida', 'Cybill', 'Cyd',
'Cynthia', 'Damaris', 'Damia', 'Daphne', 'Daria', 'Daryn',
'Dasha', 'Dea', 'Delbin', 'Della', 'Delphine', 'Delta',
'Demetria', 'Desdemona', 'Desma', 'Despina', 'Dionne', 'Diotama',
'Dora', 'Dorcas', 'Doria', 'Dorian', 'Doris', 'Dorothy',
'Dorrit', 'Drew', 'Drucilla', 'Dysis', 'Ebony', 'Effie',
'Eileen', 'Elani', 'Eleanor', 'Electra', 'Elke', 'Elma',
'Elodie', 'Eos', 'Eppie', 'Eris', 'Ethereal', 'Eudora',
'Eugenia', 'Eulalia', 'Eunice', 'Euphemia', 'Euphrosyne', 'Euterpe',
'Evadne', 'Evangeline', 'Filmena', 'Gaea', 'Galina', 'Gelasia',
'Gemini', 'Georgia', 'Greer', 'Greta', 'Harmony', 'Hebe',
'Hecate', 'Hecuba', 'Helen', 'Hera', 'Hermia', 'Hermione',
'Hero', 'Hestia', 'Hilary', 'Hippolyta', 'Hyacinth', 'Hydra',
'Ianthe', 'Ilena', 'Iolite', 'Iona', 'Irene', 'Iris',
'Isidore', 'Jacey', 'Jacinta', 'Jolanta', 'Kacia', 'Kaethe',
'Kaia', 'Kaija', 'Kairi', 'Kairos', 'Kali', 'Kalidas',
'Kalika', 'Kalista', 'Kalli', 'Kalliope', 'Kallista', 'Kalonice',
'Kalyca', 'Kanchana', 'Kandace', 'Kara', 'Karana', 'Karen',
'Karin', 'Karis', 'Karissa', 'Karlyn', 'Kasandra', 'Kassandra',
'Katarina', 'Kate', 'Katherine', 'Katina', 'Khina', 'Kineta',
'Kirsten', 'Kolina', 'Kora', 'Koren', 'Kori', 'Korina',
'Kosma', 'Kristen', 'Kristi', 'Kristina', 'Kristine', 'Kristy',
'Kristyn', 'Krysten', 'Krystina', 'Kynthia', 'Kyra', 'Kyrene',
'Kyria', 'Lacy', 'Lali', 'Lareina', 'Laria', 'Larina',
'Larisa', 'Larissa', 'Lasthenia', 'Latona', 'Layna', 'Leandra',
'Leda', 'Ledell', 'Lenore', 'Leonora', 'Leta', 'Letha',
'Lethia', 'Lexi', 'Lexie', 'Lidia', 'Lilika', 'Lina',
'Linore', 'Litsa', 'Livana', 'Livvy', 'Lotus', 'Lyanne',
'Lycorida', 'Lycoris', 'Lydia', 'Lydie', 'Lykaios', 'Lyra',
'Lyric', 'Lyris', 'Lysandra', 'Macaria', 'Madalena', 'Madelia',
'Madeline', 'Madge', 'Maeve', 'Magan', 'Magdalen', 'Maia',
'Mala', 'Malissa', 'Mara', 'Margaret', 'Marigold', 'Marilee',
'Marjorie', 'Marlene', 'Marmara', 'Maya', 'Medea', 'Medora',
'Megan', 'Megara', 'Melanctha', 'Melanie', 'Melba', 'Melenna',
'Melia', 'Melinda', 'Melissa', 'Melitta', 'Melody', 'Melpomene',
'Minta', 'Mnemosyne', 'Mona', 'Muse', 'Myda', 'Myrtle',
'Naia', 'Naida', 'Naiyah', 'Narcissa', 'Narella', 'Natasha',
'Nell', 'Nellie', 'Nellis', 'Nelly', 'Neola', 'Neoma',
'Nerin', 'Nerina', 'Neysa', 'Nichole', 'Nicia', 'Nicki',
'Nicole', 'Nike', 'Nikita', 'Niobe', 'Nitsa', 'Noire',
'Nora', 'Nyla', 'Nysa', 'Nyssa', 'Nyx', 'Obelia',
'Oceana', 'Odea', 'Odessa', 'Ofelia', 'Olympia', 'Omega',
'Onyx', 'Ophelia', 'Ophira', 'Orea', 'Oriana', 'Padgett',
'Pallas', 'Pamela', 'Pandora', 'Panphila', 'Parthenia', 'Pelagia',
'Penelope', 'Phedra', 'Philadelphia', 'Philippa', 'Philomena', 'Phoebe',
'Phyllis', 'Pirene', 'Prisma', 'Psyche', 'Ptolema', 'Pyhrrha',
'Pyrena', 'Pythia', 'Raissa', 'Rasia', 'Rene', 'Rhea',
'Rhoda', 'Rhodanthe', 'Rita', 'Rizpah', 'Saba', 'Sandra',
'Sandrine', 'Sapphira', 'Sappho', 'Seema', 'Selena', 'Selina',
'Sema', 'Sherise', 'Sibley', 'Sirena', 'Sofi', 'Sondra',
'Sophie', 'Sophronia', 'Stacia', 'Stefania',
'Stephaney', 'Stesha', 'Sybella', 'Sybil', 'Syna', 'Tabitha',
'Talia', 'Talieya', 'Taliyah', 'Tallya', 'Tamesis', 'Tanith',
'Tansy', 'Taryn', 'Tasha', 'Tasia', 'Tedra', 'Teigra',
'Tekla', 'Telma', 'Terentia', 'Terpsichore', 'Terri', 'Tess',
'Thaddea', 'Thaisa', 'Thalassa', 'Thalia', 'Than', 'Thea',
'Thelma', 'Themis', 'Theodora', 'Theodosia', 'Theola', 'Theone',
'Theophilia', 'Thera', 'Theresa', 'Thisbe', 'Thomasa', 'Thracia',
'Thyra', 'Tiana', 'Tienette', 'Timandra', 'Timothea', 'Titania',
'Titian', 'Tomai', 'Tona', 'Tresa', 'Tressa', 'Triana',
'Trifine', 'Trina', 'Tryna', 'Urania', 'Uriana', 'Vanessa',
'Vasiliki', 'Velma', 'Venus', 'Voleta', 'Xandria', 'Xandy',
'Xantha', 'Xenia', 'Xenobia', 'Xianthippe', 'Xylia', 'Xylona',
'Yolanda', 'Yolie', 'Zagros', 'Zale', 'Zanaide', 'Zandra',
'Zanita', 'Zanthe', 'Zebina', 'Zelia', 'Zena', 'Zenaide',
'Zenia', 'Zenobia', 'Zenon', 'Zera', 'Zeta', 'Zeuti',
'Zeva', 'Zinaida', 'Zoe', 'Zosima', 'Ai', 'Aiko',
'Akako', 'Akanah', 'Aki', 'Akina', 'Akiyama', 'Amarante',
'Amaya', 'Aneko', 'Anzan', 'Anzu', 'Aoi', 'Asa',
'Asami', 'Ayame', 'Bankei', 'Chika', 'Chihiro',
'Chiyo', 'Cho', 'Chorei', 'Dai', 'Eido', 'Ema',
'Etsu', 'Fuyo', 'Hakue', 'Hama', 'Hanako',
'Haya', 'Hisa', 'Himari', 'Hoshi', 'Ima', 'Ishi',
'Iva', 'Jimin', 'Jin', 'Jun', 'Junko',
'Kaede', 'Kagami', 'Kaida', 'Kaiya', 'Kameko',
'Kamin', 'Kanako', 'Kane', 'Kaori', 'Kaoru', 'Kata',
'Kaya', 'Kei', 'Keiko', 'Kiaria', 'Kichi', 'Kiku',
'Kimi', 'Kin', 'Kioko', 'Kira', 'Kita', 'Kiwa',
'Kiyoshi', 'Kohana', 'Koto', 'Kozue',
'Kuma', 'Kumi', 'Kumiko', 'Kuniko', 'Kura', 'Kyoko',
'Leiko', 'Machi', 'Machiko', 'Maeko', 'Maemi', 'Mai',
'Maiko', 'Makiko', 'Mamiko', 'Mariko', 'Masago', 'Masako',
'Matsuko', 'Mayako', 'Mayuko', 'Michi', 'Michiko', 'Midori',
'Mieko', 'Mihoko', 'Mika', 'Miki', 'Minako', 'Minato',
'Mine', 'Misako', 'Misato', 'Mitsuko', 'Miwa', 'Miya',
'Miyoko', 'Miyuki', 'Momoko', 'Mutsuko', 'Myoki', 'Nahoko',
'Nami', 'Nanako', 'Nanami', 'Naoko', 'Naomi', 'Nariko',
'Natsuko', 'Nayoko', 'Nishi', 'Nori', 'Noriko', 'Nozomi',
'Nyoko', 'Oki', 'Rai', 'Raku', 'Rei', 'Reina',
'Reiko', 'Ren', 'Renora', 'Rieko', 'Rikako', 'Riku',
'Rinako', 'Rin', 'Rini', 'Risako', 'Ritsuko', 'Roshin',
'Rumiko', 'Ruri', 'Ryoko', 'Sachi', 'Sachiko', 'Sada',
'Saeko', 'Saiun', 'Saki', 'Sakiko', 'Sakuko', 'Sakura',
'Sakurako', 'Sanako', 'Sasa', 'Sashi', 'Sato', 'Satoko',
'Sawa', 'Sayo', 'Sayoko', 'Seki', 'Shika', 'Shikah',
'Shina', 'Shinko', 'Shoko', 'Sorano', 'Suki', 'Sumi',
'Tadako', 'Taido', 'Taka', 'Takako', 'Takara', 'Taki',
'Tamaka', 'Tamiko', 'Tanaka', 'Taney', 'Tani', 'Taree',
'Tazu', 'Tennen', 'Tetsu', 'Tokiko', 'Tomi', 'Tomiko',
'Tora', 'Tori', 'Toyo', 'Tsubame', 'Umeko', 'Usagi',
'Wakana', 'Washi', 'Yachi', 'Yaki', 'Yama', 'Yasu',
'Yayoi', 'Yei', 'Yoi', 'Yoko', 'Yori', 'Yoshiko',
'Yuka', 'Yukako', 'Yukiko', 'Yumi', 'Yumiko', 'Yuri',
'Yuriko', 'Yutsuko',
]

rpw_surnames = [
'Shadow', 'Dark', 'Light', 'Star', 'Moon', 'Sun', 'Sky', 'Night', 'Dawn',
'Storm', 'Frost', 'Fire', 'Stanley', 'Nero', 'Clifford', 'Volsckev',
'Draven', 'Smith', 'Greisler', 'Wraith', 'Hale', 'Voss', 'Lockhart',
'Ashford', 'Wynters', 'Grayson', 'Ravenwood', 'Langford', 'Averill',
'Cross', 'Kane', 'Holloway', 'Mercer', 'Devereux', 'Vale', 'Alden',
'Blackwell', 'Marcellis', 'Vossler', 'Crane', 'Laurent', 'Radcliffe',
'Hadrian', 'Vexley', 'Roth', 'Everhart', 'Winslow', 'Fayden', 'Crawford',
'Ashborne', 'Davenport', 'Drayton', 'Sutherland', 'Vayne', 'Rosenthal',
'Arkwright', 'Devere', 'Langley', 'Kingsley', 'Vanora', 'Astor',
'Carrington', 'Trevane', 'Remmington', 'Wolfe', 'Drayke', 'Hawke', 'Briar',
'Sterling', 'Crowhurst', 'Marlowe', 'Hastings', 'Westwood', 'Ravenshire',
'Locke', 'Harrow', 'Draxler', 'Valemont', 'Caine', 'Redgrave', 'Frost',
'Vanthorn', 'Ashcroft', 'Moreau', 'Rothwell', 'Varen', 'Lancaster',
'Ashfield', 'Sinclair', 'Duskwood', 'Vermillion', 'Whitlock', 'Halden',
'Faust', 'Ironwood', 'Drayven', 'Grey', 'Valeheart', 'Caldwell', 'Vosslyn',
'Avenhart', 'Nightray', 'Morraine', 'Leclair', 'Hartgrave', 'Thorne',
'Montclair', 'Ashen', 'Dreyer', 'Stormwell', 'Vossen', 'Gryphon',
'Reinhart', 'Claremont', 'Hartley', 'Nightborne', 'Valentine', 'Dreyson',
'Marchand', 'Blackburn', 'Lucan', 'Callister', 'Hartfield', 'Verden',
'Draymor', 'Feyr', 'Ravencroft', 'Ainsley', 'Crestfall', 'Silvera',
'Gravemont', 'Vinter', 'Beaumont', 'Lockridge', 'Thornefield', 'Ashcroft',
'Crowley', 'Winchester', 'Keller', 'Ravenholm', 'Rosier', 'Everett',
'Valeon', 'Marrow', 'Vossell', 'Ashenwald', 'Wyncrest', 'Durand',
'Montague', 'Dreyke', 'Carmine', 'Verlith', 'Harrington', 'Briarson',
'Corvin', 'Tessler', 'Delane', 'Rayven', 'Fletcher', 'Crosswell',
'Sterren', 'Valeric', 'Blackthorn', 'Davenport', 'Vanix', 'Dravien',
'Vexen', 'Rhyker', 'Krynn', 'Greymont', 'Elridge', 'Locksen', 'Harrowell',
'Valeis', 'Avenor', 'Gravelle', 'Dravenhart', 'Noxford', 'Rothen',
'Vallier', 'Devereaux', 'Stormvale', 'Kain', 'Drevis', 'Marchen',
'Langdon', 'Frostell', 'Haldenne', 'Ravenshade', 'Vairn', 'Wyncliff',
'Greystone', 'Vossmer', 'Ashborne', 'Drexel', 'Rykov', 'Drayven',
'Malvern', 'Greyhart', 'Holloway', 'Wraithson', 'Crowden', 'Valleris',
'Stark', 'Wynther', 'Creswell', 'Torrence', 'Arden', 'Fayre', 'Crawell',
'Thayen', 'Morrick', 'Vanier', 'Drevik', 'Hawthorne', 'Evers', 'Aldric',
'Larkson', 'Valemir', 'Dravelle', 'Rothenwald', 'Greyvale', 'Veyron',
'Craven', 'Frostwyn', 'Vares', 'Ashveil', 'Locken', 'Vandrell', 'Silvern',
'Dawncrest', 'Graves', 'Hartwell', 'Falconer', 'Varnell', 'Ashwynn',
'Dravenor', 'Vollaire', 'Kingswell', 'Vashier', 'Larkwell', 'Auren',
'Ravenson', 'Greyborne', 'Voltaire', 'Halewyn', 'Verrin', 'Blackmore',
'Crimson', 'Wrenford', 'Ravelle', 'Valenor', 'Frostfield', 'Vosswick',
'Hollowcrest', 'Veyson', 'Atheron', 'Veyra', 'Raines', 'Grimmond',
'Ashlynn', 'Draywell', 'Vander', 'Vortan', 'Nightwell', 'Vallence', 'Faye',
'Roswell', 'Stormen', 'Havelock', 'Greys', 'Whitmore', 'Thayne', 'Drevan',
'Halric', 'Ashmere', 'Westhall', 'Wray', 'Norring', 'Dane', 'Valeir',
'Kraiven', 'Vosslin', 'Rynhart', 'Eldren', 'Trevane', 'Greisler',
'Hawthorne', 'Morrin', 'Draylen', 'Aurel', 'Briarson', 'Carter', 'Rexford',
'Lynhart', 'Ashland', 'Frostwick', 'Vanloren', 'Crowe', 'Vynne',
'Rothmere', 'Duskhelm', 'Harron', 'Valecrest', 'Merrin', 'Hawken',
'Dreylor', 'Blackwell', 'Farron', 'Caldren', 'Vanora', 'Hollowen',
'Varelle', 'Draymore', 'Westcliff', 'Alder', 'Gryff', 'Ashlock', 'Volsen',
'Drehl', 'Vayden', 'Ravenholt', 'Vossane', 'Krell', 'Marwen', 'Drace',
'Varenne', 'Lockmere', 'Greysten', 'Hawking', 'Ryswell', 'Drayden',
'Cresden', 'Hallow', 'Ashven', 'Valter', 'Greyson', 'Morrinell', 'Wraith',
'Veyden', 'Falken', 'Ashwell', 'Nero', 'Scavendich', 'Volschev', 'Vermont', 'Suez', 'Ashford', 'Blackwood', 'Crane', 'Draven', 'Everhart',
'Frost', 'Grimshaw', 'Hawthorne', 'Ironwood', 'Kingsley', 'Lancaster', 'Mercer', 'Nightshade', 'Oakley', 'Pembroke',
'Radcliffe', 'Shadowfax', 'Thornfield', 'Underwood', 'Vance', 'Whitmore', 'Sterling', 'Ravencroft', 'Ashbury', 'Blackwell',
]

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
{W}[{G}•{W}]{G} DEVELOPER {W}:{R} netz
{W}[{G}•{W}]{G} FACEBOOK  {W}:{R} netz
{W}[{G}•{W}]{G} GITHUB    {W}:{R} netz
{W}[{G}•{W}]{G} TOOL      {W}:{R} AUTO-FB
{W}─────────────────────────────────────────────{W}""")

def linex():
    print(f"{W}─────────────────────────────────────────────{W}")

oks = []
cps = []

def check_facebook_profile_picture(uid):
    pic_url = f"https://graph.facebook.com/{uid}/picture?type=normal"
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Mobile Safari/537.36"
    }
    try:
        response = requests.get(pic_url, headers=headers, allow_redirects=False, timeout=10)
        if response.status_code == 302:
            redirect_url = response.headers.get("Location", "")
            if "scontent" in redirect_url:
                return "live"
            else:
                return "not_live"
        else:
            return
    except requests.RequestException as e:
        return 

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
    print(f"{W}[{G}•{W}]{G} Use {R}1.1.1{G} Vpn{W}")
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
                ses = requests.Session()
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
                    'sec-ch-ua': '',
                    'sec-ch-ua-mobile': '?1',
                    'sec-ch-ua-platform': 'Android',
                    'sec-fetch-dest': 'document',
                    'sec-fetch-mode': 'navigate',
                    'sec-fetch-site': 'same-origin',
                    'sec-fetch-user': '?1',
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

def register_account(domain_choice, name_option="1", gender_option="3", custom_pass=None, max_retries=5):
    for attempt in range(max_retries):
        try:
            ses = requests.Session()
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

            import time as _time
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
                        cookie_str = ";".join([f"{k}={v}" for k, v in cookies_dict.items()])
                        return {
                            "name": f"{firstname} {lastname}",
                            "email": email,
                            "password": pww,
                            "uid": uid,
                            "cookies": cookie_str,
                            "session": ses,
                            "otp_fetched": True,
                            "otp_code": otp_code
                        }
                    else:
                        continue
                else:
                    cookie_str = ";".join([f"{k}={v}" for k, v in login_coki.items()])
                    return {
                        "name": f"{firstname} {lastname}",
                        "email": email,
                        "password": pww,
                        "uid": login_coki["c_user"],
                        "cookies": cookie_str,
                        "session": ses,
                        "otp_fetched": False,
                        "otp_code": None
                    }
            
            otp_keywords = ["checkpoint", "confirm", "code", "verification"]
            needs_otp = any(kw in response_lower for kw in otp_keywords)
            
            if needs_otp:
                success, uid, cookies_dict, otp_code = confirm_account_with_auto_otp(ses, email)
                if success and uid:
                    cookie_str = ";".join([f"{k}={v}" for k, v in cookies_dict.items()])
                    return {
                        "name": f"{firstname} {lastname}",
                        "email": email,
                        "password": pww,
                        "uid": uid,
                        "cookies": cookie_str,
                        "session": ses,
                        "otp_fetched": True,
                        "otp_code": otp_code
                    }
                else:
                    continue

        except Exception as e:
            print(f"[DEBUG] Registration error: {e}")
        
        time.sleep(2)
    
    return None

def confirm_account_with_otp(session, response_text, otp_code):
    try:
        soup = BeautifulSoup(response_text, 'html.parser')
        form = soup.find('form')
        if not form:
            return None
        
        action = form.get('action', '')
        if not action.startswith('http'):
            action = 'https://www.facebook.com' + action
        
        fields = {}
        for inp in form.find_all('input'):
            name = inp.get('name')
            value = inp.get('value', '')
            if name:
                fields[name] = value
        
        for key in ['code', 'confirm_code', 'n', 'otp', 'verification_code', 'confirmation_code']:
            if key in fields:
                fields[key] = otp_code
                break
        
        confirm_res = session.post(action, data=fields, timeout=15)
        cookies = session.cookies.get_dict()
        
        if 'c_user' in cookies:
            cookie_str = ";".join([f"{k}={v}" for k, v in cookies.items()])
            return {
                "uid": cookies["c_user"],
                "cookies": cookie_str,
                "session": session
            }
        return None
    except Exception as e:
        print(f"[DEBUG] OTP confirmation error: {e}")
        return None

def get_cookie_string(session):
    cookies = session.cookies.get_dict()
    return ";".join([f"{k}={v}" for k, v in cookies.items()])

# ============ TELEGRAM BOT KE LIYE REGISTER ACCOUNT FUNCTION - FIXED ============
def register_account_for_bot(domain_choice="yandex", name_option="1", gender_option="3", custom_pass=None, max_retries=5):
    """Single account creation for Telegram bot - ALWAYS fetches and shows OTP"""
    import time as _time
    
    for attempt in range(max_retries):
        try:
            ses = requests.Session()
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
                        print(f"{G}[✓] Returning OTP to bot: {otp_code}{W}")
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
                    # FIX: Account created without checkpoint - still fetch OTP from email!
                    print(f"{Y}[!] Account created without checkpoint, fetching OTP from email anyway...{W}")
                    otp_code = fetch_otp_from_yandex(email, timeout=60, mark_read=True)
                    print(f"{G}[✓] OTP fetched from email: {otp_code}{W}")
                    return {
                        "name": f"{firstname} {lastname}",
                        "email": email,
                        "password": pww,
                        "uid": login_coki["c_user"],
                        "cookies": cookie_str,
                        "session": ses,
                        "otp_fetched": True,
                        "otp_code": otp_code if otp_code else "OTP_CHECK_EMAIL"
                    }
            
            otp_keywords = ["checkpoint", "confirm", "code", "verification"]
            needs_otp = any(kw in response_lower for kw in otp_keywords)
            
            if needs_otp:
                success, uid, cookies_dict, otp_code = confirm_account_with_auto_otp(ses, email)
                if success and uid:
                    cookie_str = get_cookie_string(ses)
                    print(f"{G}[✓] Returning OTP to bot: {otp_code}{W}")
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

# =====================================================
# ============ NEW FUNCTIONS ADDED BELOW ============
# =====================================================

# ============ PROXY FUNCTIONS ============
def load_proxies_from_file(file_path="proxies.txt"):
    """proxies.txt se proxies load karega"""
    proxies = []
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Format: http://user:pass@ip:port or ip:port or http://ip:port
                        if '://' not in line:
                            line = 'http://' + line
                        proxies.append(line)
        else:
            # Create sample proxies.txt
            with open(file_path, 'w') as f:
                f.write("# Proxy format: http://user:pass@ip:port\n")
                f.write("# Or: ip:port\n")
                f.write("# Or: http://ip:port\n")
            print(f"{Y}[!] Created proxies.txt template. Add your proxies.{W}")
    except Exception as e:
        print(f"{R}[!] Error loading proxies: {e}{W}")
    return proxies

def check_proxy_working(proxy, test_url="https://facebook.com", timeout=10):
    """Proxy working hai ya nahi check karega"""
    try:
        proxies = {'http': proxy, 'https': proxy}
        response = requests.get(test_url, proxies=proxies, timeout=timeout, headers={'User-Agent': ugenX()})
        if response.status_code == 200:
            return True
        return False
    except:
        return False

def get_working_proxy(proxies_list):
    """List mein se working proxy return karega"""
    for proxy in proxies_list:
        if check_proxy_working(proxy):
            print(f"{G}[✓] Working proxy found: {proxy}{W}")
            return proxy
    print(f"{R}[!] No working proxies found! Using direct connection.{W}")
    return None

def get_session_with_proxy(proxy=None):
    """Proxy ke saath session create karega"""
    session = requests.Session()
    if proxy:
        session.proxies = {'http': proxy, 'https': proxy}
    return session
# =========================================

# ============ COMPLETE CHECKPOINT HANDLER ============
def handle_all_checkpoints(session, email_address):
    """
    Saare checkpoints handle karega - email confirm, security, phone skip, etc.
    """
    max_checks = 8
    for attempt in range(max_checks):
        try:
            # Current page check
            resp = session.get("https://mbasic.facebook.com/", allow_redirects=True)
            
            # Already have full access?
            if 'c_user' in session.cookies.get_dict():
                uid = session.cookies.get_dict()['c_user']
                print(f"{G}[✓] Full access achieved! UID: {uid}{W}")
                return True, uid, session.cookies.get_dict()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            text_lower = resp.text.lower()
            
            # ====== 1. EMAIL CONFIRMATION PAGE ======
            if "email address belongs to you" in text_lower:
                print(f"{Y}[*] On email confirmation page...{W}")
                otp = fetch_otp_from_yandex(email_address, timeout=120)
                if otp:
                    form = soup.find('form')
                    if form:
                        action = form.get('action', '')
                        if not action.startswith('http'):
                            action = 'https://mbasic.facebook.com' + action
                        
                        fields = {}
                        for inp in form.find_all('input'):
                            name = inp.get('name')
                            value = inp.get('value', '')
                            if name:
                                fields[name] = value
                        
                        otp_field = None
                        for key in ['code', 'confirm_code', 'n', 'approvals_code', 'otp']:
                            if key in fields:
                                otp_field = key
                                break
                        
                        if otp_field:
                            fields[otp_field] = otp
                            submit_resp = session.post(action, data=fields, allow_redirects=True)
                            print(f"{G}[✓] OTP submitted!{W}")
                            time.sleep(2)
                            continue
            
            # ====== 2. "OK" BUTTON PAGE ======
            if "you should receive your email" in text_lower:
                print(f"{Y}[*] Clicking OK button...{W}")
                ok_form = soup.find('form')
                if ok_form:
                    action = ok_form.get('action', '')
                    if not action.startswith('http'):
                        action = 'https://mbasic.facebook.com' + action
                    
                    fields = {}
                    for inp in ok_form.find_all('input'):
                        name = inp.get('name')
                        value = inp.get('value', '')
                        if name:
                            fields[name] = value
                    
                    session.post(action, data=fields, allow_redirects=True)
                    time.sleep(1)
                    continue
            
            # ====== 3. SKIP PHONE NUMBER ======
            if "confirm your phone" in text_lower or "add a phone" in text_lower:
                print(f"{Y}[*] Skipping phone number...{W}")
                skip_link = soup.find('a', href=True, string=re.compile(r'skip|not now|later|no thanks', re.I))
                if skip_link:
                    skip_url = skip_link.get('href')
                    if not skip_url.startswith('http'):
                        skip_url = 'https://mbasic.facebook.com' + skip_url
                    session.get(skip_url, allow_redirects=True)
                    time.sleep(1)
                    continue
            
            # ====== 4. PROFILE COMPLETION ======
            if "complete your profile" in text_lower or "tell us about yourself" in text_lower:
                print(f"{Y}[*] Skipping profile completion...{W}")
                skip_link = soup.find('a', href=True, string=re.compile(r'skip|later|not now', re.I))
                if skip_link:
                    skip_url = skip_link.get('href')
                    if not skip_url.startswith('http'):
                        skip_url = 'https://mbasic.facebook.com' + skip_url
                    session.get(skip_url, allow_redirects=True)
                    time.sleep(1)
                    continue
            
            # ====== 5. FRIEND SUGGESTIONS ======
            if "people you may know" in text_lower or "friend suggestions" in text_lower:
                print(f"{Y}[*] Skipping friend suggestions...{W}")
                next_link = soup.find('a', href=True, string=re.compile(r'next|continue|skip', re.I))
                if next_link:
                    next_url = next_link.get('href')
                    if not next_url.startswith('http'):
                        next_url = 'https://mbasic.facebook.com' + next_url
                    session.get(next_url, allow_redirects=True)
                    time.sleep(1)
                    continue
            
            # ====== 6. INTERESTS PAGE ======
            if "select your interests" in text_lower:
                print(f"{Y}[*] Skipping interests...{W}")
                skip_link = soup.find('a', href=re.compile(r'.*skip.*', re.I))
                if skip_link:
                    skip_url = skip_link.get('href')
                    if not skip_url.startswith('http'):
                        skip_url = 'https://mbasic.facebook.com' + skip_url
                    session.get(skip_url, allow_redirects=True)
                    time.sleep(1)
                    continue
            
            time.sleep(2)
            
        except Exception as e:
            print(f"{R}[!] Checkpoint error: {e}{W}")
        
        time.sleep(1)
    
    final_resp = session.get("https://mbasic.facebook.com/me/", allow_redirects=True)
    if 'c_user' in session.cookies.get_dict():
        uid = session.cookies.get_dict()['c_user']
        return True, uid, session.cookies.get_dict()
    
    return False, None, None

def upload_profile_picture_from_url(session, uid, image_url=None):
    """
    Profile picture upload karega - ya to URL se ya manual input se
    """
    try:
        print(f"{Y}[*] Uploading profile picture for UID: {uid}{W}")
        
        if not image_url:
            gender = random.choice(['men', 'women'])
            num = random.randint(1, 99)
            image_url = f"https://randomuser.me/api/portraits/{gender}/{num}.jpg"
        
        img_data = requests.get(image_url, timeout=15).content
        temp_path = f"temp_pfp_{uid}.jpg"
        with open(temp_path, 'wb') as f:
            f.write(img_data)
        
        profile_url = f"https://mbasic.facebook.com/{uid}/profile.php"
        resp = session.get(profile_url)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        change_photo = soup.find('a', href=re.compile(r'profile_pic|change_photo|update_pic', re.I))
        if not change_photo:
            change_photo = soup.find('a', href=re.compile(r'/photo\.php\?fbid=', re.I))
        
        if change_photo:
            photo_url = change_photo.get('href')
            if not photo_url.startswith('http'):
                photo_url = 'https://mbasic.facebook.com' + photo_url
            
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
                
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                
                return True
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        return False
        
    except Exception as e:
        print(f"{R}[!] Profile picture upload failed: {e}{W}")
        return False

def create_account_complete(use_proxy=True, name_option="1", gender_option="3", custom_pass=None, profile_pic_url=None):
    """
    Complete account creation with proxy support and profile picture
    """
    proxies_list = load_proxies_from_file("proxies.txt") if use_proxy else []
    working_proxy = get_working_proxy(proxies_list) if proxies_list else None
    
    session = get_session_with_proxy(working_proxy)
    
    result = register_account_for_bot_complete(
        session=session,
        domain_choice="yandex",
        name_option=name_option,
        gender_option=gender_option,
        custom_pass=custom_pass,
        profile_pic_url=profile_pic_url
    )
    
    return result

def register_account_for_bot_complete(session, domain_choice="yandex", name_option="1", gender_option="3", custom_pass=None, profile_pic_url=None, max_retries=5):
    """
    Complete registration with full checkpoint handling and profile picture
    """
    import time as _time
    
    for attempt in range(max_retries):
        try:
            response = session.get("https://x.facebook.com/reg", timeout=15)
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

            reg_submit = session.post("https://www.facebook.com/reg/submit/", data=payload, headers=headers, timeout=20)
            response_text = reg_submit.text
            response_lower = response_text.lower()

            if "checkpoint" in response_lower or "confirm" in response_lower or "code" in response_lower:
                print(f"{Y}[!] Verification needed for {email}, handling checkpoints...{W}")
                
                otp_code = fetch_otp_from_yandex(email, timeout=180, mark_read=True)
                
                if otp_code:
                    success, uid, cookies_dict = submit_otp_to_facebook(session, otp_code)
                    
                    if success and uid:
                        full_success, final_uid, final_cookies = handle_all_checkpoints(session, email)
                        
                        if full_success and final_uid:
                            pic_uploaded = False
                            if profile_pic_url:
                                pic_uploaded = upload_profile_picture_from_url(session, final_uid, profile_pic_url)
                            
                            cookie_str = get_cookie_string(session)
                            
                            return {
                                "name": f"{firstname} {lastname}",
                                "email": email,
                                "password": pww,
                                "uid": final_uid,
                                "cookies": cookie_str,
                                "session": session,
                                "otp_fetched": True,
                                "otp_code": otp_code,
                                "profile_pic_uploaded": pic_uploaded
                            }
            
            if 'c_user' in session.cookies.get_dict():
                uid = session.cookies.get_dict()['c_user']
                
                full_success, final_uid, final_cookies = handle_all_checkpoints(session, email)
                
                if full_success and final_uid:
                    pic_uploaded = False
                    if profile_pic_url:
                        pic_uploaded = upload_profile_picture_from_url(session, final_uid, profile_pic_url)
                    
                    cookie_str = get_cookie_string(session)
                    
                    return {
                        "name": f"{firstname} {lastname}",
                        "email": email,
                        "password": pww,
                        "uid": final_uid,
                        "cookies": cookie_str,
                        "session": session,
                        "otp_fetched": False,
                        "otp_code": None,
                        "profile_pic_uploaded": pic_uploaded
                    }

        except Exception as e:
            print(f"[DEBUG] Registration error: {e}")
        
        time.sleep(2)
    
    return None

# Modified register_account_for_bot with proxy and profile pic support (optional, keeps original working)
def register_account_for_bot_enhanced(domain_choice="yandex", name_option="1", gender_option="3", custom_pass=None, max_retries=5, use_proxy=True, profile_pic_url=None):
    """Enhanced account creation with proxy and profile pic support"""
    
    proxies_list = load_proxies_from_file("proxies.txt") if use_proxy else []
    working_proxy = get_working_proxy(proxies_list) if proxies_list else None
    
    session = get_session_with_proxy(working_proxy)
    
    result = register_account_for_bot_complete(
        session=session,
        domain_choice=domain_choice,
        name_option=name_option,
        gender_option=gender_option,
        custom_pass=custom_pass,
        profile_pic_url=profile_pic_url,
        max_retries=max_retries
    )
    
    return result

# =====================================================
# ============ END OF NEW FUNCTIONS ==================
# =====================================================

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
