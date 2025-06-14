import os

def ensure_dirs(path):
    if "/" not in path:
        return
    if not path.startswith("/"):
        path = "/" + path
    parts = path.split("/")
    curr_path = ""
    for i in range(len(parts) - 1):
        part = parts[i]
        if part:
            curr_path += "/" + part
            try:
                os.mkdir(curr_path)
            except OSError:
                pass
