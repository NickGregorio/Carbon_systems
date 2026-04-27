# Screenshot API Troubleshooting Guide

If your API is returning `Internal Server Error` or failing to start, work through these fixes one by one.

---

## 1. Multi-line commands breaking when pasted into Cloud Shell

**The error:**

```
-bash: --zone: command not found
-bash: --service-account: command not found
-bash: --scopes: command not found
```

**What's causing it:**
When you copy-paste commands with backslashes (`\`) from the tutorial, Cloud Shell sometimes doesn't register the line continuation. Each line gets treated as a separate command.

**How to fix it:**
Always paste multi-line commands as a **single line** with no backslashes. For example, instead of:

```
gcloud compute instances set-service-account trw-123 \
--zone us-central1-a \
--service-account YOUR_SERVICE_ACCOUNT \
--scopes https://www.googleapis.com/auth/cloud-platform
```

Paste this:

```
gcloud compute instances set-service-account trw-123 --zone us-central1-a --service-account YOUR_SERVICE_ACCOUNT --scopes https://www.googleapis.com/auth/cloud-platform
```

**Be careful with:** Every command from the tutorial that uses `\` to split across lines. Always join them into one line before pasting.

---

## 2. GCS Python library can't authenticate (SSL / metadata error)

**The error:**

```
google.auth.exceptions.RefreshError: Failed to retrieve
https://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/?recursive=true
...
SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed'))
```

**What's causing it:**
The `google-auth` Python library is trying to reach the GCP metadata server over HTTPS instead of HTTP. The metadata server only supports HTTP, so SSL verification fails. This is a bug in newer versions of the library.

**How to fix it:**
Downgrade `google-auth` to a version that doesn't have this bug. SSH into your VM and run:

```bash
source ~/screenshot-api/venv/bin/activate
pip install google-auth==2.27.0
```

If that specific version doesn't fix it, set the metadata host explicitly. Add these environment variables to your `ecosystem.config.cjs`:

```jsx
env: {
  // ...your other env vars...
  GCE_METADATA_HOST: "169.254.169.254",
  GCE_METADATA_ROOT: "169.254.169.254"
}
```

**Be careful with:** After changing the library version, you must restart PM2 (see section 6 below).

---

## 3. Service account not attached to the VM

**The error:**

```
OSError: Project was not passed and could not be determined from the environment.
```

**What's causing it:**
The `set-service-account` command didn't apply properly — usually because of the multi-line paste issue from fix #1. Without a service account, the VM can't talk to GCS.

**How to fix it:**
Run these commands **from Cloud Shell** (not from inside the VM), **one at a time**, waiting for each to finish:

```bash
gcloud compute instances stop [INSTANCE_NAME] --zone [ZONE]
```

```bash
gcloud compute instances set-service-account [INSTANCE_NAME] --zone [ZONE] --service-account [SERVICE_ACCOUNT_EMAIL] --scopes https://www.googleapis.com/auth/cloud-platform
```

```bash
gcloud compute instances start [INSTANCE_NAME] --zone [ZONE]
```

Replace `[INSTANCE_NAME]`, `[ZONE]`, and `[SERVICE_ACCOUNT_EMAIL]` with your actual values.

**Be careful with:** Your VM's external IP will change after a stop/start. Check the new IP in the output of the start command or in the GCP Console.

---

## 4. Service account doesn't have permission to write to the bucket

**The error:**

```
google.api_core.exceptions.Forbidden: 403 POST
...does not have storage.objects.create access to the Google Cloud Storage object.
Permission 'storage.objects.create' denied on resource (or it may not exist).
```

**What's causing it:**
The service account attached to your VM doesn't have write permissions on your GCS bucket.

**How to fix it:**
Run this from **Cloud Shell**:

```bash
gsutil iam ch serviceAccount:[SERVICE_ACCOUNT_EMAIL]:roles/storage.objectAdmin gs://[BUCKET_NAME]
```

Replace `[SERVICE_ACCOUNT_EMAIL]` and `[BUCKET_NAME]` with your actual values.

**Be careful with:** Make sure you're granting the permission to the correct service account (the one attached to the VM, not your personal account).

---

## 5. Project ID not set in app.py

**The error:**

```
OSError: Project was not passed and could not be determined from the environment.
```

**What's causing it:**
The `storage.Client()` call in `app.py` doesn't know which GCP project to use.

**How to fix it:**
Edit `app.py` and change this line:

```python
storage_client = storage.Client()
```

To this:

```python
storage_client = storage.Client(project="YOUR_PROJECT_ID")
```

You can do it with one command:

```bash
sed -i 's/storage_client = storage.Client()/storage_client = storage.Client(project="YOUR_PROJECT_ID")/' ~/screenshot-api/app.py
```

**Be careful with:** Use your actual project ID (e.g., `engaged-lamp-491500-h2`), not the project name.

---

## 6. Save and restart — do this after every fix

After making any change, always restart the API:

```bash
cd ~/screenshot-api
source venv/bin/activate
pm2 delete screenshot-api
pm2 start ecosystem.config.cjs
pm2 save
```

Wait a few seconds, then check it's running:

```bash
pm2 logs screenshot-api --lines 5
```

You should see:

```
INFO:     Uvicorn running on http://0.0.0.0:3333 (Press CTRL+C to quit)
```

Then test:

```bash
curl -X POST http://localhost:3333/screenshot -H "Content-Type: application/json" -d '{"urls":["https://google.com"]}'
```

You should get back a JSON response with GCS URLs for the desktop and mobile screenshots.

**If PM2 says "process not found" after a VM reboot**, the process list was lost. Just run `pm2 start ecosystem.config.cjs` again.

---

## Quick checklist

If your API isn't working, go through this in order:

1. Is the service account attached? (Fix #3)
2. Does the service account have bucket permissions? (Fix #4)
3. Is the project ID set in `app.py`? (Fix #5)
4. Is `google-auth` on a working version? (Fix #2)
5. Did you restart PM2 after making changes? (Fix #6)