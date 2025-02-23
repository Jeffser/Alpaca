# Security Policy

## Supported Packaging and distribution methods

Alpaca only supports [Flatpak](https://flatpak.org/), [Snap](https://snapcraft.io/) and Apple MacOS packaging officially, any other packaging methods might not behave as expected.
Thus, official security-related support is only provided to the Flatpak, Snap and MacOS distribution as of right now.
This may be subject to change in the future.

## Data Handling

All user data is stored locally in an **unencrypted** SQLite3 (.db) file. Please exercise caution with your own device's security and data integrity.

The SQLite3 file includes:
- Chat metadata
- Messages
- Attachments
- API keys
- Bearer tokens
- Model metadata
- Preferences

**No user data or ussage data is ever uploaded to the internet by Alpaca**, if you detect your data being mishandled by any third parties please report it.

## Official Versions

The only ways Alpaca is being distributed officially are:

- [Alpaca's GitHub Repository Releases Page](https://github.com/Jeffser/Alpaca/releases)
- [Flathub](https://flathub.org/apps/com.jeffser.Alpaca)

## Where to report critical security vulnerabilities

As Alpaca is a public project with several thousands of users, it's extremely vital to keep it secure.
Flatpak confines it already due to sandboxing mechanisms, but nothing is bulletproof.

If you believe to have found a critical security vulnerability, **DO NOT** disclose it publicly immediately.
Allow for it to be patched first and **use the contact methods listed in the maintainer's profile** ([Jeffser](https://github.com/Jeffser))
to disclose any vulnerability privately.

Thank you in advance!
