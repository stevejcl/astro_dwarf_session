import json
from urllib import request

class StellariumConnection:
    def __init__(self, ip='127.0.0.1', port=8090):
        self.ip = ip
        self.port = port

    def get_data(self):
        url = f"http://{self.ip}:{self.port}/api/objects/info?format=json"
        try:
            with request.urlopen(url, timeout=5) as response:
                if response.status == 200:
                    return json.loads(response.read().decode())
                else:
                    raise Exception(f"Failed to retrieve data: {response.status}")
        except Exception as e:
            raise Exception(f"Error connecting to Stellarium: {e}")