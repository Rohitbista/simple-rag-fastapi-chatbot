import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account
from pypdf import PdfReader
from uvfastapi.config.settings import PROJECT_ID, PRIVATE_KEY_ID, PRIVATE_KEY, CLIENT_EMAIL

# 2. Extract text from PDF
def extract_text_from_pdf(service, file_id):
    request = service.files().get_media(fileId=file_id)
    file_stream = io.BytesIO()
    downloader = MediaIoBaseDownload(file_stream, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    file_stream.seek(0)
    reader = PdfReader(file_stream)

    text = ""
    for page in reader.pages:
        text += (page.extract_text() or "") + "\n"

    return text

# 3. Extract text from Google Docs
def extract_text_from_gdoc(service, file_id):
    request = service.files().export_media(
        fileId=file_id,
        mimeType='text/plain'
    )
    file_stream = io.BytesIO()
    downloader = MediaIoBaseDownload(file_stream, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    return file_stream.getvalue().decode("utf-8")


# 4. Get all files from a folder
def get_files_from_folder(service, folder_id):
    query = f"'{folder_id}' in parents and trashed = false"

    results = service.files().list(
        q=query,
        fields="files(id, name, mimeType)"
    ).execute()

    return results.get('files', [])


# 5. Process all files
def process_folder(service, folder_id):
    files = get_files_from_folder(service, folder_id)

    all_text = {}

    for file in files:
        file_id = file['id']
        name = file['name']
        mime = file['mimeType']

        print(f"Processing: {name}")

        try:
            if mime == 'application/pdf':
                text = extract_text_from_pdf(service, file_id)

            elif mime == 'application/vnd.google-apps.document':
                text = extract_text_from_gdoc(service, file_id)

            else:
                print(f"Skipped (unsupported type): {mime}")
                continue

            all_text[name] = text

        except Exception as e:
            print(f"Error processing {name}: {e}")

    return all_text

def extract_data_from_folder(folder_id):
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

    credentials_info = {
        "type": "service_account",
        "project_id": PROJECT_ID,
        "private_key_id": PRIVATE_KEY_ID,
        "private_key": PRIVATE_KEY,
        "client_email": CLIENT_EMAIL,
        "token_uri": "https://oauth2.googleapis.com/token",
    }

    # Old method
    #creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE_PATH, scopes=SCOPES)

    creds = service_account.Credentials.from_service_account_info(
        credentials_info, 
        scopes=SCOPES
    )
    
    service = build('drive', 'v3', credentials=creds)
    
    data = process_folder(service, folder_id)
    return data

# Did during testing phase:
# data = extract_data_from_folder(GOOGLE_DRIVE_FOLDER_ID)

# # Example: print extracted text
# for filename, content in data.items():
#     print(f"\n--- {filename} ---\n")
#     print(content)  # preview first 1000 chars