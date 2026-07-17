import os
import pickle
import time
from google_auth_oauthlib.flow import InstalledAppFlow

# --- SETTINGS ---
FOLDER_PATH = r"E:\client_secret_"

# YouTube API Scopes
SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 
          'https://www.googleapis.com/auth/youtube.readonly']

def main():
    if not os.path.exists(FOLDER_PATH):
        print(f"Error: Folder '{FOLDER_PATH}' nahi mila.")
        return

    files = os.listdir(FOLDER_PATH)
    
    # SIRF .json PAR END HONE WALI FILES UTHAYEGA
    secret_files = [f for f in files if f.endswith('.json')]

    if not secret_files:
        print("Folder mein koi bhi .json file nahi mili.")
        return

    print(f"Total {len(secret_files)} channels ki json files mili.\n")

    for secret_file in secret_files:
        # .json ko hata kar base naam nikalna
        base_name = secret_file.replace('.json', '')
        
        # Token file ka naam
        token_file = f"{base_name}_token.pickle"
        
        secret_path = os.path.join(FOLDER_PATH, secret_file)
        token_path = os.path.join(FOLDER_PATH, token_file)

        # Agar token file already hai toh skip karein
        if os.path.exists(token_path):
            print(f"[SKIP] {secret_file} - Token ({token_file}) pehle se maujud hai.")
            continue

        # ----- YAHAN CHANGE KIYA GAYA HAI -----
        # Ab exact file names dikhein ge
        print("\n" + "="*65)
        print(f"   JSON File (Use ho rahi hai):  {secret_file}")
        print(f"   PICKLE File (Bane gi):        {token_file}")
        print("="*65)
        # -------------------------------------

        # 30 seconds ka countdown
        print("\n*** ALERT ***")
        print("Browser open hone se pehle sahi Gmail account select kar lijiye.")
        
        for i in range(30, 0, -1):
            print(f"Browser open hone mein: {i} seconds...", end='\r')
            time.sleep(1)
        print("\n\nBrowser open ho raha hai...")

        # Auth flow start karein
        try:
            flow = InstalledAppFlow.from_client_secrets_file(secret_path, SCOPES)
            # ---- YAHAN PORT 0 KO 8080 MEIN CHANGE KIYA GAYA HAI ----
            creds = flow.run_local_server(port=8080)
            # --------------------------------------------------------
            
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
            
            print(f"\n[SUCCESS] '{token_file}' successfully save ho gayi!\n")

        except Exception as e:
            print(f"\n[ERROR] '{secret_file}' ke liye authentication fail.")
            print(f"Error: {e}\n")

        time.sleep(2)

    print("\n" + "="*65)
    print("   Tamam channels ka process mukammal ho gaya!")
    print("="*65)

if __name__ == '__main__':
    main()