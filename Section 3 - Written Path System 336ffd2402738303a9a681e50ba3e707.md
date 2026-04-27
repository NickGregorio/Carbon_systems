# Section 3 - Written Path System

# Set project, stop VM, attach the new identity, and restart

```jsx
gcloud config set project [PROJECT_ID]
```

```jsx
gcloud compute instances stop [INSTANCE_NAME] --zone [ZONE]
```

```jsx
gcloud compute instances set-service-account [INSTANCE_NAME] \
--zone [ZONE] \
--service-account [SERVICE_ACCOUNT_EMAIL] \
--scopes [https://www.googleapis.com/auth/cloud-platform](https://www.googleapis.com/auth/cloud-platform)
```

```jsx
gcloud compute instances start [INSTANCE_NAME] --zone [ZONE]
```

---

# Create the firewall rule for port 3333

```jsx
gcloud compute firewall-rules create allow-screenshot-api-3333 \
--direction=INGRESS --priority=1000 --network=default --action=ALLOW \
--rules=tcp:3333 --source-ranges=0.0.0.0/0 --target-tags=screenshot-api
```

# Apply the tag to your instance

```jsx
gcloud compute instances add-tags [INSTANCE_NAME] --zone [ZONE] --tags screenshot-api
```

---

## VM terminal

# Update the system and install the required tools

```jsx
sudo apt update && sudo apt upgrade -y
```

```jsx
sudo apt install -y python3 python3-venv python3-pip chromium \
libnss3 libatk1.0-0 libatk-bridge2.0-0 libxkbcommon0 libxdamage1 \
libxrandr2 libgbm1 libasound2 curl unzip nodejs npm
```

# Verify that Chromium is properly located

```jsx
which chromium
```

# 1. Create and enter the project directory

```jsx
mkdir -p ~/screenshot-api && cd ~/screenshot-api
```

# 2. Create the virtual environment

```jsx
python3 -m venv venv
```

# 3. Activate the environment

```jsx
source venv/bin/activate
```

# 4. Install the core Python libraries

```jsx
pip install --upgrade pip
pip install fastapi uvicorn playwright google-cloud-storage pydantic
```

# 5. Install the Playwright Chromium binary

```jsx
playwright install chromium
```

---

```jsx
cat > app.py <<'EOF'
import os
import uuid
from typing import List
from fastapi import FastAPI
from pydantic import BaseModel
from playwright.async_api import async_playwright
from google.cloud import storage

# ====== CONFIG ======
BUCKET_NAME = "[BUCKET NAME]"
CHROMIUM_PATH = "/usr/bin/chromium"

DESKTOP = {"width": 1440, "height": 900}
MOBILE  = {"width": 390,  "height": 844}

app = FastAPI()
storage_client = storage.Client()
bucket = storage_client.bucket(BUCKET_NAME)

class ScreenshotRequest(BaseModel):
    urls: List[str]

def upload_to_gcs(file_path: str) -> str:
    blob_name = os.path.basename(file_path)
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(file_path)
    os.remove(file_path) 
    return f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_name}"

async def capture(urls: List[str]):
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path=CHROMIUM_PATH,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        for url in urls:
            page_id = uuid.uuid4().hex[:8]
            # Desktop
            page = await browser.new_page(viewport=DESKTOP)
            await page.goto(url, wait_until="networkidle")
            await page.wait_for_timeout(5000)
            d_path = f"/tmp/{page_id}-desktop.png"
            await page.screenshot(path=d_path, full_page=True)
            await page.close()
            # Mobile
            page = await browser.new_page(viewport=MOBILE, is_mobile=True)
            await page.goto(url, wait_until="networkidle")
            await page.wait_for_timeout(5000)
            m_path = f"/tmp/{page_id}-mobile.png"
            await page.screenshot(path=m_path, full_page=True)
            await page.close()

            results.append({
                "url": url,
                "desktop": upload_to_gcs(d_path),
                "mobile": upload_to_gcs(m_path),
            })
        await browser.close()
    return results

@app.post("/screenshot")
async def screenshot(req: ScreenshotRequest):
    return {"results": await capture(req.urls)}
EOF
```

## Then Run This:

```jsx
cat > ecosystem.config.cjs <<EOF
module.exports = {
  apps: [{
    name: "screenshot-api",
    cwd: "/home/[USER]/screenshot-api",
    script: "/home/[USER]/screenshot-api/venv/bin/uvicorn",
    args: "app:app --host 0.0.0.0 --port 3333",
    exec_interpreter: "none",
    autorestart: true,
    env: {
      BUCKET_NAME: "[BUCKET_NAME]",
      CHROMIUM_PATH: "/usr/bin/chromium"
    }
  }]
};
EOF
```

# Start the API

```jsx
sudo npm install -g pm2
pm2 start ecosystem.config.cjs
pm2 save
```

# Test with a live URL on your specific IP

```jsx
curl -X POST [http://34.172.90.203:3333/screenshot](http://34.172.90.203:3333/screenshot) \
-H "Content-Type: application/json" \
-d '{"urls":["[https://google.com](https://google.com/)"]}'
```

---

## N8N Code Modules

Workflow - Get Variables for emails 

**First code block (website parser)**

```jsx
return items.map(item => {
  // Raw from sheet
  let raw = String(item.json.website || '');

  // Sanitize invisible garbage that breaks parsing
  raw = raw
    .replace(/\u00A0/g, ' ')   // nbsp
    .replace(/\u200B/g, '')    // zero-width space
    .replace(/\u200C/g, '')    // zero-width non-joiner
    .replace(/\u200D/g, '')    // zero-width joiner
    .replace(/\uFEFF/g, '')    // BOM
    .trim();

  // Take first URL-ish token if the cell contains extra stuff
  const tokenMatch = raw.match(/https?:\/\/[^\s]+|[a-z0-9.-]+\.[a-z]{2,}(\/[^\s]*)?/i);
  const token = (tokenMatch ? tokenMatch[0] : raw).trim();

  // Extract hostname without trusting URL()
  let host = '';
  const m1 = token.match(/^https?:\/\/([^\/?#\s]+)/i);
  if (m1 && m1[1]) {
    host = m1[1];
  } else {
    // If no scheme, grab leading domain
    const m2 = token.match(/^([a-z0-9.-]+\.[a-z]{2,})(?:[\/?#]|$)/i);
    if (m2 && m2[1]) host = m2[1];
  }

  // Normalize
  const website_domain = host.replace(/^www\./i, '').toLowerCase();

  // Canonical clean website root
  const website_clean = website_domain ? `https://${website_domain}/` : '';

  return {
    json: {
      row_number: item.json.row_number,
      website_clean,
      website_domain
    }
  };
});

```

## Sitemap Check Code:

```jsx
// n8n Code node

const body = $json.data || '';
const sizeBytes = Buffer.byteLength(body, 'utf8');

// hard size cutoff: 1.5 MB
const MAX_SIZE = 1.5 * 1024 * 1024;

// normalize
const text = body.slice(0, 5000).toLowerCase();

// garbage checks
const looksLikeHtml =
  text.includes('<!doctype html') ||
  text.includes('<html') ||
  text.includes('<head') ||
  text.includes('<body');

if (sizeBytes > MAX_SIZE || looksLikeHtml) {
  return [{ status: 2 }];
}

// sitemap checks
const looksLikeSitemap =
  text.includes('<?xml') &&
  (text.includes('<sitemapindex') ||
   text.includes('<urlset') ||
   text.includes('<url><loc>'));

if (looksLikeSitemap) {
  return [{ status: 1 }];
}

// default: treat as garbage
return [{ status: 2 }];

```

## Prompt Code:

```jsx
const raw = $('HTTP Request').first().json.data ?? '';
const xml = String(raw);

// Pull all <loc> links
const locs = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map(m => m[1].trim());

// Build the sitemap blob (links + separator + flattened XML)
const sitemap_blob = [
  locs.join(', '),
  '---',
  xml.replace(/\s+/g, ' ').trim()
].join('\n');

// Prompt template (NORMAL newlines for now)
const prompt =
  "You are a technical research analyst processing XML sitemap data for a business website.\n" +
  "You are given the raw response body retrieved from requesting /sitemap.xml.\n" +
  "Use ONLY the provided sitemap data.\n" +
  "Do NOT use prior knowledge, assumptions, or external information.\n" +
  "If required information cannot be determined from the sitemap data, return null.\n\n" +
  "Business Website data: " + sitemap_blob + "\n\n" +
  "Instructions:\n" +
  "Analyze the provided sitemap response.\n" +
  "First, determine whether the response represents:\n" +
  "- a sitemap index (containing links to other sitemaps),\n" +
  "- a page-level sitemap (containing page URLs),\n" +
  "- or a non-sitemap response (HTML page, blocked response, or invalid content).\n\n" +
  "Decision Rules:\n" +
  "1) If the response is a sitemap index:\n" +
  "   - Select ONE best page-level sitemap URL (prefer page-sitemap.xml or similar; avoid post/category/tag if possible).\n" +
  "   - Output MUST be this exact JSON shape (all keys required):\n" +
  "     {\"sitemap_index\":\"<page sitemap url>\",\"mode\":2,\"url_1\":null,\"url_2\":null,\"url_3\":null}\n\n" +
  "2) If the response is already a page-level sitemap:\n" +
  "   - Select EXACTLY three URLs from the provided URLs only:\n" +
  "     url_1 = homepage (root URL / canonical homepage)\n" +
  "     url_2 = primary offer/service page\n" +
  "     url_3 = trust/differentiation page (about/contact/faq/how-it-works/suppliers)\n" +
  "   - Output MUST be this exact JSON shape (all keys required):\n" +
  "     {\"sitemap_index\":null,\"mode\":1,\"url_1\":\"<url>\",\"url_2\":\"<url>\",\"url_3\":\"<url>\"}\n\n" +
  "3) If invalid/non-sitemap:\n" +
  "   - Output MUST be this exact JSON shape (all keys required):\n" +
  "     {\"sitemap_index\":null,\"mode\":0,\"url_1\":null,\"url_2\":null,\"url_3\":null}\n\n" +
  "Output Requirements (STRICT):\n" +
  "- Output MUST be valid JSON.\n" +
  "- Output MUST be ONE JSON object ONLY.\n" +
  "- Do NOT include markdown, code fences, or extra text.\n" +
  "- Do NOT include arrays.\n" +
  "- Use null exactly as shown.\n" +
  "- All keys MUST be present exactly: sitemap_index, mode, url_1, url_2, url_3\n";

// Convert to escaped style for JSON-safe embedding:
// - escape backslashes
// - escape double quotes
// - turn real newlines into literal \\n
const escapedPrompt = prompt
  .replace(/\\/g, '\\\\')
  .replace(/"/g, '\\"')
  .replace(/\r?\n/g, '\\\\n');

return [
  {
    json: {
      prompt: escapedPrompt
    }
  }
];

```

Sitemap Output code:

```jsx
// Combine chunked Gemini outputs into a single JSON string, then parse.
// Outputs: sitemap_index, mode, url_1, url_2, url_3

const items = $input.all();

// 1) Stitch together all candidate text parts from all items
let text = '';
for (const it of items) {
  const parts = it.json?.candidates?.[0]?.content?.parts ?? [];
  for (const p of parts) {
    if (typeof p.text === 'string') text += p.text;
  }
}

text = text.trim();

// 2) Remove code fences if Gemini ever adds them
text = text.replace(/```(?:json)?/gi, '').replace(/```/g, '').trim();

// 3) Extract JSON object safely (first {...} block)
const m = text.match(/\{[\s\S]*\}/);
if (!m) {
  return [{
    json: {
      sitemap_index: null,
      mode: null,
      url_1: null,
      url_2: null,
      url_3: null,
      _raw: text
    }
  }];
}

let jsonStr = m[0].trim();

// 4) Parse
let obj;
try {
  obj = JSON.parse(jsonStr);
} catch (e) {
  // try minor repair: remove trailing commas
  jsonStr = jsonStr.replace(/,\s*([}\]])/g, '$1');
  obj = JSON.parse(jsonStr);
}

// 5) Clean variables (exact names you want)
const sitemap_index = typeof obj.sitemap_index === 'string' ? obj.sitemap_index : null;
const mode = typeof obj.mode === 'number' ? obj.mode : null;
const url_1 = typeof obj.url_1 === 'string' ? obj.url_1 : null;
const url_2 = typeof obj.url_2 === 'string' ? obj.url_2 : null;
const url_3 = typeof obj.url_3 === 'string' ? obj.url_3 : null;

return [{
  json: { sitemap_index, mode, url_1, url_2, url_3 }
}];

```

Second Prompt Code:

```jsx
// n8n Code node: Upgraded Prompt Builder
const rawText = $input.first().json?.candidates?.[0]?.content?.parts?.[0]?.text ?? '';
let s = String(rawText).trim();

// 1. Clean up JSON fences
s = s.replace(/```json/gi, '').replace(/```/g, '').trim();

// 2. Extract the JSON block from the vision output
const m = s.match(/\{[\s\S]*\}/);
if (!m) return [{ json: { prompt: "No vision JSON found." } }];

let parsed = JSON.parse(m[0].trim());
const pages = Array.isArray(parsed.pages) ? parsed.pages : [];

const cleanPages = pages.map(p => ({
  url: p.url ?? null,
  verdict: p.verdict ?? null,
  issues: Array.isArray(p.issues) ? p.issues.slice(0, 5) : [],
  quick_wins: Array.isArray(p.quick_wins) ? p.quick_wins.slice(0, 5) : []
}));

const pagesJson = JSON.stringify(cleanPages);

// 3. YOUR ORIGINAL PROMPT + STRATEGIC IMPROVEMENT LOGIC
const prompt =
  "You are a research analyst generating short outreach variables for cold email.\n" +
  "You are given VERIFIED website page issues from a vision review. Those issues are the ONLY allowed website problems.\n" +
  "Use live web search to research the COMPANY (what it is, what it offers, locations, credibility signals). Prefer third-party sources.\n" +
  "Do NOT invent new website problems. Only use the vision issues provided.\n" +
  "If something cannot be verified via web sources, use null.\n\n" +
  "COMPANY:\n" +
  "- Domain: " + $('Code in JavaScript1').first().json.website_domain + "\n" +
  "- Company Name: " + $('Get row(s) in sheet').first().json.name + "\n" +
  "- Lead Name: " + $('Get row(s) in sheet').first().json.first_name + " " + $('Get row(s) in sheet').first().json.last_name + "\n\n" +
  "VISION_PAGES_JSON:\n" +
  pagesJson +
  "\n\n" +
  "TASK:\n" +
  "1) Pick ONE best page to anchor outreach.\n" +
  "2) If issues exist: Pick ONE best website_problem directly from the vision issues list.\n" +
  "3) If website is 'fine' (no issues): Use web search to find a business gap (e.g., weak reviews, missing social proof, or outdated info). Use this as the website_problem to show how they can improve.\n" +
  "4) Do quick web research (third-party preferred) to support outreach context.\n\n" +
  "OUTPUT REQUIREMENTS (STRICT):\n" +
  "- Output MUST be valid JSON only. No markdown. No code fences. No extra keys.\n" +
  "- Return exactly these keys: page, website_problem, recognizable_reason, consequence_mechanics, preview_asset_exists, review_time, micro_yes, subject_label\n" +
  "- page = short page name (Home/Menu/About etc)\n" +
  "- website_problem = one line (technical bug from vision OR business gap from search)\n" +
  "- recognizable_reason = why a visitor notices this gap\n" +
  "- consequence_mechanics = how this specific gap hurts revenue or bookings\n" +
  "- preview_asset_exists = true/false/null based on web research\n" +
  "- review_time = integer minutes or null\n" +
  "- micro_yes = <= 10 words\n" +
  "- subject_label = 2-5 words\n";

// 4. Escape for JSON embedding
const escapedPrompt = prompt
  .replace(/\\/g, '\\\\')
  .replace(/"/g, '\\"')
  .replace(/\r?\n/g, '\\\\n');

return [{ json: { prompt: escapedPrompt } }];
```

## Variables Parsing:

```jsx
// n8n Code node: Final Variable Extractor

const raw =
  $input.first().json?.candidates?.[0]?.content?.parts?.[0]?.text ??
  $input.first().json?.text ??
  '';

let text = String(raw).trim();

// 1. Strip code fences
text = text.replace(/```json/gi, '').replace(/```/g, '').trim();

// 2. Extract and Parse JSON
const match = text.match(/\{[\s\S]*\}/);
if (!match) {
  return [{ json: { error: 'No JSON object found', raw_text: text } }];
}

let obj;
try {
  obj = JSON.parse(match[0].trim());
} catch (e) {
  // Minor repair for trailing commas
  const fixedStr = match[0].trim().replace(/,\s*([}\]])/g, '$1');
  obj = JSON.parse(fixedStr);
}

// 3. Map variables directly (No more .answer wrapper)
return [{
  json: {
    page: obj.page ?? null,
    website_problem: obj.website_problem ?? null,
    recognizable_reason: obj.recognizable_reason ?? null,
    consequence_mechanics: obj.consequence_mechanics ?? null,
    preview_asset_exists: typeof obj.preview_asset_exists === 'boolean' ? obj.preview_asset_exists : null,
    review_time: Number.isFinite(obj.review_time) ? obj.review_time : null,
    micro_yes: obj.micro_yes ?? null,
    subject_label: obj.subject_label ?? null,
    // Add sources if Gemini included groundingMetadata
    sources: $input.first().json?.groundingMetadata?.webSearchQueries ?? []
  }
}];
```

# Outreach System Code:

## Randomizer

```jsx
const min = 3;
const max = 7;

const randomNumber = Math.floor(Math.random() * (max - min + 1)) + min;

return [
  {
    json: {
      number: randomNumber
    }
  }
];

```

## Reply Checker:

```jsx
// thread object from Gmail → Thread → Get
const thread = items[0].json;

// result meanings:
// 1 = real reply
// 2 = no reply
// 3 = auto reply
let result = 2;

// keywords that scream "robot"
const autoReplyKeywords = [
  "out of office",
  "automatic reply",
  "auto-reply",
  "autoreply",
  "away from the office",
  "on vacation",
  "on holiday",
  "in holiday",
  "i'm on holiday",
  "i am on holiday",
  "i'm in holiday",
  "i am in holiday",
  "ooo"
];

// helper to read headers safely
function getHeader(msg, name) {
  const h = (msg.payload?.headers || [])
    .find(h => h.name.toLowerCase() === name.toLowerCase());
  return h?.value?.toLowerCase() || "";
}

const msgs = thread.messages || [];

// only your own message exists
if (msgs.length <= 1) {
  return [{ json: { result } }];
}

for (let i = 1; i < msgs.length; i++) {
  const msg = msgs[i];

  const snippet = (msg.snippet || "").toLowerCase();
  const labels = (msg.labels || []).map(l => l.id || l);

  // if it's SENT, it's yours → skip
  if (labels.includes("SENT")) {
    continue;
  }

  // keyword-based auto reply detection
  const isKeywordAutoReply = autoReplyKeywords.some(k =>
    snippet.includes(k)
  );

  // header-based auto reply detection (the real signal)
  const autoSubmitted = getHeader(msg, "Auto-Submitted");
  const xAutoReply = getHeader(msg, "X-Autoreply");
  const precedence = getHeader(msg, "Precedence");

  const isHeaderAutoReply =
    autoSubmitted.includes("auto") ||
    xAutoReply === "yes" ||
    precedence === "bulk";

  // optional short-text heuristic
  const isVeryShort = snippet.split(" ").length <= 6;

  if (isHeaderAutoReply || isKeywordAutoReply || isVeryShort) {
    result = 3; // auto reply
    break;
  }

  // otherwise real human reply
  result = 1;
  break;
}

return [{ json: { result } }];

```