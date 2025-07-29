import gc
import time

import requests


def get_claims(url_path, token, e_type=None):
    try:
        gc.collect()
        url = f"{url_path}/api/claims"
        if e_type:
            url += f"?e_type={e_type}"
        
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=3,
        )
        if resp.status_code == 200:
            try:
                return resp.json()
            except ValueError:
                return {"error": "Invalid JSON response", "code": 500}
        if resp.status_code >= 500:
            return {
                "error": "Authentication Server Error",
                "code": resp.status_code,
            }
        return {
            "error": f"Authentication Failed: {resp.status_code}",
            "code": resp.status_code,
        }
    except OSError as e:
        if e.errno == 104:
            return {"error": "Tendrl Server Down", "code": 503}
        if e.errno == 116:
            time.sleep(2)
            return {"error": "Temporary Connection Issue", "code": 500}
        return {"error": str(e), "code": 500}
    except Exception as e:
        return {"error": str(e), "code": 500}
