"""Send 30 login attempts in quick succession and record each status code.

The ingress allows 20 a minute per client address on the login path, so
attempts past that should be refused by NGINX (503) before reaching Flask.
"""

import json
import urllib.error
import urllib.request

SITE = "https://hitc602.centralindia.cloudapp.azure.com"
codes = []
for i in range(30):
    req = urllib.request.Request(SITE + "/api/accounts/login?include_auth_token", method="POST",
                                 data=json.dumps({"email": "nobody@example.com", "password": "wrong-password"}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        codes.append(urllib.request.urlopen(req, timeout=15).status)
    except urllib.error.HTTPError as e:
        codes.append(e.code)
print(json.dumps({"attempts": len(codes), "codes": codes}))
