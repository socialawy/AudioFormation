# Security Policy

## Supported Versions

The following versions of AudioFormation are currently supported with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1.0 | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in AudioFormation, please report it responsibly:

**Where to report:**
- **Email:** ahmed.itc@gmail.com (ahmed.itc@gmail.com)
- **GitHub Issues:** For non-sensitive security concerns, open a [GitHub Issue](https://github.com/socialawy/AudioFormation/issues) with the `security` label

**What to include:**
1. Description of the vulnerability
2. Steps to reproduce
3. Affected version(s)
4. Potential impact
5. Suggested fix (if available)

**Response timeline:**
- Acknowledgment within 48 hours
- Initial assessment within 5 business days
- Patch timeline communicated after assessment

**What to expect:**
- Confidential handling of your report
- Credit in release notes (with your permission)
- Coordinated disclosure process
- No legal action for good-faith security research

## Security Considerations

When using AudioFormation, be aware of the following security aspects:

### API Keys
- Store cloud TTS API keys (ElevenLabs, OpenAI) in `00_CONFIG/engines.json`
- Never commit API keys to version control
- Use environment variables for CI/CD pipelines

### File Paths
- AudioFormation validates all paths against project directory
- Symbolic links outside project scope are blocked
- User input is sanitized before filesystem operations

### Audio Processing
- Generated audio files are stored in project directories only
- No network calls except to configured TTS engines
- Local processing only (no cloud upload of generated content)

### Dependencies
- Regular security audits via `pip-audit`
- Minimal dependency footprint
- No compiled extensions from untrusted sources
