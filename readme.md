# 🚀 CodifyLive — Backend (FastAPI)

CodifyLive is a real-time collaboration platform that lets users chat, call, and code together directly in the browser.
This repository contains the backend, built with FastAPI, Supabase, and modern real-time tooling. 

Check-out frontend [here](https://github.com/fulanii/codify-live-frontend)


## 🔥 Features (Backend)

### Authentication
- User registration, login, logout
- Email/password auth via Supabase Auth
- JWT verification in FastAPI
- Password reset & email verification
- Secure session handling

### User System
- User profiles
- Add / remove friends
- Friend request system
- User search by username

### Real-Time Collaboration
- Real-time messaging (1:1 chats)
- Video/audio calling (WebRTC + signaling server)
- Live cursor presence
- Real-time code editor sync (OT/CRDT planned)

### File Workspace
- Create, rename, delete files
- File content updates
- Save to Supabase storage / database
- Run code in isolated sandboxes (MVP placeholder)

### 🧱 Tech Stack (Backend)
- FastAPI — backend framework
- Supabase — auth, database, storage
- PostgreSQL — primary database
- WebSockets — real-time communication
- PyJWT / JWT — token verification


### 🤝 Contributing
This is an open learning project — contributions, feedback, and PRs are welcome.

### 📣 Follow the Build
I'm building this project in public — follow progress on Twitter/X: @yassinecodes