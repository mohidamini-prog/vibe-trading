import os
import zipfile

def export_workspace():
    zip_filename = "/root/forschung/mohid_trading_research.zip"
    folder = "/root/forschung"
    
    print(f"Packe Forschungsordner in {zip_filename}...")
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder):
            for file in files:
                if file.endswith('.zip') or file.startswith('.'):
                    continue
                fullpath = os.path.join(root, file)
                relpath = os.path.relpath(fullpath, folder)
                zipf.write(fullpath, relpath)
                
    print(f"Export erfolgreich! Datei erstellt: {zip_filename}")

if __name__ == "__main__":
    export_workspace()
