# AUD-6 evidence — payload id absent from the access log

Captured on branch `fix/aud-6-payload-id-in-access-log`, 2026-09-17.

Server: `uvicorn app.main:app --port 8099` against the compose Redis,
`DATABASE_URL` unset (audit disabled — this run tests logging, not the audit table).

## Before the fix

Recorded while testing AUD-2, with `GET /secrets/{id}` still in place:

```
INFO:     127.0.0.1:52134 - "GET /secrets/<43-character payload id> HTTP/1.1" 200 OK
```

The id in that line was a live capability: pasting it back into the same URL
returned the secret, because it had not yet been burned.

## After the fix

Round trip: create, reveal, then an attempt on the removed path-style route.

```
$ ID=$(curl -s -X POST localhost:8099/secrets \
       -H 'content-type: application/json' \
       -d '{"ciphertext":"evidence-envelope-for-aud6"}' | jq -r .payload_id)
$ echo $ID
KuU6lmFf8l52JnfR-XdrSon3C5b2MYDms4UAJQBW_oA

$ curl -s -X POST localhost:8099/secrets/reveal \
       -H 'content-type: application/json' -d "{\"payload_id\":\"$ID\"}"
{"ciphertext":"evidence-envelope-for-aud6"}

$ curl -s -o /dev/null -w '%{http_code}\n' "localhost:8099/secrets/$ID"
404
```

Captured server log for those three requests:

```
INFO:     127.0.0.1:32918 - "GET /health HTTP/1.1" 200 OK
INFO:     127.0.0.1:57054 - "POST /secrets HTTP/1.1" 201 Created
INFO:     127.0.0.1:57068 - "POST /secrets/reveal HTTP/1.1" 200 OK
INFO:     127.0.0.1:57084 - "GET /secrets/<redacted> HTTP/1.1" 404 Not Found
```

```
$ grep -c "$ID" uvicorn.log
0
```

Two things are visible here:

1. The reveal request line carries no id at all — it is `POST /secrets/reveal`,
   with the id in the request body. This is the primary control.
2. The deliberate attempt on the old `GET /secrets/<id>` shape was logged as
   `/secrets/<redacted>`, so even a stale bookmarked link cannot write an id to
   the log. This is `RedactSecretPaths`, the defence-in-depth layer.

The id never appears in the log: `grep -c` returns 0 for the full 43-character
value that the reveal call demonstrably accepted.

## Automated equivalent

`api/tests/security/test_access_log.py` asserts the same two properties without
needing a live server, so a regression fails CI rather than waiting for the next
manual capture.
