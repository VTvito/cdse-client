# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.3.x   | :white_check_mark: |
| < 0.3   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in cdse-client, please report it responsibly:

1. **Do NOT** open a public GitHub issue for security vulnerabilities
2. Email the maintainer at: 75219756+VTvito@users.noreply.github.com
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes (optional)

## Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 1 week
- **Fix Timeline**: Depends on severity
  - Critical: 24-72 hours
  - High: 1-2 weeks
  - Medium/Low: Next release cycle

## Security Best Practices for Users

1. **Never commit credentials**: Use environment variables for `CDSE_CLIENT_ID` and `CDSE_CLIENT_SECRET`
2. **Use `.env` files** with `.gitignore` for local development
3. **Rotate credentials** periodically in your CDSE account
4. **Keep dependencies updated**: Run `pip install --upgrade cdse-client` regularly

## Dependencies

This library uses well-maintained dependencies with known security practices:
- `requests` - HTTP library with TLS/SSL support
- `requests-oauthlib` - OAuth2 authentication
- `tqdm` - Progress bars (no network access)

Optional dependencies are only loaded when needed, minimizing attack surface.
