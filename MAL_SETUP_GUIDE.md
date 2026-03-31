# MyAnimeList API Setup Guide

This guide explains how to configure MyAnimeList (MAL) integration in Anime Updater.

## Step 1 — Create a MAL API Client

1. Log in to your MyAnimeList account.
2. Go to **API settings**: <https://myanimelist.net/apiconfig>
3. Click **"Create ID"** (you may need to agree to the API License first).
4. Fill in the application form:

| Field              | Value                                    |
|--------------------|------------------------------------------|
| **App Name**       | `Anime Updater` (or any name you like)   |
| **App Type**       | `web`                                    |
| **App Description**| Optional — e.g. "Desktop anime tracker" |
| **App Redirect URL** | `http://localhost:8080/callback`       |
| **Homepage URL**   | Optional — leave blank or any URL       |
| **Commercial / Non-Commercial** | Non-Commercial             |

5. Click **Submit**. You will see your new application listed.
6. Click **Edit** on the newly created application to view your credentials:
   - **Client ID** — a long alphanumeric string
   - **Client Secret** — another long string (may be empty for some app types)

> **Important:** The **App Redirect URL** must be exactly `http://localhost:8080/callback`.
> If the port is already in use the app will try nearby ports (8081, 8082, etc.), but the URL
> registered on MAL must match the one the app opens in the browser. Port 8080 is the default.

## Step 2 — Configure the App

1. Open **Anime Updater**.
2. Go to **Menu → Options...** (or press the Options button).
3. In the **Anime Service** section, change the dropdown to **MyAnimeList**.
4. Enter your **Client ID** and **Client Secret** in the fields that appear.
5. Click **Save**.

## Step 3 — Authenticate

1. Click **Authentication...** in the main menu.
2. Click **Start Authentication**.
3. Your browser will open to MyAnimeList's authorization page.
4. Log in (if not already) and click **Allow**.
5. The browser will redirect to `localhost` and the app will automatically capture the authorization code.
6. The dialog will show "Authentication successful!" and close.

After successful authentication your anime and manga lists will be loaded automatically.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "MAL Client ID is not configured" | Enter your Client ID in Options → Anime Service → MyAnimeList |
| Browser shows "connection refused" after clicking Allow | Make sure no firewall is blocking `localhost:8080`. Try closing other apps that might use that port. |
| Authentication timed out | Retry. The timeout is 2 minutes. |
| Token refresh errors / lists fail to load | Go to Options, re-save your credentials, and re-authenticate. MAL access tokens expire every hour but should refresh automatically. |
| "Authorization failed: invalid_client" | Double-check that the Client ID and Client Secret match what is shown on <https://myanimelist.net/apiconfig>. |

## Notes

- MAL access tokens expire after **1 hour**. The app refreshes them automatically using the refresh token.
- MAL refresh tokens expire after **1 month**. If the app stops working after a long break, re-authenticate.
- The app uses **OAuth 2.0 Authorization Code Grant with PKCE** (plain method) as required by the MAL API v2.
- All list operations (update progress, change status, add, remove) work the same way as with Shikimori.
- You can switch between Shikimori and MyAnimeList at any time in Options. Each service maintains its own credentials and tokens independently.
