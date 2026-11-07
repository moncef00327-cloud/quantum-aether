# Validation
- 223 backend regression tests passed.
- 192 Chromium view checks: 7 review sections plus 17 service pages × Arabic/English × 320/390/768/1440 px. No horizontal overflow, missing labels or duplicate headings.
- Mobile drawer: focus on close, background inert, scroll lock, Escape to close.
- Invalid-domain error and valid reserved fixture POST through to report.
- Screenshots: artifacts/command-replacement.
- React/CSS production bundle built with npm run build; initial HTML generated for both supported reference languages.

Shared service pages assert 7 reference navigation items, no primary-nav, no mobile-dock and no references to removed UI assets. Business drawer focus, Escape and screenshots checked in both languages. Final backend suite: all 223 tests passed.
