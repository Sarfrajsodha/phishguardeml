# Google OAuth 2.0 Architecture & Flow Diagrams

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PHISHGUARD APPLICATION                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      FRONTEND (Browser)                            │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │  index.html                                                         │   │
│  │  ├─ Login Form                                                      │   │
│  │  │  ├─ Email/Password input                                         │   │
│  │  │  ├─ "Login" button ────────────────┐                             │   │
│  │  │  └─ "Continue with Google" button  │                             │   │
│  │  │                                    │                             │   │
│  │  ├─ Register Form                     │                             │   │
│  │  │  ├─ Username/Email/Password input  │                             │   │
│  │  │  ├─ "Register" button ─────────┐   │                             │   │
│  │  │  └─ "Continue with Google" btn ┼───┤                             │   │
│  │  │                                │   │  [Google Identity Services]  │   │
│  │  └─────────────────────────────────┼───┼─→ api.js                   │   │
│  │                                    │   │   auth.js                   │   │
│  │                                    │   │                             │   │
│  │  JS Functions:                     │   │                             │   │
│  │  • handleLogin()    ───────────────┘   │                             │   │
│  │  • handleRegister() ────────────────┐  │                             │   │
│  │  • handleGoogleSignIn() ────────────┼──┘                             │   │
│  │                                    │                                 │   │
│  │  localStorage:                      │                                 │   │
│  │  • phishguard_token (JWT)           │                                 │   │
│  │  • phishguard_user (JSON)           │                                 │   │
│  │  • google_client_id (config)        │                                 │   │
│  │                                     │                                 │   │
│  └─────────────────────────────────────┼─────────────────────────────────┘   │
│                                        │                                     │
│  ┌────────────────────────────────────┼─────────────────────────────────┐   │
│  │                                    │ HTTP/JSON                      │   │
│  │                                    ▼                                 │   │
│  │  ┌────────────────────────────────────────────────────────────────┐  │   │
│  │  │              BACKEND (Flask API Server)                        │  │   │
│  │  ├────────────────────────────────────────────────────────────────┤  │   │
│  │  │                                                                │  │   │
│  │  │  routes/auth.py                                               │  │   │
│  │  │  ├─ POST /login                                               │  │   │
│  │  │  │  └─ Check email/password vs DB                             │  │   │
│  │  │  │                                                             │  │   │
│  │  │  ├─ POST /register                                            │  │   │
│  │  │  │  └─ Create email/password user                             │  │   │
│  │  │  │                                                             │  │   │
│  │  │  └─ POST /auth/google/token ◄─── GOOGLE OAUTH ROUTE           │  │   │
│  │  │     │                            (NEW)                         │  │   │
│  │  │     ├─ [1] Receive Google ID token from frontend              │  │   │
│  │  │     │                                                         │  │   │
│  │  │     ├─ [2] Verify token signature                            │  │   │
│  │  │     │     using google-auth library                          │  │   │
│  │  │     │                                                         │  │   │
│  │  │     ├─ [3] Extract: google_id, email, name, picture          │  │   │
│  │  │     │                                                         │  │   │
│  │  │     ├─ [4] Query database:                                    │  │   │
│  │  │     │     ├─ Find by google_id (primary lookup)               │  │   │
│  │  │     │     ├─ If found: Update & login user                    │  │   │
│  │  │     │     └─ If not found: Look up by email                   │  │   │
│  │  │     │        ├─ If email exists: Link OAuth & login           │  │   │
│  │  │     │        └─ If new email: Create account & login          │  │   │
│  │  │     │                                                         │  │   │
│  │  │     └─ [5] Generate JWT token                                 │  │   │
│  │  │         Return: { token, user, message }                      │  │   │
│  │  │                                                                │  │   │
│  │  │  models/user.py                                               │  │   │
│  │  │  └─ User (SQLAlchemy model)                                   │  │   │
│  │  │     ├─ id, username, email, password_hash (nullable)          │  │   │
│  │  │     ├─ role, created_at, last_login, is_active                │  │   │
│  │  │     │                                                          │  │   │
│  │  │     └─ NEW OAuth fields:                                       │  │   │
│  │  │        ├─ google_id (unique constraint)                        │  │   │
│  │  │        ├─ auth_provider ('google', 'email', etc.)              │  │   │
│  │  │        └─ profile_picture (URL from Google)                    │  │   │
│  │  │                                                                │  │   │
│  │  │  config.py                                                    │  │   │
│  │  │  └─ GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')          │  │   │
│  │  │                                                                │  │   │
│  │  └──────────────────────────┬─────────────────────────────────────┘  │   │
│  │                             │                                        │   │
│  │  ┌────────────────────────────────────────────────────────────────┐  │   │
│  │  │              DATABASE (SQLite)                                 │  │   │
│  │  ├────────────────────────────────────────────────────────────────┤  │   │
│  │  │                                                                │  │   │
│  │  │  users table:                                                  │  │   │
│  │  │  ┌─────────────────────────────────────────────────────────┐  │  │   │
│  │  │  │ id  │ username │ email │ password_hash │ role │ ...    │  │  │   │
│  │  │  ├─────────────────────────────────────────────────────────┤  │  │   │
│  │  │  │ 1   │ john_doe │ john@ │ $2b$12$...    │ user │ ...    │  │  │   │
│  │  │  ├─────────────────────────────────────────────────────────┤  │  │   │
│  │  │  │     │ google_id        │ auth_provider │ picture        │  │  │   │
│  │  │  ├─────────────────────────────────────────────────────────┤  │  │   │
│  │  │  │     │ 12345678901      │ google        │ https://... │   │  │   │
│  │  │  └─────────────────────────────────────────────────────────┘  │  │   │
│  │  │                                                                │  │   │
│  │  └────────────────────────────────────────────────────────────────┘  │   │
│  │                                                                        │   │
│  └────────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │          EXTERNAL: Google OAuth 2.0 Service                        │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │  Frontend ──[Google Sign-In popup]──────────────►  Google          │   │
│  │                                                   Accounts          │   │
│  │  User authenticates with Google ◄────────────────                  │   │
│  │  Google returns ID Token to frontend                               │   │
│  │                                                                     │   │
│  │  Backend ──[Verify token]─────────────────────────► Google         │   │
│  │                                                   Public Keys       │   │
│  │  Token verified ◄─────────────────────────────────                 │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## User Flow Diagrams

### Flow 1: New User - Google Sign-Up

```
┌─────────────────────────────────────────────────────────────────────────┐
│ User: "I want to create an account"                                     │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ Open index.html  │
                    │ (Register tab)   │
                    └──────────────────┘
                              │
                              ▼
                    ┌──────────────────────┐
                    │ Click "Continue     │
                    │ with Google" button  │
                    └──────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────┐
        │ Google Sign-In Popup                │
        │ (Frontend: window.google.accounts) │
        └─────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────┐
        │ User: Sign in with Google           │
        │ → Consents to app access            │
        └─────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────┐
        │ Google returns ID Token to frontend         │
        │ (JWT with: sub, email, name, picture)      │
        └─────────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────────┐
        │ Frontend: handleGoogleSignIn()               │
        │ POST /api/auth/google/token                  │
        │ Body: { idToken: "eyJ..." }                  │
        └──────────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────────┐
        │ Backend: google_auth() route                 │
        │ 1. Verify token signature                    │
        │ 2. Extract: google_id, email, name, picture │
        │ 3. Query: SELECT * FROM users WHERE         │
        │    google_id = "12345..." → Not found       │
        │ 4. Query: SELECT * FROM users WHERE         │
        │    email = "john@example.com" → Not found   │
        │ 5. CREATE new user:                         │
        │    - username: "john.doe1234"               │
        │    - email: "john@example.com"              │
        │    - google_id: "12345..."                  │
        │    - auth_provider: "google"                │
        │    - profile_picture: "https://..."         │
        │    - password_hash: NULL                    │
        │    - role: "user"                           │
        │ 6. Generate JWT token                       │
        │ 7. Return: { token, user, message }         │
        └──────────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────────┐
        │ Frontend: Response received                  │
        │ • localStorage.setItem('phishguard_token', JWT)
        │ • localStorage.setItem('phishguard_user', JSON)
        │ • Show success message                       │
        │ • Redirect to dashboard.html                │
        └──────────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────────┐
        │ Dashboard loads                              │
        │ • Gets token from localStorage               │
        │ • Sends GET /api/me with Authorization       │
        │ • Backend verifies JWT, returns user info    │
        │ • Displays: username, avatar (Google), etc. │
        └──────────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────────┐
        │ ✅ User successfully registered & logged in   │
        │ via Google OAuth 2.0                         │
        └──────────────────────────────────────────────┘
```

### Flow 2: Existing User - Google Login

```
┌─────────────────────────────────────────────────────────────────────────┐
│ User: "I want to log in"                                                │
│ (Already has account created with Google on same email)                 │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ Open index.html  │
                    │ (Login tab)      │
                    └──────────────────┘
                              │
                              ▼
                    ┌──────────────────────┐
                    │ Click "Continue     │
                    │ with Google" button  │
                    └──────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────┐
        │ Google Sign-In (already cached)     │
        │ Quickly authenticates user          │
        └─────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────────┐
        │ Backend: google_auth() route                 │
        │ 1. Verify token signature                    │
        │ 2. Extract: google_id = "12345..."          │
        │ 3. Query: SELECT * FROM users WHERE         │
        │    google_id = "12345..." → FOUND! ✓       │
        │ 4. Update: last_login = NOW()                │
        │ 5. Generate JWT token                       │
        │ 6. Return: { token, user, message }         │
        └──────────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────────┐
        │ Frontend: Redirect to dashboard              │
        │ → User logged in (fast!)                     │
        └──────────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────────┐
        │ ✅ User successfully logged in via Google     │
        │ (same account as before)                    │
        └──────────────────────────────────────────────┘
```

### Flow 3: Account Linking - Email → Email + Google

```
┌─────────────────────────────────────────────────────────────────────────┐
│ User: "I registered with email/password, now want to use Google"        │
│ Scenario: Email is "john@example.com" (both platforms)                 │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        Step 1: First login with email/password
        ┌──────────────────────────────────────────────┐
        │ • Username: john_doe                         │
        │ • Password: ••••••••                         │
        │ • POST /api/auth/login                       │
        │ • Logged in successfully ✓                  │
        │ • DB: google_id = NULL, auth_provider = NULL│
        └──────────────────────────────────────────────┘
                              │
                              ▼
        Step 2: Later, user tries to login with Google
        ┌──────────────────────────────────────────────┐
        │ • Click "Continue with Google"               │
        │ • Google popup with same email              │
        │ • POST /api/auth/google/token                │
        └──────────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────────┐
        │ Backend: google_auth() route                 │
        │ 1. Verify token signature                    │
        │ 2. Extract: google_id = "12345..."          │
        │            email = "john@example.com"       │
        │ 3. Query: SELECT * FROM users WHERE         │
        │    google_id = "12345..." → NOT found       │
        │ 4. Query: SELECT * FROM users WHERE         │
        │    email = "john@example.com" → FOUND! ✓   │
        │ 5. LINK the OAuth:                          │
        │    UPDATE users SET                         │
        │    • google_id = "12345..."                │
        │    • auth_provider = "email_and_google"     │
        │    • profile_picture = "https://..."        │
        │    WHERE id = 1                             │
        │ 6. Generate JWT token                       │
        │ 7. Return: { token, user, message }         │
        └──────────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────────┐
        │ Frontend: Redirect to dashboard              │
        │ • Same user (john_doe)                       │
        │ • Now can login with both:                   │
        │   - Email + password                         │
        │   - Google account                          │
        └──────────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────────┐
        │ ✅ Account successfully linked!              │
        │ Single user with dual auth methods          │
        └──────────────────────────────────────────────┘
```

---

## Token Verification Flow (Security)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                 HOW GOOGLE OAUTH TOKEN IS VERIFIED                      │
└─────────────────────────────────────────────────────────────────────────┘

Frontend sends ID Token to Backend:
                            
    id_token_str = "eyJhbGc..." (JWT from Google)
         │
         ▼
Backend: google.oauth2.id_token.verify_oauth2_token(
           id_token_str, 
           requests.Request(),        ◄─ HTTPS request object
           GOOGLE_CLIENT_ID            ◄─ Our app's Client ID
         )

         │
         ▼ (Library makes HTTPS request to Google's public keys endpoint)
         
    https://www.googleapis.com/oauth2/v1/certs
    
    Google responds with:
    {
      "alg": "RS256",
      "kid": "1",
      "key": "-----BEGIN RSA PUBLIC KEY-----\n..."
    }
         │
         ▼ (Library verifies token signature)
         
    1. Extract header: alg = "RS256", kid = "1"
    2. Get matching public key from Google
    3. Verify token signature with RS256 algorithm
    4. Check expiration time
    5. Check audience (matches our GOOGLE_CLIENT_ID)
    6. Extract payload
         │
         ▼ (Return verified payload)
         
    {
      "sub": "12345678901234567890",    ◄─ Unique Google ID
      "email": "john@example.com",
      "name": "John Doe",
      "picture": "https://...",
      "iat": 1625097600,
      "exp": 1625101200,                ◄─ Token valid for ~1 hour
      "aud": "YOUR_CLIENT_ID.apps.googleusercontent.com"
    }

🔐 SECURITY BENEFITS:
   ✓ Token is cryptographically signed by Google
   ✓ We verify signature against Google's public keys
   ✓ Token cannot be forged by attacker
   ✓ Token cannot be modified after signing
   ✓ Frontend cannot trick backend (token verified server-side)
   ✓ Expiration is checked automatically
   ✓ Audience is verified (token for correct app)
```

---

## Database Query Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│            HOW DATABASE QUERIES WORK FOR GOOGLE AUTH                   │
└─────────────────────────────────────────────────────────────────────────┘

Backend receives verified payload:
  {
    "sub": "12345678901234567890",
    "email": "john@example.com",
    ...
  }
         │
         ▼

Step 1: Look up by google_id (PRIMARY)
─────────────────────────────────
         
    SELECT * FROM users
    WHERE google_id = "12345678901234567890"
    
    ├─ Result: FOUND?
    │  └─► Go to Step 4 (LOGIN EXISTING)
    │
    └─ Result: NOT FOUND?
       └─► Go to Step 2
         │
         ▼

Step 2: Look up by email (SECONDARY)
─────────────────────────────────
    
    SELECT * FROM users
    WHERE email = "john@example.com"
    
    ├─ Result: FOUND?
    │  └─► Go to Step 3 (LINK ACCOUNT)
    │
    └─ Result: NOT FOUND?
       └─► Go to Step 5 (CREATE NEW)
         │
         ▼

Step 3: LINK ACCOUNT (Email exists, but no google_id)
────────────────────────────────────────────────────
    
    UPDATE users SET
      google_id = "12345678901234567890",
      auth_provider = "email_and_google",
      profile_picture = "https://...",
      last_login = NOW()
    WHERE id = <user_id>
    
    ✓ Account linked successfully
    └─► Go to Step 6 (RETURN TOKEN)
         │
         ▼

Step 4: LOGIN EXISTING (Google ID found)
───────────────────────────────────────
    
    UPDATE users SET
      last_login = NOW(),
      profile_picture = "https://..."
    WHERE google_id = "12345678901234567890"
    
    ✓ User logged in
    └─► Go to Step 6 (RETURN TOKEN)
         │
         ▼

Step 5: CREATE NEW (Email doesn't exist)
─────────────────────────────────────
    
    INSERT INTO users (
      username,           ◄─ Generated: "john.doe1234"
      email,              ◄─ "john@example.com"
      google_id,          ◄─ "12345678901234567890"
      auth_provider,      ◄─ "google"
      profile_picture,    ◄─ "https://..."
      password_hash,      ◄─ NULL (not needed for OAuth)
      role,               ◄─ "user" (or "admin" if first user)
      created_at,
      is_active
    ) VALUES (...)
    
    ✓ New user created
    └─► Go to Step 6 (RETURN TOKEN)
         │
         ▼

Step 6: RETURN TOKEN
──────────────────
    
    1. Generate JWT token
       {
         "sub": <user_id>,
         "username": "john_doe",
         "role": "user",
         "exp": <24 hours from now>
       }
    
    2. Return HTTP 200 or 201:
       {
         "token": "eyJhbG...",
         "user": {
           "id": 1,
           "username": "john_doe",
           "email": "john@example.com",
           "auth_provider": "google",
           "profile_picture": "https://...",
           ...
         },
         "message": "..."
       }
    
    ✓ Frontend receives JWT
    ✓ Frontend stores in localStorage
    ✓ Frontend redirects to dashboard
```

---

## Backward Compatibility

```
┌─────────────────────────────────────────────────────────────────────────┐
│              HOW EXISTING EMAIL/PASSWORD AUTH STILL WORKS              │
└─────────────────────────────────────────────────────────────────────────┘

BEFORE: Email/Password Only
──────────────────────────
┌─────────────────────────┐
│ POST /api/auth/login    │
│ (email/password)        │
│ → Check password_hash   │
│ → Return JWT            │
└─────────────────────────┘

AFTER: Email/Password + Google OAuth
─────────────────────────────────────
┌─────────────────────────┐         ┌──────────────────────────┐
│ POST /api/auth/login    │         │ POST /api/auth/google/   
│ (email/password)        │         │ token (Google ID token)  │
│ → Check password_hash   │         │ → Verify token signature │
│ → Return JWT            │         │ → Check google_id        │
└─────────────────────────┘         │ → Return JWT             │
         │                          └──────────────────────────┘
         │                                    │
         ├────────────────┬───────────────────┤
                          ▼
         Both return same JWT format!
         
         {
           "token": "eyJhbG...",
           "user": {...}
         }
         
         Frontend stores both the same way:
         localStorage.setItem('phishguard_token', token)
         
         Protected routes use same JWT verification:
         GET /api/me
         GET /api/scan/history
         ... etc ...
         
         All routes work for both auth methods! ✓

DATABASE SCHEMA COMPATIBILITY:
──────────────────────────────

┌─────────────────────────────────────────────────┐
│ EXISTING USERS (Email/Password)                 │
├─────────────────────────────────────────────────┤
│ id │ username │ email │ password_hash │ ...    │
│ 1  │ john_doe │ john@ │ $2b$12$...    │ ...    │
│                      │                          │
│    NEW (nullable) ──→│ google_id = NULL         │
│    NEW (nullable) ──→│ auth_provider = NULL     │
│    NEW (nullable) ──→│ profile_picture = NULL   │
│                      │                          │
│ User works normally! ✓                         │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ NEW USERS (Google OAuth)                        │
├─────────────────────────────────────────────────┤
│ id │ username │ email │ password_hash │ ...    │
│ 2  │ alice... │ alice@│ NULL          │ ...    │
│                      │                          │
│    NEW (set) ───────→│ google_id = "12345..."  │
│    NEW (set) ───────→│ auth_provider = "google"│
│    NEW (set) ───────→│ profile_picture = "..." │
│                      │                          │
│ User works normally! ✓                         │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ LINKED USERS (Both methods)                     │
├─────────────────────────────────────────────────┤
│ id │ username │ email │ password_hash │ ...    │
│ 3  │ bob_...  │ bob@  │ $2b$12$...    │ ...    │
│                      │                          │
│    NEW (set) ───────→│ google_id = "54321..."  │
│    NEW (set) ───────→│ auth_provider =         │
│                      │  "email_and_google"     │
│    NEW (set) ───────→│ profile_picture = "..." │
│                      │                          │
│ User can login both ways! ✓                    │
└─────────────────────────────────────────────────┘
```

---

## Summary

✅ **Architecture**: Modular, scalable, production-ready  
✅ **Security**: Server-side verification, unique constraints  
✅ **Compatibility**: No breaking changes to existing auth  
✅ **UX**: Seamless account creation and linking  
✅ **Flexibility**: Users can use one or both methods  

