---
name: <client-slug>-brand
kind: brand
title: "<Client Name> — brand"
status: active
client: <client-slug>
primary_color: "#000000"
secondary_color: "#333333"
accent_color: "#666666"
heading_font: "Calibri"
body_font: "Calibri"
logo_full: "logo-full.png"
logo_mono: "logo-mono.svg"
pptx_master: "<client-slug>.potx"
docx_master: "<client-slug>.dotx"
fonts: []
voice:
  tone: professional
  taboo: []
  preferred: []
created_at: YYYY-MM-DD
updated_at: YYYY-MM-DD
---

Replace all <placeholders> above. Place binary assets as siblings of this file.
Binary assets are exempt from .meta.yaml sidecars per /conventions/frontmatter.md.

Steps to create a new brand:
1. Copy this _template/ directory to /brands/<client-slug>/
2. Fill in all frontmatter fields
3. Add logo-full.png, logo-mono.svg, and master files as siblings
4. Run `uv run ft-autoclaude-index sync` to index the new brand
5. Create the client record: POST /clients with brand_slug: "<client-slug>-brand"
