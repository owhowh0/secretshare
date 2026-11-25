# SecretShare - ZAP passive scan

ZAP by [Checkmarx](https://checkmarx.com/).


## Summary of Alerts

| Risk Level | Number of Alerts |
| --- | --- |
| High | 0 |
| Medium | 7 |
| Low | 7 |
| Informational | 8 |




## Insights

| Level | Reason | Site | Description | Statistic |
| --- | --- | --- | --- | --- |
| Low | Warning |  | ZAP warnings logged - see the zap.log file for details | 100    |
| Info | Informational | http://localhost | Percentage of responses with status code 2xx | 70 % |
| Info | Informational | http://localhost | Percentage of responses with status code 3xx | 13 % |
| Info | Informational | http://localhost | Percentage of responses with status code 4xx | 15 % |
| Info | Informational | http://localhost | Percentage of responses with status code 5xx | 1 % |
| Info | Informational | http://localhost | Percentage of endpoints with content type application/javascript | 7 % |
| Info | Informational | http://localhost | Percentage of endpoints with content type application/json | 20 % |
| Info | Informational | http://localhost | Percentage of endpoints with content type application/octet-stream | 13 % |
| Info | Informational | http://localhost | Percentage of endpoints with content type font/woff2 | 2 % |
| Info | Informational | http://localhost | Percentage of endpoints with content type image/png | 2 % |
| Info | Informational | http://localhost | Percentage of endpoints with content type image/svg+xml | 1 % |
| Info | Informational | http://localhost | Percentage of endpoints with content type text/css | 4 % |
| Info | Informational | http://localhost | Percentage of endpoints with content type text/html | 13 % |
| Info | Informational | http://localhost | Percentage of endpoints with content type text/javascript | 3 % |
| Info | Informational | http://localhost | Percentage of endpoints with content type text/plain | 6 % |
| Info | Informational | http://localhost | Percentage of endpoints with content type text/x-component | 2 % |
| Info | Informational | http://localhost | Percentage of endpoints with method GET | 92 % |
| Info | Informational | http://localhost | Percentage of endpoints with method POST | 7 % |
| Info | Informational | http://localhost | Count of total endpoints | 139    |
| Info | Informational | http://localhost | Percentage of slow responses | 12 % |
| Info | Informational | https://cdn.jsdelivr.net | Percentage of responses with status code 2xx | 100 % |
| Info | Informational | https://cdn.jsdelivr.net | Percentage of endpoints with content type application/javascript | 50 % |
| Info | Informational | https://cdn.jsdelivr.net | Percentage of endpoints with content type text/css | 50 % |
| Info | Informational | https://cdn.jsdelivr.net | Percentage of endpoints with method GET | 100 % |
| Info | Informational | https://cdn.jsdelivr.net | Count of total endpoints | 2    |
| Info | Informational | https://cdn.jsdelivr.net | Percentage of slow responses | 100 % |







## Alerts

| Name | Risk Level | Number of Instances |
| --- | --- | --- |
| Absence of Anti-CSRF Tokens | Medium | Systemic |
| CSP: Failure to Define Directive with No Fallback | Medium | Systemic |
| CSP: Wildcard Directive | Medium | 5 |
| CSP: script-src unsafe-inline | Medium | Systemic |
| CSP: style-src unsafe-inline | Medium | Systemic |
| Content Security Policy (CSP) Header Not Set | Medium | 1 |
| Sub Resource Integrity Attribute Missing | Medium | 2 |
| Application Error Disclosure | Low | 2 |
| Cookie No HttpOnly Flag | Low | 2 |
| Cookie with SameSite Attribute None | Low | 4 |
| Cookie without SameSite Attribute | Low | 1 |
| Cross-Domain JavaScript Source File Inclusion | Low | 1 |
| Information Disclosure - Debug Error Messages | Low | 1 |
| Server Leaks Information via "X-Powered-By" HTTP Response Header Field(s) | Low | Systemic |
| Authentication Request Identified | Informational | 1 |
| Content-Type Header Missing | Informational | Systemic |
| Cookie Poisoning | Informational | 1 |
| Information Disclosure - Sensitive Information in URL | Informational | 4 |
| Information Disclosure - Suspicious Comments | Informational | 2 |
| Modern Web Application | Informational | Systemic |
| Session Management Response Identified | Informational | 10 |
| User Controllable HTML Element Attribute (Potential XSS) | Informational | 1 |




## Alert Detail



### [ Absence of Anti-CSRF Tokens ](https://www.zaproxy.org/docs/alerts/10202/)



##### Medium (Low)

### Description

No Anti-CSRF tokens were found in a HTML submission form.
A cross-site request forgery is an attack that involves forcing a victim to send an HTTP request to a target destination without their knowledge or intent in order to perform an action as the victim. The underlying cause is application functionality using predictable URL/form actions in a repeatable way. The nature of the attack is that CSRF exploits the trust that a web site has for a user. By contrast, cross-site scripting (XSS) exploits the trust that a user has for a web site. Like XSS, CSRF attacks are not necessarily cross-site, but they can be. Cross-site request forgery is also known as CSRF, XSRF, one-click attack, session riding, confused deputy, and sea surf.

CSRF attacks are effective in a number of situations, including:
    * The victim has an active session on the target site.
    * The victim is authenticated via HTTP auth on the target site.
    * The victim is on the same local network as the target site.

CSRF has primarily been used to perform an action against a target site using the victim's privileges, but recent techniques have been discovered to disclose information by gaining access to the response. The risk of information disclosure is dramatically increased when the target site is vulnerable to XSS, because XSS can be used as a platform for CSRF, allowing the attack to operate within the bounds of the same-origin policy.

* URL: http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth%3Fresponse_type=code&client_id=secretshare-api&redirect_uri=http%253A%252F%252Flocalhost%252Fapi%252Fauth%252Fcallback%252Fkeycloak&code_challenge=H41YvXbxcSkBi_QdYt1r1LIt_ZeaFRHdn49N5ThWLcQ&code_challenge_method=S256&scope=openid+profile+email
  * Node Name: `http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth (client_id,code_challenge,code_challenge_method,redirect_uri,response_type,scope)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `<form id="kc-form-login" class="pf-v5-c-form" onsubmit="login.disabled = true; return true;" action="http://localhost/keycloak/realms/secretshare/login-actions/authenticate?session_code=9cjAadFj_Cw_qWwv3wbnqINELOih6aUkd1NCEYJzQ-A&amp;execution=d7e7ae34-dcf5-43c5-bec2-235bbd176dbc&amp;client_id=secretshare-api&amp;tab_id=SuzaWSFCmQk&amp;client_data=eyJydSI6Imh0dHA6Ly9sb2NhbGhvc3QvYXBpL2F1dGgvY2FsbGJhY2sva2V5Y2xvYWsiLCJydCI6ImNvZGUifQ" method="post" novalidate="novalidate">`
  * Other Info: `No known Anti-CSRF token [anticsrf, CSRFToken, __RequestVerificationToken, csrfmiddlewaretoken, authenticity_token, OWASP_CSRFTOKEN, anoncsrf, csrf_token, _csrf, _csrfSecret, __csrf_magic, CSRF, _token, _csrf_token, _csrfToken] was found in the following HTML form: [Form 1: "id-hidden-input" "password" "username" ].`
* URL: http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth%3Fresponse_type=code&client_id=secretshare-api&redirect_uri=http%253A%252F%252Flocalhost%252Fapi%252Fauth%252Fcallback%252Fkeycloak&code_challenge=vKAi9JgAg_YXd7iugZ52L5qXNbQQHv2Q77xcmwKineA&code_challenge_method=S256&scope=openid+profile+email
  * Node Name: `http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth (client_id,code_challenge,code_challenge_method,redirect_uri,response_type,scope)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `<form id="kc-form-login" class="pf-v5-c-form" onsubmit="login.disabled = true; return true;" action="http://localhost/keycloak/realms/secretshare/login-actions/authenticate?session_code=JgPNCNJKiP5FhZeKh5INjP_o7N3eRiLFLi9yIhJQxpo&amp;execution=d7e7ae34-dcf5-43c5-bec2-235bbd176dbc&amp;client_id=secretshare-api&amp;tab_id=McpxvC9qFbg&amp;client_data=eyJydSI6Imh0dHA6Ly9sb2NhbGhvc3QvYXBpL2F1dGgvY2FsbGJhY2sva2V5Y2xvYWsiLCJydCI6ImNvZGUifQ" method="post" novalidate="novalidate">`
  * Other Info: `No known Anti-CSRF token [anticsrf, CSRFToken, __RequestVerificationToken, csrfmiddlewaretoken, authenticity_token, OWASP_CSRFTOKEN, anoncsrf, csrf_token, _csrf, _csrfSecret, __csrf_magic, CSRF, _token, _csrf_token, _csrfToken] was found in the following HTML form: [Form 1: "id-hidden-input" "password" "username" ].`
* URL: http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth%3Fresponse_type=code&client_id=secretshare-api&redirect_uri=http%253A%252F%252Flocalhost%252Fapi%252Fauth%252Fcallback%252Fkeycloak&code_challenge=oxeu5quZK8PY72mCCgeTLpuiYjuy1t6fA8lvINvBlf4&code_challenge_method=S256&scope=openid+profile+email
  * Node Name: `http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth (client_id,code_challenge,code_challenge_method,redirect_uri,response_type,scope)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `<form id="kc-form-login" class="pf-v5-c-form" onsubmit="login.disabled = true; return true;" action="http://localhost/keycloak/realms/secretshare/login-actions/authenticate?session_code=ZNoHuMfG36SnERG9y7HtSfsMw3Pq9ldcJTbpRXvCukc&amp;execution=d7e7ae34-dcf5-43c5-bec2-235bbd176dbc&amp;client_id=secretshare-api&amp;tab_id=V5i8oXIUWJM&amp;client_data=eyJydSI6Imh0dHA6Ly9sb2NhbGhvc3QvYXBpL2F1dGgvY2FsbGJhY2sva2V5Y2xvYWsiLCJydCI6ImNvZGUifQ" method="post" novalidate="novalidate">`
  * Other Info: `No known Anti-CSRF token [anticsrf, CSRFToken, __RequestVerificationToken, csrfmiddlewaretoken, authenticity_token, OWASP_CSRFTOKEN, anoncsrf, csrf_token, _csrf, _csrfSecret, __csrf_magic, CSRF, _token, _csrf_token, _csrfToken] was found in the following HTML form: [Form 1: "id-hidden-input" "password" "username" ].`
* URL: http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth%3Fresponse_type=code&client_id=secretshare-api&redirect_uri=http%253A%252F%252Flocalhost%252Fapi%252Fauth%252Fcallback%252Fkeycloak&code_challenge=H41YvXbxcSkBi_QdYt1r1LIt_ZeaFRHdn49N5ThWLcQ&code_challenge_method=S256&scope=openid+profile+email
  * Node Name: `http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth (client_id,code_challenge,code_challenge_method,redirect_uri,response_type,scope)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `<form id="kc-form-login" class="pf-v5-c-form" onsubmit="login.disabled = true; return true;" action="http://localhost/keycloak/realms/secretshare/login-actions/authenticate?session_code=sedylghQJnmDfDvM_4WFzfVweE1xOx2EVynlkRxSK0w&amp;execution=d7e7ae34-dcf5-43c5-bec2-235bbd176dbc&amp;client_id=secretshare-api&amp;tab_id=p0ky3FRdUWY&amp;client_data=eyJydSI6Imh0dHA6Ly9sb2NhbGhvc3QvYXBpL2F1dGgvY2FsbGJhY2sva2V5Y2xvYWsiLCJydCI6ImNvZGUifQ" method="post" novalidate="novalidate">`
  * Other Info: `No known Anti-CSRF token [anticsrf, CSRFToken, __RequestVerificationToken, csrfmiddlewaretoken, authenticity_token, OWASP_CSRFTOKEN, anoncsrf, csrf_token, _csrf, _csrfSecret, __csrf_magic, CSRF, _token, _csrf_token, _csrfToken] was found in the following HTML form: [Form 1: "id-hidden-input" "password" "username" ].`
* URL: http://localhost/keycloak/realms/secretshare/login-actions/authenticate%3Fsession_code=ZNoHuMfG36SnERG9y7HtSfsMw3Pq9ldcJTbpRXvCukc&execution=d7e7ae34-dcf5-43c5-bec2-235bbd176dbc&client_id=secretshare-api&tab_id=V5i8oXIUWJM&client_data=eyJydSI6Imh0dHA6Ly9sb2NhbGhvc3QvYXBpL2F1dGgvY2FsbGJhY2sva2V5Y2xvYWsiLCJydCI6ImNvZGUifQ
  * Node Name: `http://localhost/keycloak/realms/secretshare/login-actions/authenticate (client_data,client_id,execution,session_code,tab_id)(credentialId,password,username)`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `<form id="kc-form-login" class="pf-v5-c-form" onsubmit="login.disabled = true; return true;" action="http://localhost/keycloak/realms/secretshare/login-actions/authenticate?session_code=_bBI0IUa1Y_l6vHJhHeS1pwxCyqGclkIm4pX11uIOFs&amp;execution=d7e7ae34-dcf5-43c5-bec2-235bbd176dbc&amp;client_id=secretshare-api&amp;tab_id=V5i8oXIUWJM&amp;client_data=eyJydSI6Imh0dHA6Ly9sb2NhbGhvc3QvYXBpL2F1dGgvY2FsbGJhY2sva2V5Y2xvYWsiLCJydCI6ImNvZGUifQ" method="post" novalidate="novalidate">`
  * Other Info: `No known Anti-CSRF token [anticsrf, CSRFToken, __RequestVerificationToken, csrfmiddlewaretoken, authenticity_token, OWASP_CSRFTOKEN, anoncsrf, csrf_token, _csrf, _csrfSecret, __csrf_magic, CSRF, _token, _csrf_token, _csrfToken] was found in the following HTML form: [Form 1: "id-hidden-input" "password" "username" ].`

Instances: Systemic


### Solution

Phase: Architecture and Design
Use a vetted library or framework that does not allow this weakness to occur or provides constructs that make this weakness easier to avoid.
For example, use anti-CSRF packages such as the OWASP CSRFGuard.

Phase: Implementation
Ensure that your application is free of cross-site scripting issues, because most CSRF defenses can be bypassed using attacker-controlled script.

Phase: Architecture and Design
Generate a unique nonce for each form, place the nonce into the form, and verify the nonce upon receipt of the form. Be sure that the nonce is not predictable (CWE-330).
Note that this can be bypassed using XSS.

Identify especially dangerous operations. When the user performs a dangerous operation, send a separate confirmation request to ensure that the user intended to perform that operation.
Note that this can be bypassed using XSS.

Use the ESAPI Session Management control.
This control includes a component for CSRF.

Do not use the GET method for any request that triggers a state change.

Phase: Implementation
Check the HTTP Referer header to see if the request originated from an expected page. This could break legitimate functionality, because users or proxies may have disabled sending the Referer for privacy reasons.

### Reference


* [ https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html ](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
* [ https://cwe.mitre.org/data/definitions/352.html ](https://cwe.mitre.org/data/definitions/352.html)


#### CWE Id: [ 352 ](https://cwe.mitre.org/data/definitions/352.html)


#### WASC Id: 9

#### Source ID: 3

### [ CSP: Failure to Define Directive with No Fallback ](https://www.zaproxy.org/docs/alerts/10055/)



##### Medium (High)

### Description

The Content Security Policy fails to define one of the directives that has no fallback. Missing/excluding them is the same as allowing anything.

* URL: http://localhost/api/docs
  * Node Name: `http://localhost/api/docs`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; connect-src 'self'; frame-ancestors 'none'`
  * Other Info: `The directive(s): form-action, base-uri is/are among the directives that do not fallback to default-src.`
* URL: http://localhost/keycloak/realms/secretshare/account
  * Node Name: `http://localhost/keycloak/realms/secretshare/account`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `frame-src 'self'; frame-ancestors 'self'; object-src 'none';`
  * Other Info: `The directive(s): form-action, base-uri is/are among the directives that do not fallback to default-src.`
* URL: http://localhost/keycloak/realms/secretshare/login-actions/authenticate%3Fsession_code=sedylghQJnmDfDvM_4WFzfVweE1xOx2EVynlkRxSK0w&execution=d7e7ae34-dcf5-43c5-bec2-235bbd176dbc&client_id=secretshare-api&tab_id=p0ky3FRdUWY&client_data=eyJydSI6Imh0dHA6Ly9sb2NhbGhvc3QvYXBpL2F1dGgvY2FsbGJhY2sva2V5Y2xvYWsiLCJydCI6ImNvZGUifQ
  * Node Name: `http://localhost/keycloak/realms/secretshare/login-actions/authenticate (client_data,client_id,execution,session_code,tab_id)`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `frame-src 'self'; frame-ancestors 'self'; object-src 'none';`
  * Other Info: `The directive(s): form-action, base-uri is/are among the directives that do not fallback to default-src.`
* URL: http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth%3Fresponse_type=code&client_id=secretshare-api&redirect_uri=http%253A%252F%252Flocalhost%252Fapi%252Fauth%252Fcallback%252Fkeycloak&code_challenge=H41YvXbxcSkBi_QdYt1r1LIt_ZeaFRHdn49N5ThWLcQ&code_challenge_method=S256&scope=openid+profile+email
  * Node Name: `http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth (client_id,code_challenge,code_challenge_method,redirect_uri,response_type,scope)`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `frame-src 'self'; frame-ancestors 'self'; object-src 'none';`
  * Other Info: `The directive(s): form-action, base-uri is/are among the directives that do not fallback to default-src.`
* URL: http://localhost/keycloak/realms/secretshare/login-actions/authenticate%3Fclient_data=eyJydSI6Imh0dHA6Ly9sb2NhbGhvc3QvYXBpL2F1dGgvY2FsbGJhY2sva2V5Y2xvYWsiLCJydCI6ImNvZGUifQ&client_id=secretshare-api&execution=d7e7ae34-dcf5-43c5-bec2-235bbd176dbc&session_code=9cjAadFj_Cw_qWwv3wbnqINELOih6aUkd1NCEYJzQ-A&tab_id=SuzaWSFCmQk
  * Node Name: `http://localhost/keycloak/realms/secretshare/login-actions/authenticate (client_data,client_id,execution,session_code,tab_id)(credentialId,password,username)`
  * Method: `POST`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `frame-src 'self'; frame-ancestors 'self'; object-src 'none';`
  * Other Info: `The directive(s): form-action, base-uri is/are among the directives that do not fallback to default-src.`

Instances: Systemic


### Solution

Ensure that your web server, application server, load balancer, etc. is properly configured to set the Content-Security-Policy header.

### Reference


* [ https://www.w3.org/TR/CSP/ ](https://www.w3.org/TR/CSP/)
* [ https://caniuse.com/#search=content+security+policy ](https://caniuse.com/#search=content+security+policy)
* [ https://content-security-policy.com/ ](https://content-security-policy.com/)
* [ https://github.com/HtmlUnit/htmlunit-csp ](https://github.com/HtmlUnit/htmlunit-csp)
* [ https://web.dev/articles/csp#resource-options ](https://web.dev/articles/csp#resource-options)


#### CWE Id: [ 693 ](https://cwe.mitre.org/data/definitions/693.html)


#### WASC Id: 15

#### Source ID: 3

### [ CSP: Wildcard Directive ](https://www.zaproxy.org/docs/alerts/10055/)



##### Medium (High)

### Description

Content Security Policy (CSP) is an added layer of security that helps to detect and mitigate certain types of attacks. Including (but not limited to) Cross Site Scripting (XSS), and data injection attacks. These attacks are used for everything from data theft to site defacement or distribution of malware. CSP provides a set of standard HTTP headers that allow website owners to declare approved sources of content that browsers should be allowed to load on that page — covered types are JavaScript, CSS, HTML frames, fonts, images and embeddable objects such as Java applets, ActiveX, audio and video files.

* URL: http://localhost/keycloak/
  * Node Name: `http://localhost/keycloak/`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `frame-src 'self'; frame-ancestors 'self'; object-src 'none';`
  * Other Info: `The following directives either allow wildcard sources (or ancestors), are not defined, or are overly broadly defined:
script-src, style-src, img-src, connect-src, font-src, media-src, manifest-src, worker-src`
* URL: http://localhost/keycloak/realms/secretshare/account
  * Node Name: `http://localhost/keycloak/realms/secretshare/account`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `frame-src 'self'; frame-ancestors 'self'; object-src 'none';`
  * Other Info: `The following directives either allow wildcard sources (or ancestors), are not defined, or are overly broadly defined:
script-src, style-src, img-src, connect-src, font-src, media-src, manifest-src, worker-src`
* URL: http://localhost/keycloak/realms/secretshare/login-actions/authenticate%3Fsession_code=sedylghQJnmDfDvM_4WFzfVweE1xOx2EVynlkRxSK0w&execution=d7e7ae34-dcf5-43c5-bec2-235bbd176dbc&client_id=secretshare-api&tab_id=p0ky3FRdUWY&client_data=eyJydSI6Imh0dHA6Ly9sb2NhbGhvc3QvYXBpL2F1dGgvY2FsbGJhY2sva2V5Y2xvYWsiLCJydCI6ImNvZGUifQ
  * Node Name: `http://localhost/keycloak/realms/secretshare/login-actions/authenticate (client_data,client_id,execution,session_code,tab_id)`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `frame-src 'self'; frame-ancestors 'self'; object-src 'none';`
  * Other Info: `The following directives either allow wildcard sources (or ancestors), are not defined, or are overly broadly defined:
script-src, style-src, img-src, connect-src, font-src, media-src, manifest-src, worker-src`
* URL: http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth%3Fresponse_type=code&client_id=secretshare-api&redirect_uri=http%253A%252F%252Flocalhost%252Fapi%252Fauth%252Fcallback%252Fkeycloak&code_challenge=H41YvXbxcSkBi_QdYt1r1LIt_ZeaFRHdn49N5ThWLcQ&code_challenge_method=S256&scope=openid+profile+email
  * Node Name: `http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth (client_id,code_challenge,code_challenge_method,redirect_uri,response_type,scope)`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `frame-src 'self'; frame-ancestors 'self'; object-src 'none';`
  * Other Info: `The following directives either allow wildcard sources (or ancestors), are not defined, or are overly broadly defined:
script-src, style-src, img-src, connect-src, font-src, media-src, manifest-src, worker-src`
* URL: http://localhost/keycloak/realms/secretshare/login-actions/authenticate%3Fclient_data=eyJydSI6Imh0dHA6Ly9sb2NhbGhvc3QvYXBpL2F1dGgvY2FsbGJhY2sva2V5Y2xvYWsiLCJydCI6ImNvZGUifQ&client_id=secretshare-api&execution=d7e7ae34-dcf5-43c5-bec2-235bbd176dbc&session_code=9cjAadFj_Cw_qWwv3wbnqINELOih6aUkd1NCEYJzQ-A&tab_id=SuzaWSFCmQk
  * Node Name: `http://localhost/keycloak/realms/secretshare/login-actions/authenticate (client_data,client_id,execution,session_code,tab_id)(credentialId,password,username)`
  * Method: `POST`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `frame-src 'self'; frame-ancestors 'self'; object-src 'none';`
  * Other Info: `The following directives either allow wildcard sources (or ancestors), are not defined, or are overly broadly defined:
script-src, style-src, img-src, connect-src, font-src, media-src, manifest-src, worker-src`


Instances: 5

### Solution

Ensure that your web server, application server, load balancer, etc. is properly configured to set the Content-Security-Policy header.

### Reference


* [ https://www.w3.org/TR/CSP/ ](https://www.w3.org/TR/CSP/)
* [ https://caniuse.com/#search=content+security+policy ](https://caniuse.com/#search=content+security+policy)
* [ https://content-security-policy.com/ ](https://content-security-policy.com/)
* [ https://github.com/HtmlUnit/htmlunit-csp ](https://github.com/HtmlUnit/htmlunit-csp)
* [ https://web.dev/articles/csp#resource-options ](https://web.dev/articles/csp#resource-options)


#### CWE Id: [ 693 ](https://cwe.mitre.org/data/definitions/693.html)


#### WASC Id: 15

#### Source ID: 3

### [ CSP: script-src unsafe-inline ](https://www.zaproxy.org/docs/alerts/10055/)



##### Medium (High)

### Description

Content Security Policy (CSP) is an added layer of security that helps to detect and mitigate certain types of attacks. Including (but not limited to) Cross Site Scripting (XSS), and data injection attacks. These attacks are used for everything from data theft to site defacement or distribution of malware. CSP provides a set of standard HTTP headers that allow website owners to declare approved sources of content that browsers should be allowed to load on that page — covered types are JavaScript, CSS, HTML frames, fonts, images and embeddable objects such as Java applets, ActiveX, audio and video files.

* URL: http://localhost/api/docs
  * Node Name: `http://localhost/api/docs`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; connect-src 'self'; frame-ancestors 'none'`
  * Other Info: `script-src includes unsafe-inline.`
* URL: http://localhost/keycloak/realms/secretshare/account
  * Node Name: `http://localhost/keycloak/realms/secretshare/account`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `frame-src 'self'; frame-ancestors 'self'; object-src 'none';`
  * Other Info: `script-src includes unsafe-inline.`
* URL: http://localhost/keycloak/realms/secretshare/login-actions/authenticate%3Fsession_code=sedylghQJnmDfDvM_4WFzfVweE1xOx2EVynlkRxSK0w&execution=d7e7ae34-dcf5-43c5-bec2-235bbd176dbc&client_id=secretshare-api&tab_id=p0ky3FRdUWY&client_data=eyJydSI6Imh0dHA6Ly9sb2NhbGhvc3QvYXBpL2F1dGgvY2FsbGJhY2sva2V5Y2xvYWsiLCJydCI6ImNvZGUifQ
  * Node Name: `http://localhost/keycloak/realms/secretshare/login-actions/authenticate (client_data,client_id,execution,session_code,tab_id)`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `frame-src 'self'; frame-ancestors 'self'; object-src 'none';`
  * Other Info: `script-src includes unsafe-inline.`
* URL: http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth%3Fresponse_type=code&client_id=secretshare-api&redirect_uri=http%253A%252F%252Flocalhost%252Fapi%252Fauth%252Fcallback%252Fkeycloak&code_challenge=H41YvXbxcSkBi_QdYt1r1LIt_ZeaFRHdn49N5ThWLcQ&code_challenge_method=S256&scope=openid+profile+email
  * Node Name: `http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth (client_id,code_challenge,code_challenge_method,redirect_uri,response_type,scope)`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `frame-src 'self'; frame-ancestors 'self'; object-src 'none';`
  * Other Info: `script-src includes unsafe-inline.`
* URL: http://localhost/keycloak/realms/secretshare/login-actions/authenticate%3Fclient_data=eyJydSI6Imh0dHA6Ly9sb2NhbGhvc3QvYXBpL2F1dGgvY2FsbGJhY2sva2V5Y2xvYWsiLCJydCI6ImNvZGUifQ&client_id=secretshare-api&execution=d7e7ae34-dcf5-43c5-bec2-235bbd176dbc&session_code=9cjAadFj_Cw_qWwv3wbnqINELOih6aUkd1NCEYJzQ-A&tab_id=SuzaWSFCmQk
  * Node Name: `http://localhost/keycloak/realms/secretshare/login-actions/authenticate (client_data,client_id,execution,session_code,tab_id)(credentialId,password,username)`
  * Method: `POST`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `frame-src 'self'; frame-ancestors 'self'; object-src 'none';`
  * Other Info: `script-src includes unsafe-inline.`

Instances: Systemic


### Solution

Ensure that your web server, application server, load balancer, etc. is properly configured to set the Content-Security-Policy header.

### Reference


* [ https://www.w3.org/TR/CSP/ ](https://www.w3.org/TR/CSP/)
* [ https://caniuse.com/#search=content+security+policy ](https://caniuse.com/#search=content+security+policy)
* [ https://content-security-policy.com/ ](https://content-security-policy.com/)
* [ https://github.com/HtmlUnit/htmlunit-csp ](https://github.com/HtmlUnit/htmlunit-csp)
* [ https://web.dev/articles/csp#resource-options ](https://web.dev/articles/csp#resource-options)


#### CWE Id: [ 693 ](https://cwe.mitre.org/data/definitions/693.html)


#### WASC Id: 15

#### Source ID: 3

### [ CSP: style-src unsafe-inline ](https://www.zaproxy.org/docs/alerts/10055/)



##### Medium (High)

### Description

Content Security Policy (CSP) is an added layer of security that helps to detect and mitigate certain types of attacks. Including (but not limited to) Cross Site Scripting (XSS), and data injection attacks. These attacks are used for everything from data theft to site defacement or distribution of malware. CSP provides a set of standard HTTP headers that allow website owners to declare approved sources of content that browsers should be allowed to load on that page — covered types are JavaScript, CSS, HTML frames, fonts, images and embeddable objects such as Java applets, ActiveX, audio and video files.

* URL: http://localhost/
  * Node Name: `http://localhost/`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `default-src 'self'; script-src 'self' 'nonce-5fd8eeed81c74be8a7aa21ebab7a93fb' 'strict-dynamic'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'`
  * Other Info: `style-src includes unsafe-inline.`
* URL: http://localhost/
  * Node Name: `http://localhost/`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `default-src 'self'; script-src 'self' 'nonce-e95987edb77242f9a48783dec74c3661' 'strict-dynamic'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'`
  * Other Info: `style-src includes unsafe-inline.`
* URL: http://localhost/%3Fid=M4Slu3czC-EzjqIqOvCX6XfJbAy9rsc58OThsomArbE
  * Node Name: `http://localhost/ (id)`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `default-src 'self'; script-src 'self' 'nonce-0584a70d7e904be58c6d9a95710bd86a' 'strict-dynamic'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'`
  * Other Info: `style-src includes unsafe-inline.`
* URL: http://localhost/%3Fid=M4Slu3czC-EzjqIqOvCX6XfJbAy9rsc58OThsomArbE
  * Node Name: `http://localhost/ (id)`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `default-src 'self'; script-src 'self' 'nonce-eed6a345673d4403b86d42ca5f7ae193' 'strict-dynamic'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'`
  * Other Info: `style-src includes unsafe-inline.`
* URL: http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth%3Fresponse_type=code&client_id=secretshare-api&redirect_uri=http%253A%252F%252Flocalhost%252Fapi%252Fauth%252Fcallback%252Fkeycloak&code_challenge=H41YvXbxcSkBi_QdYt1r1LIt_ZeaFRHdn49N5ThWLcQ&code_challenge_method=S256&scope=openid+profile+email
  * Node Name: `http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth (client_id,code_challenge,code_challenge_method,redirect_uri,response_type,scope)`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `frame-src 'self'; frame-ancestors 'self'; object-src 'none';`
  * Other Info: `style-src includes unsafe-inline.`

Instances: Systemic


### Solution

Ensure that your web server, application server, load balancer, etc. is properly configured to set the Content-Security-Policy header.

### Reference


* [ https://www.w3.org/TR/CSP/ ](https://www.w3.org/TR/CSP/)
* [ https://caniuse.com/#search=content+security+policy ](https://caniuse.com/#search=content+security+policy)
* [ https://content-security-policy.com/ ](https://content-security-policy.com/)
* [ https://github.com/HtmlUnit/htmlunit-csp ](https://github.com/HtmlUnit/htmlunit-csp)
* [ https://web.dev/articles/csp#resource-options ](https://web.dev/articles/csp#resource-options)


#### CWE Id: [ 693 ](https://cwe.mitre.org/data/definitions/693.html)


#### WASC Id: 15

#### Source ID: 3

### [ Content Security Policy (CSP) Header Not Set ](https://www.zaproxy.org/docs/alerts/10038/)



##### Medium (High)

### Description

Content Security Policy (CSP) is an added layer of security that helps to detect and mitigate certain types of attacks, including Cross Site Scripting (XSS) and data injection attacks. These attacks are used for everything from data theft to site defacement or distribution of malware. CSP provides a set of standard HTTP headers that allow website owners to declare approved sources of content that browsers should be allowed to load on that page — covered types are JavaScript, CSS, HTML frames, fonts, images and embeddable objects such as Java applets, ActiveX, audio and video files.

* URL: http://localhost/favicon.ico
  * Node Name: `http://localhost/favicon.ico`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: ``
  * Other Info: ``


Instances: 1

### Solution

Ensure that your web server, application server, load balancer, etc. is configured to set the Content-Security-Policy header.

### Reference


* [ https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CSP ](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CSP)
* [ https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html ](https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html)
* [ https://www.w3.org/TR/CSP/ ](https://www.w3.org/TR/CSP/)
* [ https://w3c.github.io/webappsec-csp/ ](https://w3c.github.io/webappsec-csp/)
* [ https://web.dev/articles/csp ](https://web.dev/articles/csp)
* [ https://caniuse.com/#feat=contentsecuritypolicy ](https://caniuse.com/#feat=contentsecuritypolicy)
* [ https://content-security-policy.com/ ](https://content-security-policy.com/)


#### CWE Id: [ 693 ](https://cwe.mitre.org/data/definitions/693.html)


#### WASC Id: 15

#### Source ID: 3

### [ Sub Resource Integrity Attribute Missing ](https://www.zaproxy.org/docs/alerts/90003/)



##### Medium (High)

### Description

The integrity attribute is missing on a script or link tag served by an external server. The integrity tag prevents an attacker who have gained access to this server from injecting a malicious content.

* URL: http://localhost/api/docs
  * Node Name: `http://localhost/api/docs`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `<link type="text/css" rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">`
  * Other Info: ``
* URL: http://localhost/api/docs
  * Node Name: `http://localhost/api/docs`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>`
  * Other Info: ``


Instances: 2

### Solution

Provide a valid integrity attribute to the tag.

### Reference


* [ https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Subresource_Integrity ](https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Subresource_Integrity)


#### CWE Id: [ 345 ](https://cwe.mitre.org/data/definitions/345.html)


#### WASC Id: 15

#### Source ID: 3

### [ Application Error Disclosure ](https://www.zaproxy.org/docs/alerts/90022/)



##### Low (Medium)

### Description

This page contains an error/warning message that may disclose sensitive information like the location of the file that produced the unhandled exception. This information can be used to launch further attacks against the web application. The alert could be a false positive if the error message is found inside a documentation page.

* URL: http://localhost/api/auth/error/%3Ferror=Configuration
  * Node Name: `http://localhost/api/auth/error/ (error)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `HTTP/1.1 500 Internal Server Error`
  * Other Info: ``
* URL: http://localhost/api/keys/register
  * Node Name: `http://localhost/api/keys/register ()({public_key,platform,label})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `HTTP/1.1 500 Internal Server Error`
  * Other Info: ``


Instances: 2

### Solution

Review the source code of this page. Implement custom error pages. Consider implementing a mechanism to provide a unique error reference/identifier to the client (browser) while logging the details on the server side and not exposing them to the user.

### Reference



#### CWE Id: [ 550 ](https://cwe.mitre.org/data/definitions/550.html)


#### WASC Id: 13

#### Source ID: 3

### [ Cookie No HttpOnly Flag ](https://www.zaproxy.org/docs/alerts/10010/)



##### Low (Medium)

### Description

A cookie has been set without the HttpOnly flag, which means that the cookie can be accessed by JavaScript. If a malicious script can be run on this page then the cookie will be accessible and can be transmitted to another site. If this is a session cookie then session hijacking may be possible.

* URL: http://localhost/keycloak/realms/secretshare/login-actions/authenticate%3Fsession_code=sedylghQJnmDfDvM_4WFzfVweE1xOx2EVynlkRxSK0w&execution=d7e7ae34-dcf5-43c5-bec2-235bbd176dbc&client_id=secretshare-api&tab_id=p0ky3FRdUWY&client_data=eyJydSI6Imh0dHA6Ly9sb2NhbGhvc3QvYXBpL2F1dGgvY2FsbGJhY2sva2V5Y2xvYWsiLCJydCI6ImNvZGUifQ
  * Node Name: `http://localhost/keycloak/realms/secretshare/login-actions/authenticate (client_data,client_id,execution,session_code,tab_id)(credentialId,password,username)`
  * Method: `POST`
  * Parameter: `KC_RESTART`
  * Attack: ``
  * Evidence: `Set-Cookie: KC_RESTART`
  * Other Info: ``
* URL: http://localhost/keycloak/realms/secretshare/login-actions/authenticate%3Fsession_code=sedylghQJnmDfDvM_4WFzfVweE1xOx2EVynlkRxSK0w&execution=d7e7ae34-dcf5-43c5-bec2-235bbd176dbc&client_id=secretshare-api&tab_id=p0ky3FRdUWY&client_data=eyJydSI6Imh0dHA6Ly9sb2NhbGhvc3QvYXBpL2F1dGgvY2FsbGJhY2sva2V5Y2xvYWsiLCJydCI6ImNvZGUifQ
  * Node Name: `http://localhost/keycloak/realms/secretshare/login-actions/authenticate (client_data,client_id,execution,session_code,tab_id)(credentialId,password,username)`
  * Method: `POST`
  * Parameter: `KEYCLOAK_SESSION`
  * Attack: ``
  * Evidence: `Set-Cookie: KEYCLOAK_SESSION`
  * Other Info: ``


Instances: 2

### Solution

Ensure that the HttpOnly flag is set for all cookies.

### Reference


* [ https://owasp.org/www-community/HttpOnly ](https://owasp.org/www-community/HttpOnly)


#### CWE Id: [ 1004 ](https://cwe.mitre.org/data/definitions/1004.html)


#### WASC Id: 13

#### Source ID: 3

### [ Cookie with SameSite Attribute None ](https://www.zaproxy.org/docs/alerts/10054/)



##### Low (Medium)

### Description

A cookie has been set with its SameSite attribute set to "none", which means that the cookie can be sent as a result of a 'cross-site' request. The SameSite attribute is an effective counter measure to cross-site request forgery, cross-site script inclusion, and timing attacks.

* URL: http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth%3Fresponse_type=code&client_id=secretshare-api&redirect_uri=http%253A%252F%252Flocalhost%252Fapi%252Fauth%252Fcallback%252Fkeycloak&code_challenge=H41YvXbxcSkBi_QdYt1r1LIt_ZeaFRHdn49N5ThWLcQ&code_challenge_method=S256&scope=openid+profile+email
  * Node Name: `http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth (client_id,code_challenge,code_challenge_method,redirect_uri,response_type,scope)`
  * Method: `GET`
  * Parameter: `AUTH_SESSION_ID`
  * Attack: ``
  * Evidence: `Set-Cookie: AUTH_SESSION_ID`
  * Other Info: ``
* URL: http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth%3Fresponse_type=code&client_id=secretshare-api&redirect_uri=http%253A%252F%252Flocalhost%252Fapi%252Fauth%252Fcallback%252Fkeycloak&code_challenge=H41YvXbxcSkBi_QdYt1r1LIt_ZeaFRHdn49N5ThWLcQ&code_challenge_method=S256&scope=openid+profile+email
  * Node Name: `http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth (client_id,code_challenge,code_challenge_method,redirect_uri,response_type,scope)`
  * Method: `GET`
  * Parameter: `KC_RESTART`
  * Attack: ``
  * Evidence: `Set-Cookie: KC_RESTART`
  * Other Info: ``
* URL: http://localhost/keycloak/realms/secretshare/login-actions/authenticate%3Fsession_code=sedylghQJnmDfDvM_4WFzfVweE1xOx2EVynlkRxSK0w&execution=d7e7ae34-dcf5-43c5-bec2-235bbd176dbc&client_id=secretshare-api&tab_id=p0ky3FRdUWY&client_data=eyJydSI6Imh0dHA6Ly9sb2NhbGhvc3QvYXBpL2F1dGgvY2FsbGJhY2sva2V5Y2xvYWsiLCJydCI6ImNvZGUifQ
  * Node Name: `http://localhost/keycloak/realms/secretshare/login-actions/authenticate (client_data,client_id,execution,session_code,tab_id)(credentialId,password,username)`
  * Method: `POST`
  * Parameter: `KEYCLOAK_IDENTITY`
  * Attack: ``
  * Evidence: `Set-Cookie: KEYCLOAK_IDENTITY`
  * Other Info: ``
* URL: http://localhost/keycloak/realms/secretshare/login-actions/authenticate%3Fsession_code=sedylghQJnmDfDvM_4WFzfVweE1xOx2EVynlkRxSK0w&execution=d7e7ae34-dcf5-43c5-bec2-235bbd176dbc&client_id=secretshare-api&tab_id=p0ky3FRdUWY&client_data=eyJydSI6Imh0dHA6Ly9sb2NhbGhvc3QvYXBpL2F1dGgvY2FsbGJhY2sva2V5Y2xvYWsiLCJydCI6ImNvZGUifQ
  * Node Name: `http://localhost/keycloak/realms/secretshare/login-actions/authenticate (client_data,client_id,execution,session_code,tab_id)(credentialId,password,username)`
  * Method: `POST`
  * Parameter: `KEYCLOAK_SESSION`
  * Attack: ``
  * Evidence: `Set-Cookie: KEYCLOAK_SESSION`
  * Other Info: ``


Instances: 4

### Solution

Ensure that the SameSite attribute is set to either 'lax' or ideally 'strict' for all cookies.

### Reference


* [ https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-cookie-same-site ](https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-cookie-same-site)


#### CWE Id: [ 1275 ](https://cwe.mitre.org/data/definitions/1275.html)


#### WASC Id: 13

#### Source ID: 3

### [ Cookie without SameSite Attribute ](https://www.zaproxy.org/docs/alerts/10054/)



##### Low (Medium)

### Description

A cookie has been set without the SameSite attribute, which means that the cookie can be sent as a result of a 'cross-site' request. The SameSite attribute is an effective counter measure to cross-site request forgery, cross-site script inclusion, and timing attacks.

* URL: http://localhost/keycloak/realms/secretshare/login-actions/authenticate%3Fsession_code=sedylghQJnmDfDvM_4WFzfVweE1xOx2EVynlkRxSK0w&execution=d7e7ae34-dcf5-43c5-bec2-235bbd176dbc&client_id=secretshare-api&tab_id=p0ky3FRdUWY&client_data=eyJydSI6Imh0dHA6Ly9sb2NhbGhvc3QvYXBpL2F1dGgvY2FsbGJhY2sva2V5Y2xvYWsiLCJydCI6ImNvZGUifQ
  * Node Name: `http://localhost/keycloak/realms/secretshare/login-actions/authenticate (client_data,client_id,execution,session_code,tab_id)(credentialId,password,username)`
  * Method: `POST`
  * Parameter: `KC_RESTART`
  * Attack: ``
  * Evidence: `Set-Cookie: KC_RESTART`
  * Other Info: ``


Instances: 1

### Solution

Ensure that the SameSite attribute is set to either 'lax' or ideally 'strict' for all cookies.

### Reference


* [ https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-cookie-same-site ](https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-cookie-same-site)


#### CWE Id: [ 1275 ](https://cwe.mitre.org/data/definitions/1275.html)


#### WASC Id: 13

#### Source ID: 3

### [ Cross-Domain JavaScript Source File Inclusion ](https://www.zaproxy.org/docs/alerts/10017/)



##### Low (Medium)

### Description

The page includes one or more script files from a third-party domain.

* URL: http://localhost/api/docs
  * Node Name: `http://localhost/api/docs`
  * Method: `GET`
  * Parameter: `https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js`
  * Attack: ``
  * Evidence: `<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>`
  * Other Info: ``


Instances: 1

### Solution

Ensure JavaScript source files are loaded from only trusted sources, and the sources can't be controlled by end users of the application.

### Reference



#### CWE Id: [ 829 ](https://cwe.mitre.org/data/definitions/829.html)


#### WASC Id: 15

#### Source ID: 3

### [ Information Disclosure - Debug Error Messages ](https://www.zaproxy.org/docs/alerts/10023/)



##### Low (Medium)

### Description

The response appeared to contain common error messages returned by platforms such as ASP.NET, and Web-servers such as IIS and Apache. You can configure the list of common debug messages.

* URL: http://localhost/api/keys/register
  * Node Name: `http://localhost/api/keys/register ()({public_key,platform,label})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `Internal server error`
  * Other Info: ``


Instances: 1

### Solution

Disable debugging messages before pushing to production.

### Reference



#### CWE Id: [ 1295 ](https://cwe.mitre.org/data/definitions/1295.html)


#### WASC Id: 13

#### Source ID: 3

### [ Server Leaks Information via "X-Powered-By" HTTP Response Header Field(s) ](https://www.zaproxy.org/docs/alerts/10037/)



##### Low (Medium)

### Description

The web/application server is leaking information via one or more "X-Powered-By" HTTP response headers. Access to such information may facilitate attackers identifying other frameworks/components your web application is reliant upon and the vulnerabilities such components may be subject to.

* URL: http://localhost/
  * Node Name: `http://localhost/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `X-Powered-By: Next.js`
  * Other Info: ``
* URL: http://localhost/%3Fid=M4Slu3czC-EzjqIqOvCX6XfJbAy9rsc58OThsomArbE
  * Node Name: `http://localhost/ (id)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `X-Powered-By: Next.js`
  * Other Info: ``
* URL: http://localhost/s/doesnotexist/
  * Node Name: `http://localhost/s/doesnotexist/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `X-Powered-By: Next.js`
  * Other Info: ``
* URL: http://localhost/secret/doesnotexist/
  * Node Name: `http://localhost/secret/doesnotexist/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `X-Powered-By: Next.js`
  * Other Info: ``
* URL: http://localhost/sitemap.xml
  * Node Name: `http://localhost/sitemap.xml`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `X-Powered-By: Next.js`
  * Other Info: ``

Instances: Systemic


### Solution

Ensure that your web server, application server, load balancer, etc. is configured to suppress "X-Powered-By" headers.

### Reference


* [ https://owasp.org/www-project-web-security-testing-guide/v42/4-Web_Application_Security_Testing/01-Information_Gathering/08-Fingerprint_Web_Application_Framework ](https://owasp.org/www-project-web-security-testing-guide/v42/4-Web_Application_Security_Testing/01-Information_Gathering/08-Fingerprint_Web_Application_Framework)
* [ https://www.troyhunt.com/shhh-dont-let-your-response-headers/ ](https://www.troyhunt.com/shhh-dont-let-your-response-headers/)


#### CWE Id: [ 497 ](https://cwe.mitre.org/data/definitions/497.html)


#### WASC Id: 13

#### Source ID: 3

### [ Authentication Request Identified ](https://www.zaproxy.org/docs/alerts/10111/)



##### Informational (High)

### Description

The given request has been identified as an authentication request. The 'Other Info' field contains a set of key=value lines which identify any relevant fields. If the request is in a context which has an Authentication Method set to "Auto-Detect" then this rule will change the authentication to match the request identified.

* URL: http://localhost/keycloak/realms/secretshare/login-actions/authenticate%3Fsession_code=sedylghQJnmDfDvM_4WFzfVweE1xOx2EVynlkRxSK0w&execution=d7e7ae34-dcf5-43c5-bec2-235bbd176dbc&client_id=secretshare-api&tab_id=p0ky3FRdUWY&client_data=eyJydSI6Imh0dHA6Ly9sb2NhbGhvc3QvYXBpL2F1dGgvY2FsbGJhY2sva2V5Y2xvYWsiLCJydCI6ImNvZGUifQ
  * Node Name: `http://localhost/keycloak/realms/secretshare/login-actions/authenticate (client_data,client_id,execution,session_code,tab_id)(credentialId,password,username)`
  * Method: `POST`
  * Parameter: `username`
  * Attack: ``
  * Evidence: `password`
  * Other Info: `userParam=username
userValue=testuser
passwordParam=password`


Instances: 1

### Solution

This is an informational alert rather than a vulnerability and so there is nothing to fix.

### Reference


* [ https://www.zaproxy.org/docs/desktop/addons/authentication-helper/auth-req-id/ ](https://www.zaproxy.org/docs/desktop/addons/authentication-helper/auth-req-id/)



#### Source ID: 3

### [ Content-Type Header Missing ](https://www.zaproxy.org/docs/alerts/10019/)



##### Informational (Medium)

### Description

The Content-Type header was either missing or empty.

* URL: http://localhost/api/auth/callback/keycloak%3Fsession_state=f63cb8e5-0f4d-48ff-8ac9-43dec596650e&iss=http%253A%252F%252Flocalhost%252Fkeycloak%252Frealms%252Fsecretshare&code=42992a47-5368-44a7-9ad4-5d3026cf6866.f63cb8e5-0f4d-48ff-8ac9-43dec596650e.fc71cbd6-b03b-46a7-b56b-62cd0370510d
  * Node Name: `http://localhost/api/auth/callback/keycloak (code,iss,session_state)`
  * Method: `GET`
  * Parameter: `content-type`
  * Attack: ``
  * Evidence: ``
  * Other Info: ``
* URL: http://localhost/api/auth/csrf
  * Node Name: `http://localhost/api/auth/csrf`
  * Method: `GET`
  * Parameter: `content-type`
  * Attack: ``
  * Evidence: ``
  * Other Info: ``
* URL: http://localhost/api/auth/providers
  * Node Name: `http://localhost/api/auth/providers`
  * Method: `GET`
  * Parameter: `content-type`
  * Attack: ``
  * Evidence: ``
  * Other Info: ``
* URL: http://localhost/api/auth/session
  * Node Name: `http://localhost/api/auth/session`
  * Method: `GET`
  * Parameter: `content-type`
  * Attack: ``
  * Evidence: ``
  * Other Info: ``
* URL: http://localhost/api/auth/signin/keycloak
  * Node Name: `http://localhost/api/auth/signin/keycloak ()(callbackUrl,csrfToken)`
  * Method: `POST`
  * Parameter: `content-type`
  * Attack: ``
  * Evidence: ``
  * Other Info: ``

Instances: Systemic


### Solution

Ensure each page is setting the specific and appropriate content-type value for the content being delivered.

### Reference


* [ https://learn.microsoft.com/en-us/previous-versions/windows/internet-explorer/ie-developer/compatibility/gg622941(v=vs.85) ](https://learn.microsoft.com/en-us/previous-versions/windows/internet-explorer/ie-developer/compatibility/gg622941(v=vs.85))


#### CWE Id: [ 345 ](https://cwe.mitre.org/data/definitions/345.html)


#### WASC Id: 12

#### Source ID: 3

### [ Cookie Poisoning ](https://www.zaproxy.org/docs/alerts/10029/)



##### Informational (Low)

### Description

This check looks at user-supplied input in query string parameters and POST data to identify where cookie parameters might be controlled. This is called a cookie poisoning attack, and becomes exploitable when an attacker can manipulate the cookie in various ways. In some cases this will not be exploitable, however, allowing URL parameters to set cookie values is generally considered a bug.

* URL: http://localhost/api/auth/signin/keycloak/
  * Node Name: `http://localhost/api/auth/signin/keycloak/ ()(callbackUrl,csrfToken)`
  * Method: `POST`
  * Parameter: `callbackUrl`
  * Attack: ``
  * Evidence: ``
  * Other Info: `An attacker may be able to poison cookie values through POST parameters. To test if this is a more serious issue, you should try resending that request as a GET, with the POST parameter included as a query string parameter. For example: https://nottrusted.com/page?value=maliciousInput.

This was identified at:

http://localhost/api/auth/signin/keycloak/

User-input was found in the following cookie:
authjs.callback-url=http://localhost/; Path=/; HttpOnly; SameSite=Lax

The user input was:
callbackUrl=http://localhost/`


Instances: 1

### Solution

Do not allow user input to control cookie names and values. If some query string parameters must be set in cookie values, be sure to filter out semicolon's that can serve as name/value pair delimiters.

### Reference


* [ https://en.wikipedia.org/wiki/HTTP_cookie ](https://en.wikipedia.org/wiki/HTTP_cookie)
* [ https://cwe.mitre.org/data/definitions/565.html ](https://cwe.mitre.org/data/definitions/565.html)


#### CWE Id: [ 565 ](https://cwe.mitre.org/data/definitions/565.html)


#### WASC Id: 20

#### Source ID: 3

### [ Information Disclosure - Sensitive Information in URL ](https://www.zaproxy.org/docs/alerts/10024/)



##### Informational (Medium)

### Description

The request appeared to contain sensitive information leaked in the URL. This can violate PCI and most organizational compliance policies. You can configure the list of strings for this check to add or remove values specific to your environment.

* URL: http://localhost/api/auth/callback/keycloak%3Fsession_state=f63cb8e5-0f4d-48ff-8ac9-43dec596650e&iss=http%253A%252F%252Flocalhost%252Fkeycloak%252Frealms%252Fsecretshare&code=42992a47-5368-44a7-9ad4-5d3026cf6866.f63cb8e5-0f4d-48ff-8ac9-43dec596650e.fc71cbd6-b03b-46a7-b56b-62cd0370510d
  * Node Name: `http://localhost/api/auth/callback/keycloak (code,iss,session_state)`
  * Method: `GET`
  * Parameter: `session_state`
  * Attack: ``
  * Evidence: `session_state`
  * Other Info: `The URL contains potentially sensitive information. The following string was found via the pattern: session
session_state`
* URL: http://localhost/api/auth/callback/keycloak/%3Fsession_state=f63cb8e5-0f4d-48ff-8ac9-43dec596650e&iss=http%253A%252F%252Flocalhost%252Fkeycloak%252Frealms%252Fsecretshare&code=42992a47-5368-44a7-9ad4-5d3026cf6866.f63cb8e5-0f4d-48ff-8ac9-43dec596650e.fc71cbd6-b03b-46a7-b56b-62cd0370510d
  * Node Name: `http://localhost/api/auth/callback/keycloak/ (code,iss,session_state)`
  * Method: `GET`
  * Parameter: `session_state`
  * Attack: ``
  * Evidence: `session_state`
  * Other Info: `The URL contains potentially sensitive information. The following string was found via the pattern: session
session_state`
* URL: http://localhost/keycloak/realms/secretshare/login-actions/authenticate%3Fsession_code=sedylghQJnmDfDvM_4WFzfVweE1xOx2EVynlkRxSK0w&execution=d7e7ae34-dcf5-43c5-bec2-235bbd176dbc&client_id=secretshare-api&tab_id=p0ky3FRdUWY&client_data=eyJydSI6Imh0dHA6Ly9sb2NhbGhvc3QvYXBpL2F1dGgvY2FsbGJhY2sva2V5Y2xvYWsiLCJydCI6ImNvZGUifQ
  * Node Name: `http://localhost/keycloak/realms/secretshare/login-actions/authenticate (client_data,client_id,execution,session_code,tab_id)`
  * Method: `GET`
  * Parameter: `session_code`
  * Attack: ``
  * Evidence: `session_code`
  * Other Info: `The URL contains potentially sensitive information. The following string was found via the pattern: session
session_code`
* URL: http://localhost/keycloak/realms/secretshare/login-actions/authenticate%3Fsession_code=sedylghQJnmDfDvM_4WFzfVweE1xOx2EVynlkRxSK0w&execution=d7e7ae34-dcf5-43c5-bec2-235bbd176dbc&client_id=secretshare-api&tab_id=p0ky3FRdUWY&client_data=eyJydSI6Imh0dHA6Ly9sb2NhbGhvc3QvYXBpL2F1dGgvY2FsbGJhY2sva2V5Y2xvYWsiLCJydCI6ImNvZGUifQ
  * Node Name: `http://localhost/keycloak/realms/secretshare/login-actions/authenticate (client_data,client_id,execution,session_code,tab_id)(credentialId,password,username)`
  * Method: `POST`
  * Parameter: `session_code`
  * Attack: ``
  * Evidence: `session_code`
  * Other Info: `The URL contains potentially sensitive information. The following string was found via the pattern: session
session_code`


Instances: 4

### Solution

Do not pass sensitive information in URIs.

### Reference



#### CWE Id: [ 598 ](https://cwe.mitre.org/data/definitions/598.html)


#### WASC Id: 13

#### Source ID: 3

### [ Information Disclosure - Suspicious Comments ](https://www.zaproxy.org/docs/alerts/10027/)



##### Informational (Medium)

### Description

The response appears to contain suspicious comments which may help an attacker.

* URL: http://localhost/keycloak/resources/7xiaz/login/keycloak.v2/js/authChecker.js
  * Node Name: `http://localhost/keycloak/resources/7xiaz/login/keycloak.v2/js/authChecker.js`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `// See: https://bugs.webkit.org/show_bug`
  * Other Info: `The following pattern was used: \bBUGS\b and was detected in likely comment: "// See: https://bugs.webkit.org/show_bug.cgi?id=219102", see evidence field for the suspicious comment/snippet.`
* URL: http://localhost/keycloak/resources/7xiaz/login/keycloak.v2/js/authChecker.js
  * Node Name: `http://localhost/keycloak/resources/7xiaz/login/keycloak.v2/js/authChecker.js`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `tected, check again later.`
  * Other Info: `The following pattern was used: \bLATER\b and was detected in likely comment: "// No new session detected, check again later.", see evidence field for the suspicious comment/snippet.`


Instances: 2

### Solution

Remove all comments that return information that may help an attacker and fix any underlying problems they refer to.

### Reference



#### CWE Id: [ 615 ](https://cwe.mitre.org/data/definitions/615.html)


#### WASC Id: 13

#### Source ID: 3

### [ Modern Web Application ](https://www.zaproxy.org/docs/alerts/10109/)



##### Informational (Medium)

### Description

The application appears to be a modern web application. If you need to explore it automatically then the Client Spider may well be more effective than the standard one.

* URL: http://localhost/
  * Node Name: `http://localhost/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `<script src="/_next/static/chunks/4bd1b696-c023c6e3521b1417.js" async="" nonce="5fd8eeed81c74be8a7aa21ebab7a93fb"></script>`
  * Other Info: `No links have been found while there are scripts, which is an indication that this is a modern web application.`
* URL: http://localhost/
  * Node Name: `http://localhost/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `<script src="/_next/static/chunks/4bd1b696-c023c6e3521b1417.js" async="" nonce="e95987edb77242f9a48783dec74c3661"></script>`
  * Other Info: `No links have been found while there are scripts, which is an indication that this is a modern web application.`
* URL: http://localhost/%3Fid=M4Slu3czC-EzjqIqOvCX6XfJbAy9rsc58OThsomArbE
  * Node Name: `http://localhost/ (id)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `<script src="/_next/static/chunks/4bd1b696-c023c6e3521b1417.js" async="" nonce="0584a70d7e904be58c6d9a95710bd86a"></script>`
  * Other Info: `No links have been found while there are scripts, which is an indication that this is a modern web application.`
* URL: http://localhost/%3Fid=M4Slu3czC-EzjqIqOvCX6XfJbAy9rsc58OThsomArbE
  * Node Name: `http://localhost/ (id)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `<script src="/_next/static/chunks/4bd1b696-c023c6e3521b1417.js" async="" nonce="eed6a345673d4403b86d42ca5f7ae193"></script>`
  * Other Info: `No links have been found while there are scripts, which is an indication that this is a modern web application.`
* URL: http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth%3Fresponse_type=code&client_id=secretshare-api&redirect_uri=http%253A%252F%252Flocalhost%252Fapi%252Fauth%252Fcallback%252Fkeycloak&code_challenge=H41YvXbxcSkBi_QdYt1r1LIt_ZeaFRHdn49N5ThWLcQ&code_challenge_method=S256&scope=openid+profile+email
  * Node Name: `http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth (client_id,code_challenge,code_challenge_method,redirect_uri,response_type,scope)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `<script type="importmap">
        {
            "imports": {
                "rfc4648": "/keycloak/resources/7xiaz/common/keycloak/vendor/rfc4648/rfc4648.js"
            }
        }
    </script>`
  * Other Info: `No links have been found while there are scripts, which is an indication that this is a modern web application.`

Instances: Systemic


### Solution

This is an informational alert and so no changes are required.

### Reference




#### Source ID: 3

### [ Session Management Response Identified ](https://www.zaproxy.org/docs/alerts/10112/)



##### Informational (Medium)

### Description

The given response has been identified as containing a session management token. The 'Other Info' field contains a set of header tokens that can be used in the Header Based Session Management Method. If the request is in a context which has a Session Management Method set to "Auto-Detect" then this rule will change the session management to use the tokens identified.

* URL: http://localhost/api/auth/callback/keycloak/%3Fsession_state=f63cb8e5-0f4d-48ff-8ac9-43dec596650e&iss=http%253A%252F%252Flocalhost%252Fkeycloak%252Frealms%252Fsecretshare&code=42992a47-5368-44a7-9ad4-5d3026cf6866.f63cb8e5-0f4d-48ff-8ac9-43dec596650e.fc71cbd6-b03b-46a7-b56b-62cd0370510d
  * Node Name: `http://localhost/api/auth/callback/keycloak/ (code,iss,session_state)`
  * Method: `GET`
  * Parameter: `authjs.session-token`
  * Attack: ``
  * Evidence: `authjs.session-token`
  * Other Info: `cookie:authjs.session-token`
* URL: http://localhost/api/auth/csrf/
  * Node Name: `http://localhost/api/auth/csrf/`
  * Method: `GET`
  * Parameter: `authjs.csrf-token`
  * Attack: ``
  * Evidence: `authjs.csrf-token`
  * Other Info: `cookie:authjs.csrf-token
cookie:authjs.callback-url`
* URL: http://localhost/api/auth/session/
  * Node Name: `http://localhost/api/auth/session/`
  * Method: `GET`
  * Parameter: `authjs.csrf-token`
  * Attack: ``
  * Evidence: `authjs.csrf-token`
  * Other Info: `cookie:authjs.csrf-token
cookie:authjs.callback-url`
* URL: http://localhost/api/auth/session/
  * Node Name: `http://localhost/api/auth/session/`
  * Method: `GET`
  * Parameter: `authjs.session-token`
  * Attack: ``
  * Evidence: `authjs.session-token`
  * Other Info: `cookie:authjs.session-token
json:accessToken`
* URL: http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth%3Fresponse_type=code&client_id=secretshare-api&redirect_uri=http%253A%252F%252Flocalhost%252Fapi%252Fauth%252Fcallback%252Fkeycloak&code_challenge=H41YvXbxcSkBi_QdYt1r1LIt_ZeaFRHdn49N5ThWLcQ&code_challenge_method=S256&scope=openid+profile+email
  * Node Name: `http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth (client_id,code_challenge,code_challenge_method,redirect_uri,response_type,scope)`
  * Method: `GET`
  * Parameter: `KC_RESTART`
  * Attack: ``
  * Evidence: `KC_RESTART`
  * Other Info: `cookie:KC_RESTART
cookie:AUTH_SESSION_ID`
* URL: http://localhost/api/auth/signin/keycloak/
  * Node Name: `http://localhost/api/auth/signin/keycloak/ ()(callbackUrl,csrfToken)`
  * Method: `POST`
  * Parameter: `authjs.callback-url`
  * Attack: ``
  * Evidence: `authjs.callback-url`
  * Other Info: `cookie:authjs.callback-url
cookie:authjs.pkce.code_verifier`
* URL: http://localhost/keycloak/realms/secretshare/login-actions/authenticate%3Fsession_code=sedylghQJnmDfDvM_4WFzfVweE1xOx2EVynlkRxSK0w&execution=d7e7ae34-dcf5-43c5-bec2-235bbd176dbc&client_id=secretshare-api&tab_id=p0ky3FRdUWY&client_data=eyJydSI6Imh0dHA6Ly9sb2NhbGhvc3QvYXBpL2F1dGgvY2FsbGJhY2sva2V5Y2xvYWsiLCJydCI6ImNvZGUifQ
  * Node Name: `http://localhost/keycloak/realms/secretshare/login-actions/authenticate (client_data,client_id,execution,session_code,tab_id)(credentialId,password,username)`
  * Method: `POST`
  * Parameter: `KEYCLOAK_IDENTITY`
  * Attack: ``
  * Evidence: `KEYCLOAK_IDENTITY`
  * Other Info: `cookie:KEYCLOAK_IDENTITY
cookie:KEYCLOAK_SESSION`
* URL: http://localhost/api/auth/csrf/
  * Node Name: `http://localhost/api/auth/csrf/`
  * Method: `GET`
  * Parameter: `authjs.csrf-token`
  * Attack: ``
  * Evidence: `authjs.csrf-token`
  * Other Info: `cookie:authjs.csrf-token`
* URL: http://localhost/api/auth/session/
  * Node Name: `http://localhost/api/auth/session/`
  * Method: `GET`
  * Parameter: `authjs.csrf-token`
  * Attack: ``
  * Evidence: `authjs.csrf-token`
  * Other Info: `cookie:authjs.csrf-token`
* URL: http://localhost/api/auth/session/
  * Node Name: `http://localhost/api/auth/session/`
  * Method: `GET`
  * Parameter: `authjs.session-token`
  * Attack: ``
  * Evidence: `authjs.session-token`
  * Other Info: `cookie:authjs.session-token`


Instances: 10

### Solution

This is an informational alert rather than a vulnerability and so there is nothing to fix.

### Reference


* [ https://www.zaproxy.org/docs/desktop/addons/authentication-helper/session-mgmt-id/ ](https://www.zaproxy.org/docs/desktop/addons/authentication-helper/session-mgmt-id/)



#### Source ID: 3

### [ User Controllable HTML Element Attribute (Potential XSS) ](https://www.zaproxy.org/docs/alerts/10031/)



##### Informational (Low)

### Description

This check looks at user-supplied input in query string parameters and POST data to identify where certain HTML attribute values might be controlled. This provides hot-spot detection for XSS (cross-site scripting) that will require further review by a security analyst to determine exploitability.

* URL: http://localhost/keycloak/realms/secretshare/login-actions/authenticate%3Fsession_code=ZNoHuMfG36SnERG9y7HtSfsMw3Pq9ldcJTbpRXvCukc&execution=d7e7ae34-dcf5-43c5-bec2-235bbd176dbc&client_id=secretshare-api&tab_id=V5i8oXIUWJM&client_data=eyJydSI6Imh0dHA6Ly9sb2NhbGhvc3QvYXBpL2F1dGgvY2FsbGJhY2sva2V5Y2xvYWsiLCJydCI6ImNvZGUifQ
  * Node Name: `http://localhost/keycloak/realms/secretshare/login-actions/authenticate (client_data,client_id,execution,session_code,tab_id)(credentialId,password,username)`
  * Method: `POST`
  * Parameter: `username`
  * Attack: ``
  * Evidence: ``
  * Other Info: `User-controlled HTML attribute values were found. Try injecting special characters to see if XSS might be possible. The page at the following URL:

http://localhost/keycloak/realms/secretshare/login-actions/authenticate?session_code=ZNoHuMfG36SnERG9y7HtSfsMw3Pq9ldcJTbpRXvCukc&execution=d7e7ae34-dcf5-43c5-bec2-235bbd176dbc&client_id=secretshare-api&tab_id=V5i8oXIUWJM&client_data=eyJydSI6Imh0dHA6Ly9sb2NhbGhvc3QvYXBpL2F1dGgvY2FsbGJhY2sva2V5Y2xvYWsiLCJydCI6ImNvZGUifQ

appears to include user input in:
a(n) [input] tag [value] attribute

The user input found was:
username=ynEvGYfT

The user-controlled value was:
ynevgyft`


Instances: 1

### Solution

Validate all input and sanitize output it before writing to any HTML attributes.

### Reference


* [ https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html ](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)


#### CWE Id: [ 20 ](https://cwe.mitre.org/data/definitions/20.html)


#### WASC Id: 20

#### Source ID: 3


