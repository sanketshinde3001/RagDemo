# Serper API Setup Guide

## What is Serper API?

Serper API (serper.dev) is a modern, fast, and cost-effective Google Search API. It's much more affordable than SerpAPI and offers similar functionality.

## Setup Steps

### 1. Get Your API Key

1. Go to [serper.dev](https://serper.dev)
2. Sign up for a free account
3. You get **2,500 free searches per month**
4. Copy your API key from the dashboard

### 2. Add API Key to .env

Update your `backend/.env` file:

```env
SERPER_API_KEY=your_actual_serper_api_key_here
```

Replace `your_actual_serper_api_key_here` with the key you copied from serper.dev

### 3. Install Dependencies (if needed)

```bash
cd backend
pip install requests
```

The `requests` library is already in requirements.txt, so it should be installed when you run:

```bash
pip install -r requirements.txt
```

### 4. Test the Web Search

1. Start your backend server:
   ```bash
   python main.py
   ```

2. Upload a PDF in your frontend

3. Enable the "Web Search" toggle

4. Ask a question that needs web search:
   - "What's the weather today?"
   - "Latest news about AI?"
   - "Current price of Bitcoin?"

### 5. Deploy to Render

When deploying to Render, add the environment variable:

**Key:** `SERPER_API_KEY`  
**Value:** Your actual Serper API key

## Pricing

- **Free Tier**: 2,500 searches/month
- **Pay-as-you-go**: $2 per 1,000 searches after free tier
- Much cheaper than SerpAPI ($50/month for 5,000 searches)

## API Endpoint

The code uses: `https://google.serper.dev/search`

## Response Format

Serper returns results with:
- `organic`: Array of search results
- Each result has: `title`, `link`, `snippet`

## Error Handling

If web search fails, check:
1. ✅ API key is correct in `.env`
2. ✅ You haven't exceeded monthly limit
3. ✅ Internet connection is working
4. ✅ Backend server restarted after adding key

## Logs

Watch for these log messages:
- ✅ `"Web searcher initialized with Serper API"` - Good!
- ⚠️ `"SERPER_API_KEY not configured"` - Add your key to .env
- ❌ `"Web search error: ..."` - Check API key and limit

## Advantages over SerpAPI

1. **Cost**: 5x cheaper
2. **Speed**: Faster response times
3. **Simplicity**: Simple REST API (no SDK needed)
4. **Free tier**: 2,500 searches vs SerpAPI's 100
5. **No dependencies**: Just uses `requests` library

## Documentation

Full API docs: [serper.dev/docs](https://serper.dev/docs)
