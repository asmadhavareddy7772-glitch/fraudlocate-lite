# 🚀 FraudLocate Lite – Cloud Deployment Guide

This guide explains how to deploy **FraudLocate Lite** to the cloud so you can share a live public URL with your reviewer, hackathon judges, or team members.

---

## ⚠️ Important Note: Streamlit on Vercel vs Streamlit Community Cloud

### Why Vercel is NOT Recommended for Streamlit
- **Vercel is a Serverless Platform:** Vercel is designed for static websites (Next.js, React) and short-lived HTTP APIs. Serverless functions on Vercel shut down after 10–15 seconds and do **not** support persistent WebSockets.
- **Streamlit Requires Active WebSockets:** Streamlit relies on a persistent WebSocket connection (`/_stcore/stream`) to keep the session state alive, re-run DBSCAN calculations, render Folium maps, and process evidence uploads.
- **Bundle Size Limit:** Vercel has a strict 250 MB uncompressed limit for Python serverless functions. Libraries like `scikit-learn`, `pandas`, `scipy`, and `streamlit` exceed this limit and fail during the build step.
- **Ephemeral Storage:** Vercel has a read-only filesystem; uploaded evidence photos/videos and SQLite alerts cannot be saved between requests.

---

## 🏆 Option 1: Streamlit Community Cloud (Recommended — 100% Free & Takes 2 Minutes)

Streamlit Community Cloud is the **official free hosting platform** built specifically for Streamlit apps.

### Step 1: Push your code to GitHub
Open your terminal in the project folder and run:
```powershell
git init
git add .
git commit -m "FraudLocate Lite - Production Ready"
```
Then create a new repository on [GitHub](https://github.com/new) named `fraudlocate-lite` and push:
```powershell
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/fraudlocate-lite.git
git branch -M main
git push -u origin main
```

### Step 2: Deploy on Streamlit Cloud
1. Go to **[share.streamlit.io](https://share.streamlit.io/)** and sign in with your GitHub account.
2. Click **"New app"**.
3. Select your repository: `YOUR_GITHUB_USERNAME/fraudlocate-lite`.
4. Branch: `main`.
5. Main file path: `app.py`.
6. Click **"Deploy!"**.

Within 1–2 minutes, your app will be live at:
👉 `https://fraudlocate-lite.streamlit.app`

---

## 🌐 Option 2: Render.com (100% Free Container Hosting)

Render provides free persistent web services that fully support Streamlit, WebSockets, and SQLite.

### Steps:
1. Push your repository to GitHub.
2. Go to **[render.com](https://render.com/)** and sign in.
3. Click **"New +"** $\rightarrow$ **"Web Service"**.
4. Connect your GitHub repository.
5. Set:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0`
6. Click **"Create Web Service"**.

---

## 📦 Option 3: Hugging Face Spaces (100% Free & No Setup)

1. Go to **[huggingface.co/spaces](https://huggingface.co/spaces)**.
2. Click **"Create new Space"**.
3. Choose **Streamlit** as the Space SDK.
4. Upload your project files or link your GitHub repo.
5. It builds and launches automatically with a free persistent link!
