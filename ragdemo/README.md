This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.

## ⚠️ WebSocket Limitations on Vercel

**Voice Input Feature**: The real-time voice transcription feature uses WebSockets, which are **NOT supported** on Vercel's serverless infrastructure.

### What This Means:
- ✅ **All core features work**: PDF upload, chat, search modes (Vector/Keyword/Hybrid)
- ❌ **Voice input disabled**: The microphone button will be grayed out with a tooltip explanation
- ℹ️ **Automatic fallback**: The app detects WebSocket failure and gracefully disables voice input

### Solutions:

**Option 1: Keep Vercel (No Voice Input)**
- Deploy frontend on Vercel (free)
- Deploy backend on Render/Railway (supports WebSocket)
- Voice input will auto-disable on frontend
- **Best for**: Users who don't need voice input

**Option 2: Deploy Frontend Elsewhere (Full Features)**
- Deploy both frontend and backend on platforms with WebSocket support:
  - ✅ **Render** (free tier, supports WebSocket)
  - ✅ **Railway** (free trial, supports WebSocket)
  - ✅ **Fly.io** (free tier, supports WebSocket)
  - ✅ **DigitalOcean App Platform**
- **Best for**: Users who need voice input feature

### Environment Variables
```bash
# In Vercel project settings, add:
NEXT_PUBLIC_API_URL=https://your-backend.onrender.com
```

The app will automatically convert `https://` to `wss://` for WebSocket connections.
