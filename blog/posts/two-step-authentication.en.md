---
title: "Tutorial: protect your account with two-step authentication"
date: 2026-10-18
category: tutorial
summary: Add a second step to your dashboard login with an authenticator app, and keep your recovery codes safe.
tags: security, 2fa, account
---
Your falcondatabase account controls every project, key and table you own. A leaked password shouldn't be enough to get in. Two-step authentication (2FA) adds a 6-digit code from your phone that changes every 30 seconds.

## What you need

Any app that supports TOTP codes: Google Authenticator, Microsoft Authenticator, Authy, 1Password, Bitwarden, Proton Pass…

## 1. Enable it

1. Open the avatar menu → **Settings** (or go to %BASE_URL%/settings/).
2. In **Two-step authentication** click **Enable two-step authentication**.
3. Scan the QR code with your app. If you can't scan it, type the key shown next to it.
4. Enter the 6-digit code the app shows and press **Verify and enable**.

## 2. Save your recovery codes

Right after enabling it you'll see **8 recovery codes** like `3fa9c1-07be42`.

- Each one lets you sign in **once** if you don't have your phone.
- They are shown **only this time**. Copy them into your password manager or print them.
- When you have two or fewer left, falcondatabase reminds you to generate new ones.

## 3. Signing in from now on

1. Enter your username (or email) and password as usual.
2. You'll be asked for the **authentication code**. Type the current code from your app, or a recovery code.

For your safety:

- Each code works only once.
- After **5 wrong codes** you have to start again with your password.
- The verification step expires after 5 minutes.

## Manage it

In **Settings → Two-step authentication**, after confirming your password, you can:

- **New recovery codes** — invalidates the old ones and shows 8 new codes.
- **Disable** — removes the second step.

## Lost your phone and your codes?

Ask the administrator. On the **Users** page they can reset two-step authentication for your account. You'll then sign in with just your password and can enable it again with your new phone.

## For administrators

- The **Users** page shows which accounts have 2FA enabled.
- Encourage everyone with access to important projects to enable it, starting with your own admin account.
